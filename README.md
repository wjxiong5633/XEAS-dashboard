# XEAS 随访数据及主要疗效看板

Streamlit 入口：`dashboard/app.py`

## 本地运行

```bash
cd dashboard
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

页面默认读取 `2026-08-26` 的去姓名数据快照。也可在左侧上传包含 `DM`、`QS_YGTSS` 和 `SV` 工作表的新 Excel 文件，上传后将覆盖当前会话的默认数据。

## Streamlit Community Cloud

- Repository：`wjxiong5633/XEAS-dashboard`
- Branch：`main`
- Main file path：`dashboard/app.py`
- Python：`3.12`

## 数据安全

除经确认的 `2026-08-26` 默认数据快照外，其他原始 Excel、中间数据、分析结果、本地密钥和虚拟环境均由 `.gitignore` 排除。请勿提交真实凭证或未经批准的受试者数据。
