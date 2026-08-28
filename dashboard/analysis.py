from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

import numpy as np
import pandas as pd
from scipy.stats import beta


VISITS = ["V1", "V2", "V3", "V4", "V5", "V6"]
WEEKS = {"V1": 0, "V2": 2, "V3": 4, "V4": 6, "V5": 8, "V6": 12}
VISIT_LABELS = {
    "V1": "V1 基线",
    "V2": "V2 第2周",
    "V3": "V3 第4周",
    "V4": "V4 第6周",
    "V5": "V5 第8周",
    "V6": "V6 第12周",
}
AGE_GROUPS = ["A组（4–6岁）", "B组（>6–10岁）", "C组（>10–16岁）"]
SCORES = {
    "YGTSS-TTS": "ygtss_tts",
    "运动抽动总分": "motor_tic_score",
    "发声抽动总分": "vocal_tic_score",
    "总损害分": "impairment_score",
    "YGTSS总分（GSS）": "global_severity_score",
}
MANUAL_SCREEN_FAILURE_IDS = ["S01003", "S01011", "S01025", "S01053", "S01058", "S01066"]
MANUAL_WITHDRAWAL_IDS = ["S01014", "S01017", "S01026", "S01035", "S01039", "S01045", "S01074"]


@dataclass
class AnalysisBundle:
    dm: pd.DataFrame
    longitudinal: pd.DataFrame
    v5_change: pd.DataFrame
    visit_tracking: pd.DataFrame
    validation: pd.DataFrame
    source_name: str


def _age_group(age: float | None) -> str | None:
    if pd.isna(age):
        return None
    if 4 <= age <= 6:
        return AGE_GROUPS[0]
    if 6 < age <= 10:
        return AGE_GROUPS[1]
    if 10 < age < 17:
        return AGE_GROUPS[2]
    return None


def _age_status(age: float | None) -> str:
    if pd.isna(age):
        return "年龄缺失"
    if age < 4:
        return "低于4岁"
    if age >= 17:
        return "高于16岁"
    return "已分组"


def _read_excel(source: str | Path | BinaryIO | bytes) -> pd.ExcelFile:
    if isinstance(source, bytes):
        source = BytesIO(source)
    return pd.ExcelFile(source)


def load_and_analyse(source: str | Path | BinaryIO | bytes, source_name: str = "上传数据") -> AnalysisBundle:
    book = _read_excel(source)
    required = {"DM", "QS_YGTSS"}
    missing = required - set(book.sheet_names)
    if missing:
        raise ValueError(f"缺少必需工作表：{'、'.join(sorted(missing))}")

    dm_raw = pd.read_excel(book, sheet_name="DM", skiprows=1)
    qs_raw = pd.read_excel(book, sheet_name="QS_YGTSS", skiprows=1)
    if dm_raw.shape[1] < 12:
        raise ValueError("DM工作表结构异常：预期至少12列。")
    if qs_raw.shape[1] < 27:
        raise ValueError("QS_YGTSS工作表结构异常：预期至少27列。")

    dm = pd.DataFrame({
        "subject_id": dm_raw.iloc[:, 2].astype("string").str.strip(),
        "subject_status": dm_raw.iloc[:, 3].astype("string").str.strip(),
        "sex": dm_raw.iloc[:, 9].astype("string"),
        "birth_date": dm_raw.iloc[:, 10],
        "age": pd.to_numeric(dm_raw.iloc[:, 11], errors="coerce"),
    }).dropna(subset=["subject_id"]).drop_duplicates("subject_id")
    dm["age_group"] = dm["age"].map(_age_group)
    dm["age_group_status"] = dm["age"].map(_age_status)

    if "SV" in book.sheet_names:
        sv_raw = pd.read_excel(book, sheet_name="SV", skiprows=1)
        visit_tracking = pd.DataFrame({
            "subject_id": sv_raw.iloc[:, 2].astype("string").str.strip(),
            "subject_status": sv_raw.iloc[:, 3].astype("string").str.strip(),
            "visit": sv_raw.iloc[:, 4].astype("string").str.strip(),
            "visit_label": sv_raw.iloc[:, 5].astype("string"),
            "performed": sv_raw.iloc[:, 9].astype("string").str.strip(),
            "visit_date": pd.to_datetime(sv_raw.iloc[:, 10], errors="coerce"),
        }).dropna(subset=["subject_id"])
    else:
        visit_tracking = pd.DataFrame(columns=["subject_id", "subject_status", "visit", "visit_label", "performed", "visit_date"])

    long = pd.DataFrame({
        "subject_id": qs_raw.iloc[:, 2].astype("string").str.strip(),
        "visit": qs_raw.iloc[:, 4].astype("string").str.strip(),
        "visit_label": qs_raw.iloc[:, 5].astype("string"),
        "motor_tic_score": pd.to_numeric(qs_raw.iloc[:, 17], errors="coerce"),
        "vocal_tic_score": pd.to_numeric(qs_raw.iloc[:, 24], errors="coerce"),
        "impairment_score": pd.to_numeric(qs_raw.iloc[:, 25], errors="coerce"),
        "global_severity_score": pd.to_numeric(qs_raw.iloc[:, 26], errors="coerce"),
    })
    long = long[long["visit"].isin(VISITS)].copy()
    long["week"] = long["visit"].map(WEEKS)
    long["ygtss_tts"] = long[["motor_tic_score", "vocal_tic_score"]].sum(axis=1, min_count=2)
    long = long.merge(dm, on="subject_id", how="left").sort_values(["subject_id", "week"])
    # 人工确认的筛选失败者只计入筛选进展，不进入任何后续疗效、亚组或个体分析。
    screen_failure_records = int(long["subject_id"].isin(MANUAL_SCREEN_FAILURE_IDS).sum())
    long = long[~long["subject_id"].isin(MANUAL_SCREEN_FAILURE_IDS)].copy()

    duplicate = long.groupby(["subject_id", "visit"]).size().reset_index(name="n").query("n > 1")
    checks = [
        ("DM工作表", "通过", len(dm), "已识别受试者"),
        ("QS_YGTSS工作表", "通过", long["subject_id"].nunique(), "已识别YGTSS受试者"),
        ("重复ID-访视", "通过" if duplicate.empty else "需处理", len(duplicate), "同一ID同一访视重复"),
        ("筛选失败排除", "通过", screen_failure_records, "对应记录已从后续疗效分析排除"),
        ("DM年龄缺失/范围外（含筛败）", "提示", int(dm["age_group"].isna().sum()), "DM全部受试者口径；不进入A/B/C分组"),
    ]
    validation = pd.DataFrame(checks, columns=["检查项", "状态", "数量", "说明"])
    if not duplicate.empty:
        raise ValueError("发现同一受试者同一访视的重复记录，请先修正数据。")

    # 个体疗效分析以QS_YGTSS中出现过的受试者为范围；仅在DM中出现者不计为V5缺失。
    v5 = build_v5_change(long)
    return AnalysisBundle(dm=dm, longitudinal=long, v5_change=v5, visit_tracking=visit_tracking, validation=validation, source_name=source_name)


def recruitment_summary(bundle: AnalysisBundle) -> dict[str, int]:
    status_by_id = dict(zip(bundle.dm["subject_id"].astype(str), bundle.dm["subject_status"].fillna("未知").astype(str).str.strip()))
    for subject_id in MANUAL_SCREEN_FAILURE_IDS:
        status_by_id[subject_id] = "筛选失败"
    for subject_id in MANUAL_WITHDRAWAL_IDS:
        status_by_id[subject_id] = "退出"
    statuses = pd.Series(status_by_id, dtype="string")
    enrolled = int(statuses.isin(["已入组", "完成试验", "退出"]).sum())
    screening = int(statuses.eq("筛选中").sum())
    failed = int(statuses.str.contains("筛选失败|筛败", regex=True, na=False).sum())
    return {
        "已筛选": len(statuses),
        "已入组": enrolled,
        "筛选失败": failed,
        "筛选中": screening,
        "已退出": int(statuses.eq("退出").sum()),
        "已完成试验": int(statuses.eq("完成试验").sum()),
    }


def disposition_detail(bundle: AnalysisBundle) -> pd.DataFrame:
    detail = pd.DataFrame({
        "受试者编号": [*MANUAL_SCREEN_FAILURE_IDS, *MANUAL_WITHDRAWAL_IDS],
        "状态": ["筛选失败"] * len(MANUAL_SCREEN_FAILURE_IDS) + ["退出"] * len(MANUAL_WITHDRAWAL_IDS),
        "数据来源": ["人工补充"] * (len(MANUAL_SCREEN_FAILURE_IDS) + len(MANUAL_WITHDRAWAL_IDS)),
    })
    demographics = bundle.dm[["subject_id", "age", "age_group"]].rename(
        columns={"subject_id": "受试者编号", "age": "年龄", "age_group": "年龄组"}
    )
    detail = detail.merge(demographics, on="受试者编号", how="left")
    detail["年龄组"] = detail["年龄组"].fillna("年龄未分组")
    return detail[["受试者编号", "年龄", "年龄组", "状态", "数据来源"]]


FOLLOWUP_OFFSETS = {"V2": 14, "V3": 28, "V4": 42, "V5": 56, "V6": 84}


def followup_schedule(bundle: AnalysisBundle) -> pd.DataFrame:
    """生成去标识化随访计划：不包含姓名、门诊号或电话。"""
    subject_ids = sorted(set(bundle.dm["subject_id"].astype(str)) | set(MANUAL_SCREEN_FAILURE_IDS) | set(MANUAL_WITHDRAWAL_IDS))
    demographics = bundle.dm.set_index("subject_id")[["age", "age_group", "subject_status"]].to_dict("index")
    completed = bundle.visit_tracking[bundle.visit_tracking["performed"].eq("是")].copy()
    actual = completed.pivot_table(index="subject_id", columns="visit", values="visit_date", aggfunc="min")
    rows = []
    for subject_id in subject_ids:
        info = demographics.get(subject_id, {})
        if subject_id in MANUAL_SCREEN_FAILURE_IDS:
            status = "筛选失败"
        elif subject_id in MANUAL_WITHDRAWAL_IDS:
            status = "退出"
        else:
            status = info.get("subject_status", "数据待补充")
        screening_date = actual.at[subject_id, "SCR"] if subject_id in actual.index and "SCR" in actual.columns else pd.NaT
        baseline_date = actual.at[subject_id, "V1"] if subject_id in actual.index and "V1" in actual.columns else pd.NaT
        if status == "筛选失败":
            baseline_date = pd.NaT
        row = {
            "受试者编号": subject_id,
            "年龄": info.get("age", np.nan),
            "年龄组": info.get("age_group"),
            "受试者状态": status,
            "知情日期": screening_date,
            "V1发药日期": baseline_date,
        }
        for visit, days in FOLLOWUP_OFFSETS.items():
            planned = baseline_date + pd.Timedelta(days=days) if pd.notna(baseline_date) else pd.NaT
            row[f"{visit}理论日期"] = planned
            row[f"{visit}下限"] = planned - pd.Timedelta(days=2) if pd.notna(planned) else pd.NaT
            row[f"{visit}上限"] = planned + pd.Timedelta(days=2) if pd.notna(planned) else pd.NaT
            row[f"{visit}实际日期"] = actual.at[subject_id, visit] if subject_id in actual.index and visit in actual.columns else pd.NaT
        rows.append(row)
    return pd.DataFrame(rows)


def followup_calendar(bundle: AnalysisBundle, as_of: pd.Timestamp | None = None) -> pd.DataFrame:
    """将宽格式随访计划转换为按访视排列的日历。"""
    as_of = pd.Timestamp.today().normalize() if as_of is None else pd.Timestamp(as_of).normalize()
    schedule = followup_schedule(bundle)
    rows = []
    for _, person in schedule.iterrows():
        for visit in FOLLOWUP_OFFSETS:
            planned = pd.to_datetime(person[f"{visit}理论日期"], errors="coerce")
            if pd.isna(planned):
                continue
            lower = pd.to_datetime(person[f"{visit}下限"], errors="coerce")
            upper = pd.to_datetime(person[f"{visit}上限"], errors="coerce")
            actual = pd.to_datetime(person[f"{visit}实际日期"], errors="coerce")
            if pd.notna(actual):
                timing = "窗内完成" if lower <= actual <= upper else "窗外完成"
                days_from_plan = int((actual.normalize() - planned.normalize()).days)
            elif as_of < lower:
                timing = "待访"
                days_from_plan = int((planned.normalize() - as_of).days)
            elif as_of <= upper:
                timing = "访视窗内"
                days_from_plan = int((planned.normalize() - as_of).days)
            else:
                timing = "逾期未访"
                days_from_plan = int((as_of - planned.normalize()).days)
            rows.append({
                "受试者编号": person["受试者编号"],
                "年龄": person["年龄"],
                "年龄组": person["年龄组"],
                "受试者状态": person["受试者状态"],
                "访视": visit,
                "访视时间": VISIT_LABELS[visit],
                "理论日期": planned,
                "允许窗起": lower,
                "允许窗止": upper,
                "实际日期": actual,
                "随访状态": timing,
                "相差天数": days_from_plan,
            })
    columns = ["受试者编号", "年龄", "年龄组", "受试者状态", "访视", "访视时间", "理论日期", "允许窗起", "允许窗止", "实际日期", "随访状态", "相差天数"]
    return pd.DataFrame(rows, columns=columns).sort_values(["理论日期", "受试者编号"]).reset_index(drop=True)


def visit_completion_summary(bundle: AnalysisBundle) -> pd.DataFrame:
    visit_order = ["SCR", *VISITS]
    if bundle.visit_tracking.empty:
        return pd.DataFrame({"访视": visit_order, "完成访视人数": [0] * len(visit_order)})
    completed = bundle.visit_tracking[bundle.visit_tracking["performed"].eq("是")]
    completed = completed[
        completed["visit"].eq("SCR") | ~completed["subject_id"].isin(MANUAL_SCREEN_FAILURE_IDS)
    ]
    counts = completed.groupby("visit")["subject_id"].nunique()
    labels = {"SCR": "筛选期", **VISIT_LABELS}
    out = pd.DataFrame({"访视": visit_order})
    out["访视时间"] = out["访视"].map(labels)
    out["完成访视人数"] = out["访视"].map(counts).fillna(0).astype(int)
    return out


def visit_count_audit(bundle: AnalysisBundle) -> pd.DataFrame:
    """同时展示SV原始人数与排除筛选失败后的管理口径。"""
    visit_order = ["SCR", *VISITS]
    performed = bundle.visit_tracking[bundle.visit_tracking["performed"].eq("是")]
    raw = performed.groupby("visit")["subject_id"].nunique()
    managed = performed[
        performed["visit"].eq("SCR") | ~performed["subject_id"].isin(MANUAL_SCREEN_FAILURE_IDS)
    ].groupby("visit")["subject_id"].nunique()
    labels = {"SCR": "筛选期", **VISIT_LABELS}
    out = pd.DataFrame({"访视": visit_order})
    out["访视时间"] = out["访视"].map(labels)
    out["SV原始完成数"] = out["访视"].map(raw).fillna(0).astype(int)
    out["排除筛败后人数"] = out["访视"].map(managed).fillna(0).astype(int)
    out["排除人数"] = out["SV原始完成数"] - out["排除筛败后人数"]
    return out


def build_v5_change(data: pd.DataFrame, dm: pd.DataFrame | None = None) -> pd.DataFrame:
    base = data[data["visit"].isin(["V1", "V5"])][["subject_id", "visit", "ygtss_tts"]]
    demographics = (dm if dm is not None else data)[["subject_id", "age", "age_group"]].drop_duplicates("subject_id")
    wide = base.pivot(index="subject_id", columns="visit", values="ygtss_tts").reset_index()
    wide = demographics.merge(wide, on="subject_id", how="left")
    for col in ["V1", "V5"]:
        if col not in wide:
            wide[col] = np.nan
    wide = wide.rename(columns={"V1": "baseline_v1", "V5": "week8_v5"})
    wide["change_v5_minus_v1"] = wide["week8_v5"] - wide["baseline_v1"]
    wide["reduction"] = wide["baseline_v1"] - wide["week8_v5"]
    evaluable = wide["baseline_v1"].notna() & wide["week8_v5"].notna() & wide["baseline_v1"].ne(0)
    wide["percent_reduction"] = np.where(evaluable, 100 * wide["reduction"] / wide["baseline_v1"], np.nan)
    wide["analysis_status"] = np.select(
        [wide["baseline_v1"].isna() & wide["week8_v5"].isna(), wide["baseline_v1"].isna(), wide["week8_v5"].isna(), wide["baseline_v1"].eq(0)],
        ["V1和V5均缺失", "V1缺失", "V5缺失", "V1为0，无法计算"],
        default="可计算",
    )
    wide["responder_30pct"] = pd.array(np.where(evaluable, wide["percent_reduction"] >= 30, pd.NA), dtype="boolean")
    return wide.sort_values("subject_id")


def subset(bundle: AnalysisBundle, group: str) -> pd.DataFrame:
    if group == "总体":
        return bundle.longitudinal.copy()
    return bundle.longitudinal[bundle.longitudinal["age_group"].eq(group)].copy()


def exact_ci(successes: int, total: int, alpha: float = 0.05) -> tuple[float, float]:
    if total == 0:
        return np.nan, np.nan
    low = 0.0 if successes == 0 else beta.ppf(alpha / 2, successes, total - successes + 1)
    high = 1.0 if successes == total else beta.ppf(1 - alpha / 2, successes + 1, total - successes)
    return 100 * low, 100 * high


def v5_response_summary(bundle: AnalysisBundle) -> pd.DataFrame:
    rows = []
    for label in ["总体", *AGE_GROUPS]:
        v = bundle.v5_change if label == "总体" else bundle.v5_change[bundle.v5_change["age_group"].eq(label)]
        e = v[v["responder_30pct"].notna()]
        n, r = len(e), int(e["responder_30pct"].sum())
        lo, hi = exact_ci(r, n)
        rows.append([label, n, r, 100 * r / n if n else np.nan, lo, hi])
    return pd.DataFrame(rows, columns=["分析组", "可评价人数", "应答人数", "应答比例（%）", "95%CI下限", "95%CI上限"])


def visit_summary(data: pd.DataFrame, score: str) -> pd.DataFrame:
    out = data.groupby(["visit", "week"], observed=True)[score].agg(["count", "mean", "std", "median", "min", "max"]).reset_index()
    out["se"] = out["std"] / np.sqrt(out["count"])
    out["visit"] = pd.Categorical(out["visit"], VISITS, ordered=True)
    return out.sort_values("visit")


def response_by_visit(data: pd.DataFrame, score: str, thresholds: list[int]) -> pd.DataFrame:
    base = data[data["visit"].eq("V1")][["subject_id", score]].rename(columns={score: "baseline"})
    follow = data[data["visit"].isin(VISITS[1:])][["subject_id", "visit", "week", score]].rename(columns={score: "followup"}).merge(base, on="subject_id", how="left")
    follow["evaluable"] = follow["baseline"].notna() & follow["baseline"].ne(0) & follow["followup"].notna()
    follow["percent_reduction"] = np.where(follow["evaluable"], 100 * (follow["baseline"] - follow["followup"]) / follow["baseline"], np.nan)
    rows = []
    for threshold in thresholds:
        for visit in VISITS[1:]:
            x = follow[(follow["visit"].eq(visit)) & follow["evaluable"]]
            n = len(x); r = int((x["percent_reduction"] >= threshold).sum())
            lo, hi = exact_ci(r, n)
            rows.append([visit, WEEKS[visit], threshold, n, r, 100 * r / n if n else np.nan, lo, hi])
    return pd.DataFrame(rows, columns=["访视", "研究周", "降低阈值（%）", "可评价人数", "应答人数", "应答比例（%）", "95%CI下限", "95%CI上限"])


def age_response_results(bundle: AnalysisBundle, threshold: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """返回指定TTS降低阈值下的第8周年龄组汇总和各访视明细。"""
    visit_pieces = []
    v5_rows = []
    for group_label in ["总体", *AGE_GROUPS]:
        group_data = subset(bundle, group_label)
        result = response_by_visit(group_data, "ygtss_tts", [threshold])
        result["分析组"] = group_label
        visit_pieces.append(result)
        v5 = result[result["访视"].eq("V5")].iloc[0]
        v5_rows.append([
            group_label, int(v5["可评价人数"]), int(v5["应答人数"]),
            v5["应答比例（%）"], v5["95%CI下限"], v5["95%CI上限"],
        ])
    v5_summary = pd.DataFrame(v5_rows, columns=["分析组", "可评价人数", "应答人数", "应答比例（%）", "95%CI下限", "95%CI上限"])
    return v5_summary, pd.concat(visit_pieces, ignore_index=True)


def completeness(bundle: AnalysisBundle) -> pd.DataFrame:
    m = bundle.longitudinal.assign(has_score=bundle.longitudinal["ygtss_tts"].notna()).pivot(index="subject_id", columns="visit", values="has_score")
    return m.reindex(columns=VISITS).fillna(False).reset_index()
