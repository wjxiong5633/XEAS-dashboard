# XEAS YGTSS本地分析看板

纯 Python + Streamlit 实现，不依赖 R。上传包含 `DM` 和 `QS_YGTSS` 的主数据 Excel 后，页面直接进行数据清理、年龄分组、应答计算和绘图。

## 启动

双击 `启动YGTSS看板.command`，首次会自动安装所需 Python 依赖。

也可在终端执行：

```bash
cd dashboard
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

未上传文件时，看板默认读取项目内2026-08-26 09:49:19版本的数据。
