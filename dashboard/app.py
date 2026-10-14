from __future__ import annotations

import calendar as calendar_lib
import html
from datetime import datetime
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analysis import (
    AGE_GROUPS, MANUAL_WITHDRAWAL_IDS, SCORES, VISITS, VISIT_LABELS, age_response_results,
    completeness, disposition_detail, disposition_from_schedule, followup_calendar, followup_calendar_from_schedule, followup_completion_matrix,
    followup_schedule, load_and_analyse, response_by_visit, subset,
    recruitment_from_schedule, recruitment_summary, visit_completion_summary, v5_response_summary, visit_summary,
    visit_completion_from_schedule, visit_count_audit, visit_count_audit_from_schedule,
)
from qqdoc_followup import REQUIRED_SECRETS, sync_followup

APP_DIR = Path(__file__).resolve().parent
PROJECT_DIR = APP_DIR.parent
DEFAULT_FILE = PROJECT_DIR / "DATA" / "XEAS_dashboard_default_2026-08-26.xlsx"

st.set_page_config(page_title="XEAS随访数据及主要疗效看板", page_icon="📊", layout="wide")
st.markdown("""
<style>
.block-container{padding-top:1.4rem;padding-bottom:2rem}.stMetric{background:#f4f7fa;border:1px solid #dce4ec;padding:14px 16px;border-radius:6px}
h1,h2,h3{color:#17365d}.small-note{color:#64748b;font-size:.88rem}.status-ok{color:#137333;font-weight:600}.status-warn{color:#a15c00;font-weight:600}
</style>
""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def analyse_bytes(payload: bytes, name: str):
    return load_and_analyse(payload, name)


@st.cache_data(ttl=300, show_spinner="正在从腾讯文档同步最新随访数据……")
def load_qqdoc_followup(config_items: tuple[tuple[str, str], ...]):
    return sync_followup(dict(config_items))


def fmt_table(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    numeric = out.select_dtypes(include="number").columns
    out[numeric] = out[numeric].round(2)
    return out


def visit_display_status(row: pd.Series, visit: str, today: pd.Timestamp) -> str:
    """Return the compact visit status used by the follow-up master table."""
    actual = pd.to_datetime(row.get(f"{visit}实际日期"), errors="coerce")
    planned = pd.to_datetime(row.get(f"{visit}理论日期"), errors="coerce")
    lower = pd.to_datetime(row.get(f"{visit}下限"), errors="coerce")
    upper = pd.to_datetime(row.get(f"{visit}上限"), errors="coerce")
    if pd.notna(actual):
        return "已完成（超窗）" if pd.notna(lower) and pd.notna(upper) and not lower <= actual <= upper else "已完成"
    if pd.isna(planned):
        return ""
    if pd.notna(upper) and upper < today:
        return "逾期未访"
    return "待访视"


def render_month_calendar(month_schedule: pd.DataFrame, month_start: pd.Timestamp) -> None:
    """Render a compact CMP-style monthly visit calendar."""
    by_date = {day.date(): group for day, group in month_schedule.groupby("理论日期")}
    weeks = calendar_lib.Calendar(firstweekday=0).monthdatescalendar(month_start.year, month_start.month)
    cells: list[str] = []
    for week in weeks:
        for day in week:
            if day.month != month_start.month:
                cells.append('<div class="visit-cal-cell visit-cal-muted"></div>')
                continue
            day_frame = by_date.get(day)
            if day_frame is None:
                cells.append(f'<div class="visit-cal-cell"><div class="visit-cal-day">{day.day}</div><div class="visit-cal-empty">无安排</div></div>')
                continue
            counts = day_frame["访视"].value_counts()
            badges = "".join(
                f'<span class="visit-cal-badge">{html.escape(str(name))} {int(count)}</span>'
                for name, count in counts.items()
            )
            risk_count = int(day_frame["随访状态"].isin(["逾期未访", "窗外完成"]).sum())
            risks = f'<div class="visit-cal-risk">⚠ 逾期/超窗 {risk_count}</div>' if risk_count else ""
            subjects = "".join(
                '<div class="visit-cal-subject">'
                f'<span>{html.escape(str(row["试验参与者编号"]))}</span><em>{html.escape(str(row["访视"]))}</em></div>'
                for _, row in day_frame.sort_values(["试验参与者编号", "访视"]).iterrows()
            )
            cells.append(
                '<div class="visit-cal-cell">'
                f'<div class="visit-cal-day">{day.day}<span>{len(day_frame)}次</span></div>'
                f'<div class="visit-cal-badges">{badges}</div><div class="visit-cal-subjects">{subjects}</div>{risks}</div>'
            )
    st.markdown(
        """
        <style>
        .visit-cal-weekdays,.visit-cal-grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:6px}
        .visit-cal-weekdays div{padding:6px;text-align:center;color:#657080;font-size:.84rem;font-weight:600}
        .visit-cal-grid{margin-bottom:14px}.visit-cal-cell{min-height:120px;padding:9px;border:1px solid #dfe5ec;border-radius:10px;background:#fff}
        .visit-cal-muted{background:#f7f8fa;border-color:#eef0f3}.visit-cal-day{font-weight:700;color:#273241;margin-bottom:8px;display:flex;justify-content:space-between}
        .visit-cal-day span{font-size:.74rem;color:#697586;font-weight:500}.visit-cal-badges{display:flex;flex-wrap:wrap;gap:4px}
        .visit-cal-badge{font-size:.72rem;background:#e8f1fb;color:#235b8e;border-radius:999px;padding:2px 6px}
        .visit-cal-subjects{display:flex;flex-direction:column;gap:3px;margin-top:7px}.visit-cal-subject{display:flex;justify-content:space-between;gap:5px;padding:3px 5px;border-radius:5px;background:#f3f6f9;font-size:.7rem}
        .visit-cal-subject span{color:#273241;font-weight:600;overflow-wrap:anywhere}.visit-cal-subject em{color:#697586;font-style:normal;white-space:nowrap}
        .visit-cal-risk{font-size:.72rem;color:#a43b32;background:#fdecea;border-radius:6px;padding:3px 5px;margin-top:6px}.visit-cal-empty{font-size:.74rem;color:#a0a7b0;margin-top:28px;text-align:center}
        @media(max-width:900px){.visit-cal-cell{min-height:92px;padding:5px}.visit-cal-subjects{display:none}.visit-cal-badge{font-size:.65rem}}
        </style>
        <div class="visit-cal-weekdays"><div>周一</div><div>周二</div><div>周三</div><div>周四</div><div>周五</div><div>周六</div><div>周日</div></div>
        <div class="visit-cal-grid">%s</div>
        """ % "".join(cells), unsafe_allow_html=True,
    )


def line_chart(data: pd.DataFrame, score_col: str, title: str):
    summary = visit_summary(data, score_col)
    fig = go.Figure()
    for _, person in data.groupby("subject_id"):
        if person[score_col].notna().sum() >= 2:
            fig.add_trace(go.Scatter(x=person["visit"], y=person[score_col], mode="lines", line=dict(color="rgba(150,160,170,.25)", width=1), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=summary["visit"], y=summary["mean"], mode="lines+markers", name="观察均值", line=dict(color="#245b85", width=4), marker=dict(size=9, color="#e8752b"), error_y=dict(type="data", array=summary["se"], visible=True)))
    fig.update_layout(title=title, xaxis=dict(categoryorder="array", categoryarray=VISITS, tickmode="array", tickvals=VISITS, ticktext=[VISIT_LABELS[v] for v in VISITS]), yaxis_title="评分（分）", height=500, margin=dict(l=30,r=20,t=65,b=35), legend=dict(orientation="h"))
    return fig, summary


def response_line(df: pd.DataFrame, title: str):
    fig = px.line(df, x="访视", y="应答比例（%）", color="降低阈值（%）", markers=True, title=title, category_orders={"访视": VISITS[1:]})
    fig.update_layout(height=430, yaxis_range=[0,100], yaxis_title="应答比例（%）", legend_title="降低阈值")
    return fig


def individual_chart(person: pd.DataFrame, outcome: pd.Series, chart_type: str):
    subject_id = str(outcome["subject_id"])
    response_flag = outcome["responder_30pct"]
    is_nonresponder = pd.notna(response_flag) and not bool(response_flag)
    is_missing = pd.isna(outcome["week8_v5"])
    is_withdrawn = subject_id in MANUAL_WITHDRAWAL_IDS
    if is_withdrawn:
        suffix, background, border = "（退出）", "#e2f3e8", "#2e8b57"
    elif is_nonresponder:
        suffix, background, border = "（未达30%）", "#ffe3e3", "#d62728"
    elif is_missing:
        suffix, background, border = "（缺少V5）", "#fff4d6", "#d79b00"
    else:
        suffix, background, border = "", "#ffffff", "#cbd5e1"

    fig = go.Figure()
    if chart_type == "TTS及组成评分":
        series = [
            ("YGTSS-TTS", "ygtss_tts", "#245b85", 3),
            ("运动抽动总分", "motor_tic_score", "#4b8b65", 2),
            ("发声抽动总分", "vocal_tic_score", "#e8752b", 2),
        ]
        for label, col, color, width in series:
            fig.add_trace(go.Scatter(
                x=person["visit"], y=person[col], mode="lines+markers",
                name=label, line=dict(color=color, width=width), marker=dict(size=6),
                connectgaps=False,
            ))
        labels = person[person["visit"].isin(["V1", "V5"]) & person["ygtss_tts"].notna()]
        fig.add_trace(go.Scatter(
            x=labels["visit"], y=labels["ygtss_tts"], mode="text",
            text=labels["ygtss_tts"].map(lambda x: f"{x:.0f}"), textposition="top center",
            textfont=dict(size=11, color="#17365d"), showlegend=False, hoverinfo="skip",
        ))
        y_title = "评分（分）"
    else:
        fig.add_trace(go.Scatter(
            x=person["visit"], y=person["impairment_score"], mode="lines+markers+text",
            name="总损害分", line=dict(color="#7b5aa6", width=3), marker=dict(size=7),
            text=person["impairment_score"].map(lambda x: "" if pd.isna(x) else f"{x:.0f}"),
            textposition="top center",
        ))
        y_title = "总损害分（分）"

    fig.update_layout(
        title=dict(text=f"{subject_id}{suffix}", x=.5, xanchor="center", font=dict(size=15, color="#237347" if is_withdrawn else "#9b1c1c" if is_nonresponder else "#17365d")),
        height=285, margin=dict(l=34, r=12, t=45, b=42),
        paper_bgcolor=background, plot_bgcolor=background,
        xaxis=dict(categoryorder="array", categoryarray=VISITS, tickmode="array", tickvals=VISITS,
                   ticktext=[VISIT_LABELS[v].replace(" ", "<br>") for v in VISITS], tickfont=dict(size=9), fixedrange=True),
        yaxis=dict(title=dict(text=y_title, font=dict(size=10)), rangemode="tozero", fixedrange=True, tickfont=dict(size=9)),
        legend=dict(orientation="h", y=-.30, x=.5, xanchor="center", font=dict(size=8)),
        hovermode="x unified", showlegend=chart_type == "TTS及组成评分",
        shapes=[dict(type="rect", xref="paper", yref="paper", x0=0, y0=0, x1=1, y1=1, line=dict(color=border, width=2))],
    )
    return fig


st.sidebar.title("数据与筛选")
uploaded = st.sidebar.file_uploader("上传主数据Excel", type=["xlsx", "xls"], help="需包含DM和QS_YGTSS工作表。上传数据仅在当前本地会话使用。")
try:
    if uploaded:
        bundle = analyse_bytes(uploaded.getvalue(), uploaded.name)
        source_note = f"本地上传：{uploaded.name}"
    elif DEFAULT_FILE.exists():
        bundle = analyse_bytes(DEFAULT_FILE.read_bytes(), DEFAULT_FILE.name)
        source_note = f"默认示例：{DEFAULT_FILE.name}"
    else:
        st.title("XEAS随访数据及主要疗效看板")
        st.info("请在左侧上传包含 DM、QS_YGTSS 和 SV 工作表的 Excel 文件。")
        st.caption("为保护试验参与者数据，在线版不内置原始数据；上传文件仅用于当前会话的分析。")
        st.stop()
except Exception as exc:
    st.error(f"数据读取失败：{exc}")
    st.stop()

try:
    secret_values = {key: str(st.secrets.get(key, "")).strip() for key in REQUIRED_SECRETS}
except (FileNotFoundError, KeyError):
    secret_values = {key: "" for key in REQUIRED_SECRETS}

qqdoc_ready = all(secret_values.values())
qqdoc_error = None
if qqdoc_ready:
    try:
        qqdoc_schedule, qqdoc_synced_at = load_qqdoc_followup(tuple(sorted(secret_values.items())))
        followup_data_source = "腾讯文档实时随访表"
    except Exception as exc:
        qqdoc_error = str(exc)
        qqdoc_schedule = followup_schedule(bundle)
        qqdoc_synced_at = None
        followup_data_source = "EDC的SV工作表（腾讯同步失败，已回退）"
else:
    qqdoc_schedule = followup_schedule(bundle)
    qqdoc_synced_at = None
    followup_data_source = "EDC的SV工作表（未配置腾讯文档）"

group = st.sidebar.selectbox("分析人群", ["总体", *AGE_GROUPS])
metric_label = st.sidebar.selectbox("评分指标", list(SCORES))
metric = SCORES[metric_label]
st.sidebar.caption(source_note)
st.sidebar.caption(f"随访数据：{followup_data_source}")
if qqdoc_synced_at:
    st.sidebar.caption(f"腾讯文档同步：{qqdoc_synced_at:%Y-%m-%d %H:%M:%S}")
    if st.sidebar.button("立即刷新腾讯随访数据", use_container_width=True):
        load_qqdoc_followup.clear()
        st.rerun()
st.sidebar.caption(f"页面计算时间：{datetime.now():%Y-%m-%d %H:%M}")

data = subset(bundle, group)
v5_all = bundle.v5_change if group == "总体" else bundle.v5_change[bundle.v5_change["age_group"].eq(group)]
evaluable = v5_all[v5_all["responder_30pct"].notna()]
responders = int(evaluable["responder_30pct"].sum())
response_rate = 100 * responders / len(evaluable) if len(evaluable) else np.nan
missing_v5 = int(v5_all["week8_v5"].isna().sum())
nonresponders = int((v5_all["responder_30pct"] == False).sum())

st.title("XEAS随访数据及主要疗效看板")
st.markdown(f'<div class="small-note">疗效数据：{source_note} ｜ 随访数据：{followup_data_source} ｜ 当前疗效分析人群：{group}</div>', unsafe_allow_html=True)

project_tab, followup_tab, efficacy_tab, quality_tab, export_tab = st.tabs(["项目概览", "随访管理", "疗效分析", "数据质量", "结果导出"])
with efficacy_tab:
    efficacy_overview_tab, overall_tab, age_tab, individual_tab = st.tabs(["疗效概览", "总体趋势", "年龄亚组", "个体分析"])

with project_tab:
    recruitment = recruitment_from_schedule(qqdoc_schedule)
    disposition = disposition_from_schedule(qqdoc_schedule, followup_data_source)
    st.subheader("试验参与者进展")
    progress_cols = st.columns(5)
    progress_cols[0].metric("已筛选", recruitment["已筛选"])
    progress_cols[1].metric("已入组", recruitment["已入组"], help="包括当前已入组、已完成试验及已退出的试验参与者。")
    progress_cols[2].metric("筛选失败", recruitment["筛选失败"])
    progress_cols[3].metric("筛选中", recruitment["筛选中"])
    progress_cols[4].metric("已退出", recruitment["已退出"])
    st.caption(f"数据来源：{followup_data_source}。当前已完成试验 {recruitment['已完成试验']} 人；“已入组”口径包含当前已入组、已完成试验和退出者。")
    with st.expander("查看筛选失败及退出试验参与者名单"):
        st.dataframe(fmt_table(disposition), hide_index=True, use_container_width=True)

    st.subheader("各访视完成情况")
    visit_counts = visit_completion_from_schedule(qqdoc_schedule)
    visit_left, visit_right = st.columns([2.2, 1])
    with visit_left:
        visit_fig = px.bar(
            visit_counts, x="访视时间", y="完成访视人数", text="完成访视人数",
            color="完成访视人数", color_continuous_scale=[[0, "#a9c5db"], [1, "#245b85"]],
        )
        visit_fig.update_traces(textposition="outside")
        visit_fig.update_layout(height=350, showlegend=False, coloraxis_showscale=False, xaxis_title=None, yaxis_title="人数", yaxis_rangemode="tozero", margin=dict(t=25, b=35))
        st.plotly_chart(visit_fig, use_container_width=True)
    with visit_right:
        st.dataframe(visit_counts, hide_index=True, use_container_width=True, height=315)
        st.caption(f"数据来源：{followup_data_source}。按实际访视日期计数；V1及后续访视排除已确认的筛选失败者。")

with efficacy_overview_tab:
    st.subheader("主要疗效概览")
    efficacy_cols = st.columns(5)
    efficacy_cols[0].metric("YGTSS试验参与者", data["subject_id"].nunique())
    efficacy_cols[1].metric("V1/V5可评价", len(evaluable))
    efficacy_cols[2].metric("第8周30%应答率", "--" if pd.isna(response_rate) else f"{response_rate:.2f}%", f"{responders}人应答")
    efficacy_cols[3].metric("未达到30%", nonresponders)
    efficacy_cols[4].metric("缺少V5评分", missing_v5)
    st.markdown("#### 第8周YGTSS-TTS降低≥30%")
    summary30 = v5_response_summary(bundle)
    left, right = st.columns([1.4, 1])
    with left:
        fig = px.bar(summary30, x="分析组", y="应答比例（%）", text_auto=".2f", color="分析组", color_discrete_sequence=["#245b85", "#4b8b65", "#5a9bd4", "#e8752b"])
        fig.update_layout(showlegend=False, yaxis_range=[0,100], height=420)
        st.plotly_chart(fig, use_container_width=True)
    with right:
        st.dataframe(fmt_table(summary30), hide_index=True, use_container_width=True, height=390)
    if len(evaluable):
        st.info(f"第8周共{len(evaluable)}名试验参与者可评价，其中{responders}名YGTSS-TTS较基线降低至少30%，应答率为{response_rate:.2f}%。")

with followup_tab:
    st.subheader("去标识化试验参与者随访表")
    source_status = f"数据来源：{followup_data_source}"
    if qqdoc_synced_at:
        source_status += f"；最近同步于 {qqdoc_synced_at:%Y-%m-%d %H:%M:%S}，每5分钟自动更新"
    st.caption(f"{source_status}。不读取或显示姓名、门诊号和电话；理论访视日期以V1发药日期为起点计算，允许窗为±2天。")
    if qqdoc_error:
        st.warning(f"腾讯文档同步暂时不可用，当前已回退到EDC的SV数据：{qqdoc_error}")
    elif not qqdoc_ready:
        st.info("尚未配置腾讯文档密钥，当前暂用EDC的SV数据。")
    followup_table_tab, calendar_tab, visit_matrix_tab, visit_audit_tab = st.tabs(["随访总表", "随访日历", "访视完成矩阵", "访视人数核对"])
    with followup_table_tab:
        today = pd.Timestamp.today().normalize()
        schedule = qqdoc_schedule.copy()
        schedule["年龄组"] = schedule["年龄组"].fillna("年龄未分组")
        filter_col1, filter_col2, filter_col3, filter_col4 = st.columns([1.1, 1.8, 1.8, 1.5])
        subject_search = filter_col1.text_input("搜索试验参与者编号", placeholder="例如 S01014")
        available_statuses = [x for x in ["筛选中", "已入组", "完成试验", "退出", "筛选失败", "数据待补充"] if x in set(schedule["试验参与者状态"])]
        selected_statuses = filter_col2.multiselect("试验参与者状态", available_statuses, default=available_statuses)
        available_age_groups = [*AGE_GROUPS, "年龄未分组"]
        selected_age_groups = filter_col3.multiselect("年龄组", available_age_groups, default=available_age_groups)
        visit_filter = filter_col4.selectbox("访视完成情况", ["全部", "V1未完成", "V2未完成", "V3未完成", "V4未完成", "V5未完成", "V6未完成"])
        if subject_search.strip():
            schedule = schedule[schedule["试验参与者编号"].str.contains(subject_search.strip(), case=False, na=False)]
        schedule = schedule[schedule["试验参与者状态"].isin(selected_statuses) & schedule["年龄组"].isin(selected_age_groups)]
        if visit_filter != "全部":
            visit = visit_filter[:2]
            target_col = "V1发药日期" if visit == "V1" else f"{visit}实际日期"
            schedule = schedule[schedule[target_col].isna()]
        for visit in VISITS[1:]:
            schedule[f"{visit}访视状态"] = schedule.apply(
                lambda row, name=visit: visit_display_status(row, name, today), axis=1
            )
        screen_failed = schedule["试验参与者状态"].eq("筛选失败")
        schedule.loc[screen_failed, [f"{v}访视状态" for v in VISITS[1:]]] = ""
        schedule["是否存在超窗"] = schedule[[f"{v}访视状态" for v in VISITS[1:]]].eq("已完成（超窗）").any(axis=1)
        date_columns = [c for c in schedule.columns if "日期" in c or c.endswith("下限") or c.endswith("上限")]
        display_schedule = schedule.copy()
        for col in date_columns:
            display_schedule[col] = pd.to_datetime(display_schedule[col], errors="coerce").dt.strftime("%Y-%m-%d").fillna("")
        display_schedule = fmt_table(display_schedule)
        def followup_row_style(row: pd.Series) -> list[str]:
            if row["是否存在超窗"]:
                style = "background-color:#fde2e2;color:#8b1e1e"
            elif row["试验参与者状态"] == "筛选失败":
                style = "background-color:#fff2cc;color:#7f6000"
            elif row["试验参与者状态"] == "退出":
                style = "background-color:#d9ead3;color:#176b2c"
            elif row["试验参与者状态"] == "完成试验":
                style = "background-color:#d9eaf7;color:#174a6e"
            else:
                style = ""
            return [style] * len(row)
        styled_schedule = display_schedule.style.apply(followup_row_style, axis=1).hide(
            axis="columns", subset=["是否存在超窗"]
        )
        st.dataframe(styled_schedule, hide_index=True, use_container_width=True, height=590)
        enrolled_count = int(display_schedule["试验参与者状态"].isin(["已入组", "完成试验", "退出"]).sum())
        st.caption(
            f"本表经页内筛选后：筛选 {len(display_schedule)} 人，入组 {enrolled_count} 人，"
            f"筛败 {int(screen_failed.sum())} 人。黄色=筛选失败，绿色=退出，蓝色=完成试验，红色=存在超窗。"
        )
        with st.expander("查看访视时间计算规则"):
            st.markdown("V2：D14±2天　｜　V3：D28±2天　｜　V4：D42±2天　｜　V5：D56±2天　｜　V6：D84±2天")
    with calendar_tab:
        st.subheader("随访日历")
        st.caption("月历按理论访视日期排布；可切换日期矩阵和完整明细，查看窗口、实际日期及逾期/超窗情况。")
        today = pd.Timestamp.today().normalize()
        calendar = followup_calendar_from_schedule(qqdoc_schedule, today)
        calendar["年龄组"] = calendar["年龄组"].fillna("年龄未分组")
        calendar = calendar[~calendar["试验参与者状态"].isin(["退出", "筛选失败"])].copy()
        if calendar.empty:
            st.info("当前没有可展示的理论访视安排。")
        else:
            controls = st.columns([1.1, 1.3, 1.8, 2])
            months = sorted(calendar["理论日期"].dropna().dt.strftime("%Y-%m").unique().tolist())
            current_month = today.strftime("%Y-%m")
            month = controls[0].selectbox("选择月份", months, index=months.index(current_month) if current_month in months else 0,
                                          format_func=lambda value: f"{int(value[:4])}年{int(value[5:])}月")
            selected_visits = controls[1].multiselect("访视节点", VISITS[1:], default=VISITS[1:])
            person_options = [x for x in ["已入组", "完成试验", "数据待补充"] if x in set(calendar["试验参与者状态"])]
            selected_people = controls[2].multiselect("试验参与者状态", person_options, default=person_options)
            status_options = [x for x in ["待访", "访视窗内", "窗内完成", "窗外完成", "逾期未访"] if x in set(calendar["随访状态"])]
            selected_statuses = controls[3].multiselect("随访状态", status_options, default=status_options)
            filtered_calendar = calendar[
                calendar["访视"].isin(selected_visits)
                & calendar["试验参与者状态"].isin(selected_people)
                & calendar["随访状态"].isin(selected_statuses)
            ].copy()
            month_start = pd.Timestamp(f"{month}-01")
            month_end = month_start + pd.offsets.MonthEnd(1)
            month_schedule = filtered_calendar[filtered_calendar["理论日期"].between(month_start, month_end)].copy()
            view_mode = st.radio("展示方式", ["📅 月历概览", "📊 日期 × 访视", "📋 完整随访明细"], horizontal=True, label_visibility="collapsed")
            if view_mode == "📅 月历概览":
                metrics = st.columns(4)
                metrics[0].metric("当月应访", f"{len(month_schedule)} 次")
                metrics[1].metric("窗内完成", int(month_schedule["随访状态"].eq("窗内完成").sum()))
                metrics[2].metric("窗外完成", int(month_schedule["随访状态"].eq("窗外完成").sum()))
                metrics[3].metric("逾期未访", int(month_schedule["随访状态"].eq("逾期未访").sum()))
                if month_schedule.empty:
                    st.info(f"{month_start:%Y年%m月}在当前筛选条件下没有访视安排。")
                else:
                    render_month_calendar(month_schedule, month_start)
                    available_dates = sorted(month_schedule["理论日期"].dt.date.unique())
                    selected_date = st.selectbox("查看当日明细", available_dates, format_func=lambda value: value.strftime("%Y-%m-%d"))
                    day_detail = month_schedule[month_schedule["理论日期"].dt.date.eq(selected_date)].copy()
                    st.dataframe(fmt_table(day_detail), hide_index=True, use_container_width=True, height=min(420, 85 + len(day_detail) * 36))
            elif view_mode == "📊 日期 × 访视":
                if month_schedule.empty:
                    st.info(f"{month_start:%Y年%m月}在当前筛选条件下没有访视安排。")
                else:
                    matrix = pd.pivot_table(month_schedule, index="访视", columns=month_schedule["理论日期"].dt.strftime("%m-%d"),
                                            values="试验参与者编号", aggfunc="count", fill_value=0)
                    matrix["总计"] = matrix.sum(axis=1)
                    matrix.loc["所有访视总计"] = matrix.sum(axis=0)
                    st.caption("数字为当日理论应访次数；一名试验参与者的一个访视节点计 1 次。")
                    st.dataframe(matrix, use_container_width=True, height=min(560, 110 + len(matrix) * 36))
            else:
                search = st.text_input("搜索试验参与者编号", placeholder="例如 S01014", key="calendar_subject_search")
                detail = filtered_calendar.copy()
                if search.strip():
                    detail = detail[detail["试验参与者编号"].str.contains(search.strip(), case=False, na=False)]
                for col in ["理论日期", "允许窗起", "允许窗止", "实际日期"]:
                    detail[col] = pd.to_datetime(detail[col], errors="coerce").dt.strftime("%Y-%m-%d").fillna("")
                styled_detail = fmt_table(detail).style.apply(
                    lambda row: (["background-color:#fce8e6;color:#9b1c1c"] * len(row) if row["随访状态"] in ["逾期未访", "窗外完成"]
                                 else ["background-color:#fff2cc;color:#7f6000"] * len(row) if row["随访状态"] == "访视窗内"
                                 else ["background-color:#d9eaf7;color:#174a6e"] * len(row) if row["随访状态"] == "窗内完成"
                                 else [""] * len(row)), axis=1
                )
                st.dataframe(styled_detail, hide_index=True, use_container_width=True, height=590)
                st.caption(f"当前显示 {len(detail)} 条。红色=逾期或超窗，黄色=当前在访视窗，蓝色=窗内完成。")
    with visit_matrix_tab:
        st.subheader("腾讯随访表访视完成矩阵")
        st.caption("绿色表示腾讯随访表已有实际访视日期，黄色表示尚无记录；筛选失败者不在本矩阵中。该矩阵反映随访管理进度，不等同于EDC评分录入完整性。")
        comp = followup_completion_matrix(qqdoc_schedule)
        styled = comp.style.map(
            lambda x: "background-color:#d9ead3;color:#176b2c" if x is True
            else "background-color:#fff2cc;color:#9c6500" if x is False else "",
            subset=VISITS,
        )
        st.dataframe(styled, use_container_width=True, height=680, hide_index=True)
    with visit_audit_tab:
        audit = visit_count_audit_from_schedule(qqdoc_schedule)
        v1_audit = audit[audit["访视"].eq("V1")].iloc[0]
        audit_cols = st.columns(3)
        audit_cols[0].metric("V1-D1腾讯表完成数", int(v1_audit["腾讯表原始完成数"]))
        audit_cols[1].metric("排除筛败后V1人数", int(v1_audit["排除筛败后人数"]))
        audit_cols[2].metric("V1排除人数", int(v1_audit["排除人数"]))
        st.info(f"腾讯随访表当前V1-D1有{int(v1_audit['腾讯表原始完成数'])}人记录；排除已确认的筛选失败者后，管理口径为{int(v1_audit['排除筛败后人数'])}人。人数会随在线表格更新。")
        st.dataframe(audit, hide_index=True, use_container_width=True)

with overall_tab:
    sub1, sub2, sub3, sub4 = st.tabs(["TTS总体趋势", "总损害分趋势", "组成评分", "GSS应答"])
    with sub1:
        fig, summ = line_chart(data, "ygtss_tts", f"{group}：YGTSS-TTS各访视变化")
        st.plotly_chart(fig, use_container_width=True); st.dataframe(fmt_table(summ.rename(columns={"visit":"访视","week":"研究周","count":"例数","mean":"均值","std":"标准差","median":"中位数","min":"最小值","max":"最大值","se":"标准误"})), hide_index=True, use_container_width=True)
    with sub2:
        fig, summ = line_chart(data, "impairment_score", f"{group}：YGTSS总损害分各访视变化")
        st.plotly_chart(fig, use_container_width=True); st.dataframe(fmt_table(summ), hide_index=True, use_container_width=True)
    with sub3:
        means = data.groupby("visit")[["motor_tic_score", "vocal_tic_score", "ygtss_tts"]].mean().reindex(VISITS).reset_index()
        long_means = means.melt("visit", var_name="metric", value_name="mean")
        long_means["metric"] = long_means["metric"].map({"motor_tic_score":"运动抽动总分","vocal_tic_score":"发声抽动总分","ygtss_tts":"YGTSS-TTS"})
        fig = px.line(long_means, x="visit", y="mean", color="metric", markers=True, category_orders={"visit": VISITS}, title=f"{group}：运动、发声与TTS均值趋势")
        fig.update_layout(height=500, xaxis_title="访视", yaxis_title="均值（分）"); st.plotly_chart(fig, use_container_width=True)
    with sub4:
        gss = response_by_visit(data, "global_severity_score", [30,50])
        st.plotly_chart(response_line(gss, f"{group}：YGTSS总分应答比例"), use_container_width=True)
        st.dataframe(fmt_table(gss), hide_index=True, use_container_width=True)

with age_tab:
    dynamic_tab, standard_tab = st.tabs(["自定义阈值分析", "30%与50%固定对照"])
    with dynamic_tab:
        threshold = st.slider("YGTSS-TTS较基线降低阈值（%）", min_value=10, max_value=90, value=30, step=5, help="拖动后，下方图表和表格会同步更新。常用阈值为30%和50%。")
        v5_threshold, visit_threshold = age_response_results(bundle, threshold)
        st.subheader(f"第8周TTS降低≥{threshold}%：年龄组比较")
        chart_col, table_col = st.columns([1.25, 1])
        with chart_col:
            v5_fig = px.bar(
                v5_threshold, x="分析组", y="应答比例（%）", text_auto=".2f", color="分析组",
                color_discrete_sequence=["#245b85", "#4b8b65", "#5a9bd4", "#e8752b"],
            )
            v5_fig.update_layout(height=410, yaxis_range=[0, 100], showlegend=False, xaxis_title=None)
            st.plotly_chart(v5_fig, use_container_width=True)
        with table_col:
            st.dataframe(fmt_table(v5_threshold), hide_index=True, use_container_width=True, height=370)

        st.subheader(f"各年龄组TTS降低≥{threshold}%：各访视趋势")
        age_visit = visit_threshold[visit_threshold["分析组"].isin(AGE_GROUPS)].copy()
        trend_fig = px.line(
            age_visit, x="访视", y="应答比例（%）", color="分析组", markers=True,
            category_orders={"访视": VISITS[1:]},
            color_discrete_sequence=["#1570b8", "#76b7e5", "#ef3b35"],
        )
        trend_fig.update_layout(height=470, yaxis_range=[0, 100], yaxis_title="应答比例（%）", legend_title="年龄组")
        st.plotly_chart(trend_fig, use_container_width=True)
        st.dataframe(fmt_table(age_visit[["分析组", "访视", "研究周", "可评价人数", "应答人数", "应答比例（%）", "95%CI下限", "95%CI上限"]]), hide_index=True, use_container_width=True)

    with standard_tab:
        standard_summaries = []
        standard_visits = {}
        for standard_threshold in [30, 50]:
            summary_part, visit_part = age_response_results(bundle, standard_threshold)
            summary_part["降低阈值（%）"] = standard_threshold
            standard_summaries.append(summary_part)
            standard_visits[standard_threshold] = visit_part[visit_part["分析组"].isin(AGE_GROUPS)]
        standard_summary = pd.concat(standard_summaries, ignore_index=True)
        compare_fig = px.bar(
            standard_summary, x="分析组", y="应答比例（%）", color="降低阈值（%）", barmode="group", text_auto=".2f",
            color_discrete_map={30: "#5a9bd4", 50: "#e8752b"},
        )
        compare_fig.update_layout(height=440, yaxis_range=[0, 100], xaxis_title=None, legend_title="降低阈值")
        st.plotly_chart(compare_fig, use_container_width=True)
        table30_tab, table50_tab = st.tabs(["降低≥30%明细", "降低≥50%明细"])
        with table30_tab:
            st.dataframe(fmt_table(standard_visits[30]), hide_index=True, use_container_width=True)
        with table50_tab:
            st.dataframe(fmt_table(standard_visits[50]), hide_index=True, use_container_width=True)
    st.warning("A组样本量较小，年龄亚组结果仅作描述性解读。")

with individual_tab:
    st.caption("按年龄组展示全部试验参与者，每行5人；绿色表示已退出，红色表示V5可评价但TTS降低未达到30%，黄色表示缺少V5。")
    control1, control2 = st.columns([1, 1.4])
    status = control1.radio("显示人群", ["全部", "达到30%", "未达到30%", "缺少V5"], horizontal=True)
    chart_type = control2.radio("个体图类型", ["TTS及组成评分", "总损害分"], horizontal=True)
    group_tabs = st.tabs([f"{g.split('组')[0]}组" for g in AGE_GROUPS])
    for age_group, age_group_tab in zip(AGE_GROUPS, group_tabs):
        with age_group_tab:
            group_outcomes = bundle.v5_change[bundle.v5_change["age_group"].eq(age_group)].copy()
            if status == "达到30%":
                group_outcomes = group_outcomes[group_outcomes["responder_30pct"] == True]
            elif status == "未达到30%":
                group_outcomes = group_outcomes[group_outcomes["responder_30pct"] == False]
            elif status == "缺少V5":
                group_outcomes = group_outcomes[group_outcomes["week8_v5"].isna()]
            group_outcomes = group_outcomes.sort_values("subject_id")
            st.markdown(f"**{age_group}：{len(group_outcomes)}人**")
            if group_outcomes.empty:
                st.info("当前筛选条件下没有试验参与者。")
            for start in range(0, len(group_outcomes), 5):
                columns = st.columns(5)
                for column, (_, outcome) in zip(columns, group_outcomes.iloc[start:start + 5].iterrows()):
                    person = bundle.longitudinal[bundle.longitudinal["subject_id"].eq(outcome["subject_id"])]
                    with column:
                        st.plotly_chart(individual_chart(person, outcome, chart_type), use_container_width=True, config={"displayModeBar": False})
    ungrouped = bundle.v5_change[bundle.v5_change["age_group"].isna()]
    if not ungrouped.empty:
        st.caption(f"另有{len(ungrouped)}名试验参与者因年龄缺失或超出分组范围，未进入A/B/C个体图。")

with quality_tab:
    st.subheader("上传数据检查")
    st.dataframe(bundle.validation, hide_index=True, use_container_width=True)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("缺少V5", int(bundle.v5_change["week8_v5"].isna().sum()))
    m2.metric("V1和V5均缺失", int(((bundle.v5_change["baseline_v1"].isna()) & (bundle.v5_change["week8_v5"].isna())).sum()))
    m3.metric("DM年龄缺失/范围外（含筛败）", int(bundle.dm["age_group"].isna().sum()))
    m4.metric("疗效分析人群年龄未分组", int(bundle.v5_change["age_group"].isna().sum()))
    st.caption("DM口径包含全部已记录试验参与者，因此包括年龄缺失的筛选失败者S01053；疗效分析口径已排除筛败者。")
    st.subheader("缺少V5名单")
    st.dataframe(fmt_table(bundle.v5_change[bundle.v5_change["week8_v5"].isna()]),hide_index=True,use_container_width=True)
    st.subheader("可评价但未达到30%名单")
    st.dataframe(fmt_table(bundle.v5_change[bundle.v5_change["responder_30pct"]==False]),hide_index=True,use_container_width=True)

with export_tab:
    st.subheader("导出当前Python分析结果")
    output=BytesIO()
    with pd.ExcelWriter(output,engine="openpyxl") as writer:
        v5_response_summary(bundle).to_excel(writer,sheet_name="第8周30%应答",index=False)
        visit_summary(data,"ygtss_tts").to_excel(writer,sheet_name="TTS描述统计",index=False)
        response_by_visit(data,"ygtss_tts",[50]).to_excel(writer,sheet_name="TTS降低50%",index=False)
        response_by_visit(data,"global_severity_score",[30,50]).to_excel(writer,sheet_name="GSS降低30和50%",index=False)
        bundle.v5_change.to_excel(writer,sheet_name="V1V5个体明细",index=False)
        qqdoc_schedule.to_excel(writer,sheet_name="随访日期表",index=False)
        disposition.to_excel(writer,sheet_name="筛败及退出名单",index=False)
    st.download_button("下载当前分析Excel",output.getvalue(),file_name=f"YGTSS初步分析_{datetime.now():%Y%m%d}.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)
    st.download_button("下载清理后纵向数据CSV",bundle.longitudinal.to_csv(index=False).encode("utf-8-sig"),file_name="YGTSS清理后纵向数据.csv",mime="text/csv",use_container_width=True)
