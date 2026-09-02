# XEAS YGTSS本地分析看板

纯 Python + Streamlit 实现，不依赖 R。上传包含 `DM` 和 `QS_YGTSS` 的主数据 Excel 后，页面直接进行数据清理、年龄分组、应答计算和绘图。

疗效分析读取上传或默认内置的 EDC 数据；随访管理可通过腾讯文档 OpenAPI 每5分钟自动同步在线随访表，并提供手动刷新按钮。同步解析只形成筛选号、年龄、状态及访视日期等去标识化字段，网页不展示姓名、门诊号、电话或自由文本备注。腾讯接口不可用时，页面会回退到 EDC 的 `SV` 工作表。

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

## 腾讯文档随访同步

1. 将 `.streamlit/secrets.toml.example` 复制为 `.streamlit/secrets.toml`。
2. 填入开放平台的 `client_id`、`access_token`、`open_id` 和分享链接中的文件ID。
3. 重新启动看板。侧边栏会显示最近同步时间，并可点击“立即刷新腾讯随访数据”。

部署到 Streamlit Community Cloud 时，在应用的 **Settings → Secrets** 中填写同名四项配置，不要把真实密钥提交到 GitHub。
