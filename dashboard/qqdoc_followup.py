"""腾讯文档随访表只读同步与去标识化解析。"""

from __future__ import annotations

import re
import time
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Mapping
from xml.etree import ElementTree

import numpy as np
import pandas as pd
import requests


API_ROOT = "https://docs.qq.com/openapi"
FOLLOWUP_OFFSETS = {"V2": 14, "V3": 28, "V4": 42, "V5": 56, "V6": 84}
SCREEN_FAILURE_IDS = {"S01003", "S01011", "S01025", "S01053", "S01058", "S01066"}
WITHDRAWAL_IDS = {"S01014", "S01017", "S01026", "S01035", "S01039", "S01045", "S01062", "S01074"}
REQUIRED_SECRETS = ("QQDOC_CLIENT_ID", "QQDOC_ACCESS_TOKEN", "QQDOC_OPEN_ID", "QQDOC_FILE_ID")


def _request_json(method: str, url: str, headers: dict[str, str], **kwargs) -> dict:
    response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
    response.raise_for_status()
    payload = response.json()
    if payload.get("ret", 0) != 0:
        raise RuntimeError(f"腾讯文档接口错误 {payload.get('ret')}：{payload.get('msg', '未提供')}")
    return payload


def _converted_file_id(headers: dict[str, str], encoded_id: str) -> str:
    payload = _request_json(
        "GET", f"{API_ROOT}/drive/v2/util/converter", headers,
        params={"type": 2, "value": encoded_id},
    )
    data = payload.get("data", {})
    value = data if isinstance(data, str) else data.get("fileID") or data.get("fileId") or data.get("ID")
    if not value:
        raise RuntimeError("腾讯文档未返回可识别的fileID")
    return str(value)


def download_followup_xlsx(config: Mapping[str, object]) -> tuple[bytes, datetime]:
    """只读导出腾讯表格；返回XLSX字节和同步完成时间。"""
    missing = [key for key in REQUIRED_SECRETS if not str(config.get(key, "")).strip()]
    if missing:
        raise RuntimeError(f"缺少腾讯文档配置：{', '.join(missing)}")
    headers = {
        "Access-Token": str(config["QQDOC_ACCESS_TOKEN"]).strip(),
        "Client-Id": str(config["QQDOC_CLIENT_ID"]).strip(),
        "Open-Id": str(config["QQDOC_OPEN_ID"]).strip(),
    }
    file_id = _converted_file_id(headers, str(config["QQDOC_FILE_ID"]).strip())
    started = _request_json(
        "POST", f"{API_ROOT}/drive/v2/files/{file_id}/async-export",
        {**headers, "Content-Type": "application/x-www-form-urlencoded"},
        data={"exportType": "xlsx"},
    )
    operation_id = started.get("data", {}).get("operationID")
    if not operation_id:
        raise RuntimeError("腾讯文档导出接口未返回operationID")
    download_url = None
    for _ in range(20):
        progress = _request_json(
            "GET", f"{API_ROOT}/drive/v2/files/{file_id}/export-progress", headers,
            params={"operationID": operation_id},
        ).get("data", {})
        if int(progress.get("progress", 0)) >= 100 and progress.get("url"):
            download_url = progress["url"]
            break
        time.sleep(1)
    if not download_url:
        raise TimeoutError("等待腾讯文档导出超时")
    response = requests.get(download_url, timeout=60)
    response.raise_for_status()
    if not response.content.startswith(b"PK"):
        raise RuntimeError("腾讯文档下载结果不是有效XLSX")
    return response.content, datetime.now()


def _xlsx_rows(payload: bytes) -> list[dict[str, object]]:
    """避开腾讯导出样式与openpyxl的兼容问题，直接读取单元格值。"""
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in node.findall(".//x:t", ns)) for node in root.findall("x:si", ns)]
        sheet = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    rows: list[dict[str, object]] = []
    for row in sheet.findall(".//x:sheetData/x:row", ns):
        values: dict[str, object] = {}
        for cell in row.findall("x:c", ns):
            reference = cell.attrib.get("r", "")
            column_match = re.match(r"[A-Z]+", reference)
            if not column_match:
                continue
            column = column_match.group()
            cell_type = cell.attrib.get("t")
            value_node = cell.find("x:v", ns)
            if cell_type == "inlineStr":
                value = "".join(t.text or "" for t in cell.findall(".//x:t", ns))
            elif value_node is None:
                value = ""
            else:
                raw = value_node.text or ""
                value = shared[int(raw)] if cell_type == "s" and raw else raw
            values[column] = value
        rows.append(values)
    return rows


def _subject_id(value: object) -> str | None:
    text = str(value or "").strip().upper()
    if not text:
        return None
    if text.startswith("S"):
        digits = re.sub(r"\D", "", text)
    else:
        digits = re.sub(r"\D", "", text.split(".")[0])
    return f"S0{digits}" if len(digits) == 4 else f"S{digits}" if digits else None


def _age(value: object) -> float:
    text = str(value or "").strip()
    year = re.search(r"(\d+(?:\.\d+)?)\s*岁", text)
    month = re.search(r"(\d+)\s*(?:个?月|月龄)", text)
    if year:
        return float(year.group(1)) + (int(month.group(1)) / 12 if month else 0)
    try:
        return float(text)
    except ValueError:
        return np.nan


def _age_group(age: float) -> str | None:
    if pd.isna(age): return None
    if 4 <= age <= 6: return "A组（4–6岁）"
    if 6 < age <= 10: return "B组（>6–10岁）"
    if 10 < age < 17: return "C组（>10–16岁）"
    return None


def _date(value: object) -> pd.Timestamp:
    text = str(value or "").strip()
    if not text or text.startswith("#"):
        return pd.NaT
    try:
        number = float(text)
        if 20_000 < number < 100_000:
            return pd.Timestamp("1899-12-30") + pd.to_timedelta(number, unit="D")
    except ValueError:
        pass
    match = re.search(r"(20\d{2})[./年-](\d{1,2})[./月-](\d{1,2})", text)
    if match:
        return pd.to_datetime("-".join(match.groups()), errors="coerce")
    return pd.NaT


def parse_followup_schedule(payload: bytes) -> pd.DataFrame:
    """生成不含姓名、门诊号、电话及自由文本备注的随访宽表。"""
    actual_columns = {"V2": "M", "V3": "Q", "V4": "U", "V5": "Y", "V6": "AD"}
    records = []
    for row in _xlsx_rows(payload)[3:]:
        subject_id = _subject_id(row.get("A"))
        if not subject_id:
            continue
        age = _age(row.get("E"))
        screening_date = _date(row.get("G"))
        baseline_date = _date(row.get("I"))
        # 状态文字可能写在“提前退出”、某次实际访视日期或备注格中；只用于状态判定，不进入输出。
        status_text = " ".join(str(row.get(col, "")) for col in row if col not in {"B", "C", "D"})
        is_failure = subject_id in SCREEN_FAILURE_IDS or bool(re.search(r"筛败|筛选失败|不愿.*参加|不参与", status_text))
        is_withdrawn = subject_id in WITHDRAWAL_IDS or bool(re.search(r"提前退出|退出试验|退出研究|脱落", status_text))
        actuals = {visit: _date(row.get(column)) for visit, column in actual_columns.items()}
        if is_failure:
            status, baseline_date = "筛选失败", pd.NaT
        elif is_withdrawn:
            status = "退出"
        elif pd.notna(actuals["V6"]):
            status = "完成试验"
        elif pd.notna(baseline_date):
            status = "已入组"
        else:
            status = "筛选中"
        record = {
            "试验参与者编号": subject_id, "年龄": age, "年龄组": _age_group(age),
            "试验参与者状态": status, "知情日期": screening_date, "V1发药日期": baseline_date,
        }
        for visit, days in FOLLOWUP_OFFSETS.items():
            planned = baseline_date + pd.Timedelta(days=days) if pd.notna(baseline_date) else pd.NaT
            record[f"{visit}理论日期"] = planned
            record[f"{visit}下限"] = planned - pd.Timedelta(days=2) if pd.notna(planned) else pd.NaT
            record[f"{visit}上限"] = planned + pd.Timedelta(days=2) if pd.notna(planned) else pd.NaT
            record[f"{visit}实际日期"] = actuals[visit]
        records.append(record)
    result = pd.DataFrame(records).drop_duplicates("试验参与者编号", keep="last")
    return result.sort_values("试验参与者编号").reset_index(drop=True)


def sync_followup(config: Mapping[str, object], cache_dir: Path | None = None) -> tuple[pd.DataFrame, datetime]:
    payload, synced_at = download_followup_xlsx(config)
    schedule = parse_followup_schedule(payload)
    if schedule.empty:
        raise RuntimeError("腾讯文档中未识别到有效筛选号")
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / "latest.xlsx").write_bytes(payload)
    return schedule, synced_at
