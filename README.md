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

在页面左侧上传包含 `DM`、`QS_YGTSS` 和 `SV` 工作表的 Excel 文件。

## Streamlit Community Cloud

- Repository：`wjxiong5633/XEAS-dashboard`
- Branch：`main`
- Main file path：`dashboard/app.py`
- Python：`3.12`

## 数据安全

原始 Excel、中间数据、分析结果、本地密钥和虚拟环境已由 `.gitignore` 排除。请勿将受试者数据或真实凭证提交到 GitHub。
