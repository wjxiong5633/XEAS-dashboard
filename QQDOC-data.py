import os

import pandas as pd
import requests

# 凭证只从环境变量读取，不要写入代码或提交到 GitHub。
client_id = os.environ["QQDOC_CLIENT_ID"]
open_id = os.environ["QQDOC_OPEN_ID"]
access_token = os.environ["QQDOC_ACCESS_TOKEN"]
file_id = os.getenv("QQDOC_FILE_ID", "DU2NvUE9GeHhVQ0xC")

headers = {
    "Access-Token": access_token,
    "Client-Id": client_id,
    "Open-Id": open_id,
}

meta_url = f"https://docs.qq.com/openapi/v2/file/{file_id}/metadata"
resp = requests.get(meta_url, headers=headers, timeout=30)
resp.raise_for_status()
meta = resp.json()

sheet_id = meta["sheets"][0]["sheet_id"]
print(f"第一个Sheet ID: {sheet_id}")

range_url = f"https://docs.qq.com/openapi/spreadsheet/v2/files/{file_id}/sheets/{sheet_id}/values?range=A1:Z500"
resp = requests.get(range_url, headers=headers, timeout=30)
resp.raise_for_status()
values = resp.json().get("values", [])
if not values:
    raise ValueError("表格为空或读取范围无效")

df = pd.DataFrame(values[1:], columns=values[0])
print("成功读取，行数:", len(df))
print(df.head())
