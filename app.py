import io
import importlib
import os
import uuid
import math
import zipfile
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

from src.config_loader import ConfigLoader
from src.controller import Controller
from src.models import InterviewSession, InterviewState
from src.report import ReportGenerator
from src.report_exporter import ReportExporter
from src.report_repository import ReportRepository
from src.session_persistence import SessionPersistence


st.set_page_config(page_title="校园消费生态智能访谈系统", page_icon="🎓", layout="wide")


@st.cache_resource
def init_components():
    return ConfigLoader(), SessionPersistence(), ReportGenerator(), ReportExporter(), ReportRepository()


def query_get(key: str, default: str = "") -> str:
    value = st.query_params.get(key, default)
    if isinstance(value, list):
        return value[0] if value else default
    return value


def update_query_params(mode: str, scenario: str | None = None, shop_name: str | None = None, session_id: str | None = None):
    for k in list(st.query_params.keys()):
        del st.query_params[k]
    st.query_params["mode"] = mode
    if scenario:
        st.query_params["scenario"] = scenario
    if shop_name:
        st.query_params["shop"] = shop_name
    if session_id:
        st.query_params["session"] = session_id


def build_interview_url(scenario: str, shop_name: str | None, mode: str = "interview") -> str:
    base_url = os.getenv("APP_BASE_URL", "http://localhost:8501")
    url = f"{base_url}?mode={mode}&scenario={scenario}"
    if shop_name:
        url += f"&shop={shop_name}"
    return url


def build_qr_png_bytes(content: str) -> bytes:
    qrcode = importlib.import_module("qrcode")
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(content)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def create_new_interview(config_loader, session_persistence, scenario: str, shop_name: str | None):
    new_session_id = str(uuid.uuid4())[:8]
    new_session = InterviewSession(session_id=new_session_id, scenario_type=scenario, shop_name=shop_name)
    session_persistence.save_session(new_session)

    st.session_state.session_id = new_session_id
    st.session_state.messages = []
    st.session_state.current_scenario = scenario
    st.session_state.current_shop_name = shop_name

    st.session_state.scenario_config = config_loader.load_scenario(scenario, shop_name=shop_name)
    st.session_state.controller = Controller(st.session_state.scenario_config)

    session = session_persistence.load_session(new_session_id)
    if not session:
        st.error("创建会话失败，请重试")
        return

    greeting = st.session_state.controller.get_next_question(session)
    if greeting:
        st.session_state.messages.append({"role": "assistant", "content": greeting})

    first_question = st.session_state.controller.get_next_question(session)
    if first_question:
        st.session_state.messages.append({"role": "assistant", "content": first_question})

    session.conversation_history = st.session_state.messages
    session_persistence.save_session(session)
    update_query_params("interview", scenario, shop_name)


def build_export_payload(record, export_format: str, report_exporter: ReportExporter) -> tuple[bytes, str, str]:
    """返回 (文件字节, 文件名, MIME 类型)，用于浏览器下载。"""
    safe_name = (record.display_name or record.report_id).strip() or record.report_id

    if export_format == "Markdown":
        return record.content_markdown.encode("utf-8"), f"{safe_name}.md", "text/markdown"
    if export_format == "PDF":
        return report_exporter.export_to_pdf_bytes(record.content_markdown), f"{safe_name}.pdf", "application/pdf"
    return report_exporter.export_to_word_bytes(record.content_markdown), f"{safe_name}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def build_batch_export_zip(records, export_format: str, report_exporter: ReportExporter) -> tuple[bytes, int]:
    """批量导出为单个 ZIP 压缩包，返回(zip_bytes, 成功条数)"""
    mem_zip = io.BytesIO()
    success = 0
    ext_map = {"Markdown": "md", "PDF": "pdf", "Word": "docx"}
    ext = ext_map.get(export_format, "txt")

    with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for record in records:
            file_bytes, _, _ = build_export_payload(record, export_format, report_exporter)
            filename = f"{record.display_name}.{ext}"
            zf.writestr(filename, file_bytes)
            success += 1

    mem_zip.seek(0)
    return mem_zip.getvalue(), success


def render_copy_link_button(link_text: str, key_suffix: str):
    safe_text = link_text.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
    components.html(
        f"""
        <div style="width:100%; height:30px; display:flex; align-items:center; justify-content:center;">
          <button id="copyBtn_{key_suffix}" style="
              width:100%;
              height:30px;
              border-radius:8px;
              border:1px solid rgba(49,51,63,0.2);
              background: rgb(240,242,246);
              color: rgb(49,51,63);
              font-size: 0.95rem;
              font-weight: 600;
              cursor: pointer;
              padding: 0 0.75rem;
              box-sizing: border-box;
          ">复制链接</button>
        </div>
        <script>
          const btn = document.getElementById("copyBtn_{key_suffix}");
          btn.addEventListener("mouseenter", () => btn.style.filter = "brightness(0.97)");
          btn.addEventListener("mouseleave", () => btn.style.filter = "none");
          btn.onclick = async () => {{
            try {{
              await navigator.clipboard.writeText(`{safe_text}`);
            }} catch (e) {{}}
          }};
        </script>
        """,
        height=42,  # 和左边输入框高度完全一致
    )


def render_owner_dashboard(config_loader, report_generator, report_exporter, report_repository):
    st.title("🏪 商家后台")
    st.caption("左侧：链接与筛选操作 | 右侧：报告条目列表/预览")

    if "preview_report_id" not in st.session_state:
        st.session_state.preview_report_id = None
    if "bulk_mode" not in st.session_state:
        st.session_state.bulk_mode = False
    if "bulk_selected_ids" not in st.session_state:
        st.session_state.bulk_selected_ids = []
    if "owner_page" not in st.session_state:
        st.session_state.owner_page = 1
    if "pending_delete_ids" not in st.session_state:
        st.session_state.pending_delete_ids = []
    if "show_batch_delete_confirm" not in st.session_state:
        st.session_state.show_batch_delete_confirm = False
    if "batch_zip_bytes" not in st.session_state:
        st.session_state.batch_zip_bytes = None
    if "batch_zip_name" not in st.session_state:
        st.session_state.batch_zip_name = "reports.zip"
    if "owner_type_filter" not in st.session_state:
        st.session_state.owner_type_filter = "全部"
    if "owner_name_keyword" not in st.session_state:
        st.session_state.owner_name_keyword = ""
    if "owner_export_format" not in st.session_state:
        st.session_state.owner_export_format = "Markdown"
    if "owner_left_page" not in st.session_state:
        st.session_state.owner_left_page = "link"
    if "owner_page_size" not in st.session_state:
        st.session_state.owner_page_size = 20
    if "owner_scenario_filter" not in st.session_state:
        st.session_state.owner_scenario_filter = "全部"
    if "owner_shop_filter" not in st.session_state:
        st.session_state.owner_shop_filter = "全部"
    if "owner_right_page" not in st.session_state:
        st.session_state.owner_right_page = "list"
    if "editing_report_id" not in st.session_state:
        st.session_state.editing_report_id = None
    if "owner_selected_report_id" not in st.session_state:
        st.session_state.owner_selected_report_id = None
    if "owner_selected_rename" not in st.session_state:
        st.session_state.owner_selected_rename = ""
    if "owner_select_all_filtered" not in st.session_state:
        st.session_state.owner_select_all_filtered = False

    scenarios = config_loader.get_available_scenarios()
    scenario_names = {
        "canteen": "🍚 食堂消费调研",
        "convenience_store": "🏪 便利店消费调研",
        "dry_cleaner": "👕 干洗店服务调研",
    }
    if not scenarios:
        st.error("未检测到场景配置")
        return

    all_reports = report_repository.list_reports()

    scenario_options = ["全部"] + sorted({r.scenario_type for r in all_reports})
    if st.session_state.owner_scenario_filter not in scenario_options:
        st.session_state.owner_scenario_filter = "全部"

    base_for_shop = all_reports
    if st.session_state.owner_scenario_filter != "全部":
        base_for_shop = [r for r in all_reports if r.scenario_type == st.session_state.owner_scenario_filter]
    shop_options = ["全部"] + sorted({(r.shop_name or "未指定") for r in base_for_shop})
    if st.session_state.owner_shop_filter not in shop_options:
        st.session_state.owner_shop_filter = "全部"

    filtered = all_reports
    if st.session_state.owner_type_filter == "普通报告":
        filtered = [r for r in filtered if r.report_type == "base"]
    elif st.session_state.owner_type_filter == "总结报告":
        filtered = [r for r in filtered if r.report_type == "summary"]

    if st.session_state.owner_scenario_filter != "全部":
        filtered = [r for r in filtered if r.scenario_type == st.session_state.owner_scenario_filter]
    if st.session_state.owner_shop_filter != "全部":
        filtered = [r for r in filtered if (r.shop_name or "未指定") == st.session_state.owner_shop_filter]

    if st.session_state.owner_name_keyword.strip():
        kw = st.session_state.owner_name_keyword.strip().lower()
        filtered = [r for r in filtered if kw in r.display_name.lower()]

    all_report_ids = {r.report_id for r in all_reports}
    if st.session_state.owner_selected_report_id and st.session_state.owner_selected_report_id not in all_report_ids:
        st.session_state.owner_selected_report_id = None
        st.session_state.editing_report_id = None

    selected_record = None
    if st.session_state.owner_selected_report_id:
        selected_record = report_repository.get(st.session_state.owner_selected_report_id)

    page_size = int(st.session_state.owner_page_size)
    if page_size <= 0:
        page_size = max(1, len(filtered))
    total_pages = max(1, math.ceil(len(filtered) / page_size))
    if st.session_state.owner_page > total_pages:
        st.session_state.owner_page = total_pages
    if st.session_state.owner_page < 1:
        st.session_state.owner_page = 1

    start = (int(st.session_state.owner_page) - 1) * page_size
    page_reports = filtered[start:start + page_size]
    current_page_ids = [r.report_id for r in page_reports]

    def _on_single_row_toggle(rid: str, display_name: str):
        key = f"row_chk_single_{rid}"
        checked = bool(st.session_state.get(key, False))
        if checked:
            st.session_state.owner_selected_report_id = rid
            st.session_state.owner_selected_rename = display_name
            if st.session_state.editing_report_id and st.session_state.editing_report_id != rid:
                st.session_state.editing_report_id = None
            for oid in current_page_ids:
                if oid != rid:
                    st.session_state[f"row_chk_single_{oid}"] = False
        else:
            if st.session_state.owner_selected_report_id == rid:
                st.session_state.owner_selected_report_id = None
                st.session_state.editing_report_id = None

    def _on_bulk_row_toggle(rid: str):
        key = f"row_chk_bulk_{rid}"
        checked = bool(st.session_state.get(key, False))
        selected = list(st.session_state.bulk_selected_ids)
        if checked and rid not in selected:
            selected.append(rid)
        if (not checked) and rid in selected:
            selected.remove(rid)
        st.session_state.bulk_selected_ids = selected

    def _on_toggle_select_all(filtered_ids: list[str]):
        checked = bool(st.session_state.get("owner_select_all_filtered", False))
        selected = set(st.session_state.bulk_selected_ids)
        fset = set(filtered_ids)
        if checked:
            selected |= fset
        else:
            selected -= fset
        st.session_state.bulk_selected_ids = list(selected)

    st.markdown(
        """
        <style>
        .main .block-container {
            min-width: 1320px;
            overflow-x: auto;
        }
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
            min-height: 78vh;
        }
        div[data-testid="stButton"] > button,
        div[data-testid="stDownloadButton"] > button {
            white-space: nowrap !important;
            min-width: 64px;
        }
        div[data-testid="stSelectbox"],
        div[data-testid="stTextInput"],
        div[data-testid="stNumberInput"],
        div[data-testid="stButton"],
        div[data-testid="stDownloadButton"] {
            min-width: 96px;
        }
        .owner-nowrap {
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .owner-head-center {
            text-align: center;
        }
        .owner-cell-center {
            text-align: center;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    left_col, right_col = st.columns([1, 1], gap="large")

    with left_col:
        with st.container(height=760, border=True):
            if st.session_state.owner_left_page == "link":
                head_l, head_r = st.columns([4, 1])
                head_l.subheader("生成店铺专属访谈链接")
                if head_r.button("列表操作", use_container_width=True):
                    st.session_state.owner_left_page = "ops"
                    st.rerun()

                c1, c2 = st.columns(2)
                selected_scenario = c1.selectbox("访谈场景", scenarios, format_func=lambda x: scenario_names.get(x, x), key="owner_scenario")
                shops = config_loader.get_shop_options(selected_scenario)
                selected_shop = c2.selectbox("店铺", shops if shops else ["默认店铺"], key="owner_shop")

                link = build_interview_url(selected_scenario, selected_shop, mode="interview")
                st.markdown("分享链接")
                link_col, btn_col = st.columns([8, 2])
                link_col.text_input("分享链接", value=link, key="share_link_display", label_visibility="collapsed")
                with btn_col:
                    render_copy_link_button(link, "owner_link")

                qr_bytes = build_qr_png_bytes(link)
                st.image(qr_bytes, caption="商家可将该二维码投放到海报/社媒/社群")
                st.download_button("下载二维码", data=qr_bytes, file_name=f"qr_{selected_scenario}_{selected_shop}.png", mime="image/png")
            else:
                head_l, head_r = st.columns([4, 1])
                head_l.subheader("报告筛选与批量操作")
                if head_r.button("生成链接", use_container_width=True):
                    st.session_state.owner_left_page = "link"
                    st.rerun()

                f1, f2, f3 = st.columns(3)
                f1.selectbox("报告类型", ["全部", "普通报告", "总结报告"], key="owner_type_filter")
                f2.selectbox("场景", scenario_options, key="owner_scenario_filter")
                f3.selectbox("店铺", shop_options, key="owner_shop_filter")

                s1, s2 = st.columns(2)
                s1.text_input("按名称搜索", placeholder="例如：b#0cb7f7b7", key="owner_name_keyword")
                s2.number_input("单页条目数量", min_value=0, step=1, key="owner_page_size")

                st.caption(f"当前匹配 {len(filtered)} 条")

                p1, p2, p3 = st.columns([1, 2, 1])
                if p1.button("上一页", use_container_width=True, disabled=st.session_state.owner_page <= 1):
                    st.session_state.owner_page -= 1
                    st.rerun()
                p2.markdown(
                    f"<div style='text-align:center;padding-top:6px;'>第 {st.session_state.owner_page}/{total_pages} 页</div>",
                    unsafe_allow_html=True,
                )
                if p3.button("下一页", use_container_width=True, disabled=st.session_state.owner_page >= total_pages):
                    st.session_state.owner_page += 1
                    st.rerun()

                st.divider()

                st.selectbox("导出格式", ["Markdown", "PDF", "Word"], key="owner_export_format")

                mode_btn_text = "退出批量选择" if st.session_state.bulk_mode else "批量选择"
                st.caption(f"已选中 {len(st.session_state.bulk_selected_ids)} 条")
                if st.button(mode_btn_text, use_container_width=True):
                    st.session_state.bulk_mode = not st.session_state.bulk_mode
                    if not st.session_state.bulk_mode:
                        st.session_state.bulk_selected_ids = []
                    st.rerun()

                filtered_ids = [r.report_id for r in filtered]
                if st.session_state.bulk_mode:
                    all_filtered_selected = (len(filtered_ids) > 0 and all(rid in st.session_state.bulk_selected_ids for rid in filtered_ids))
                    st.session_state.owner_select_all_filtered = all_filtered_selected
                    st.checkbox(
                        "全选当前筛选结果",
                        key="owner_select_all_filtered",
                        on_change=_on_toggle_select_all,
                        args=(filtered_ids,),
                    )

                selected_ids = st.session_state.bulk_selected_ids

                b1, b2, b3 = st.columns(3)
                with b1:
                    can_bulk_export = st.session_state.bulk_mode and bool(selected_ids)
                    if can_bulk_export:
                        try:
                            selected_records = [report_repository.get(rid) for rid in selected_ids]
                            selected_records = [r for r in selected_records if r]
                            zip_bytes, _ = build_batch_export_zip(selected_records, st.session_state.owner_export_format, report_exporter)
                            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                            st.download_button(
                                "批量导出",
                                data=zip_bytes,
                                file_name=f"reports_{ts}.zip",
                                mime="application/zip",
                                use_container_width=True,
                            )
                        except ModuleNotFoundError as e:
                            st.error(str(e))
                    else:
                        st.button("批量导出", use_container_width=True, disabled=True)

                with b2:
                    if st.button("批量删除", use_container_width=True, disabled=(not st.session_state.bulk_mode or not selected_ids)):
                        st.session_state.pending_delete_ids = list(selected_ids)
                        st.session_state.show_batch_delete_confirm = True

                with b3:
                    if st.button("AI生成总结报告", use_container_width=True, disabled=(not st.session_state.bulk_mode or not selected_ids)):
                        selected_records = [report_repository.get(rid) for rid in selected_ids]
                        selected_records = [x for x in selected_records if x]
                        if selected_records:
                            merged_content = [r.content_markdown for r in selected_records]
                            summary_text = report_generator.generate_summary_report(merged_content)
                            summary_record = report_repository.create_summary_report(
                                scenario_type=selected_records[0].scenario_type,
                                shop_name=selected_records[0].shop_name,
                                source_report_ids=[r.report_id for r in selected_records],
                                content_markdown=summary_text,
                            )
                            st.success(f"总结报告已生成：{summary_record.display_name}")
                            st.rerun()

                if st.session_state.show_batch_delete_confirm:
                    st.warning(f"即将删除 {len(st.session_state.pending_delete_ids)} 条记录，此操作不可恢复。")
                    x1, x2 = st.columns(2)
                    if x1.button("确认删除", key="confirm_bulk_delete_inline", use_container_width=True):
                        count = report_repository.delete_many(st.session_state.pending_delete_ids)
                        st.session_state.bulk_selected_ids = [
                            rid for rid in st.session_state.bulk_selected_ids if rid not in st.session_state.pending_delete_ids
                        ]
                        st.session_state.pending_delete_ids = []
                        st.session_state.show_batch_delete_confirm = False
                        st.success(f"已删除 {count} 条")
                        st.rerun()
                    if x2.button("取消", key="cancel_bulk_delete_inline", use_container_width=True):
                        st.session_state.pending_delete_ids = []
                        st.session_state.show_batch_delete_confirm = False
                        st.rerun()

    with right_col:
        with st.container(height=760, border=True):
            if st.session_state.owner_right_page == "preview" and st.session_state.preview_report_id:
                report = report_repository.get(st.session_state.preview_report_id)
                if not report:
                    st.session_state.owner_right_page = "list"
                    st.session_state.preview_report_id = None
                    st.rerun()

                top_l, top_r = st.columns([4, 1])
                top_l.subheader("报告预览")
                if top_r.button("返回列表", use_container_width=True):
                    st.session_state.owner_right_page = "list"
                    st.rerun()

                st.markdown(f"### {report.display_name}")
                st.caption(
                    f"类型：{'普通报告' if report.report_type == 'base' else '总结报告'} ｜ 场景：{report.scenario_type} ｜ 店铺：{report.shop_name or '未指定'}"
                )

                with st.container(height=530, border=True):
                    st.markdown(report.content_markdown)
            else:
                top_l, top_r = st.columns([3, 2])
                top_l.subheader("报告条目列表")
                if selected_record:
                    top_l.caption(f"当前选中：{selected_record.display_name}")
                else:
                    top_l.caption("当前选中：无")

                with top_r:
                    op_r1_c1, op_r1_c2 = st.columns(2)
                    rename_text = "确认" if (selected_record and st.session_state.editing_report_id == selected_record.report_id) else "改名"
                    if op_r1_c1.button(rename_text, key="selected_rename_btn", use_container_width=True, disabled=(selected_record is None)):
                        if selected_record and st.session_state.editing_report_id == selected_record.report_id:
                            if report_repository.rename(selected_record.report_id, st.session_state.owner_selected_rename, max_len=40):
                                st.session_state.editing_report_id = None
                                st.rerun()
                            else:
                                st.error("名称无效")
                        elif selected_record:
                            st.session_state.editing_report_id = selected_record.report_id
                            st.session_state.owner_selected_rename = selected_record.display_name
                            st.rerun()

                    if op_r1_c2.button("预览", key="selected_preview_btn", use_container_width=True, disabled=(selected_record is None)):
                        st.session_state.preview_report_id = selected_record.report_id if selected_record else None
                        st.session_state.owner_right_page = "preview"
                        st.rerun()

                    op_r2_c1, op_r2_c2 = st.columns(2)
                    if selected_record:
                        try:
                            file_bytes, file_name, mime = build_export_payload(
                                selected_record,
                                st.session_state.owner_export_format,
                                report_exporter,
                            )
                            op_r2_c1.download_button(
                                "导出",
                                data=file_bytes,
                                file_name=file_name,
                                mime=mime,
                                key=f"selected_dl_{selected_record.report_id}_{st.session_state.owner_export_format}",
                                use_container_width=True,
                            )
                        except ModuleNotFoundError as e:
                            op_r2_c1.error(str(e))
                    else:
                        op_r2_c1.button("导出", key="selected_dl_disabled", disabled=True, use_container_width=True)

                    if op_r2_c2.button("删除", key="selected_delete_btn", use_container_width=True, disabled=(selected_record is None)):
                        if selected_record and report_repository.delete(selected_record.report_id):
                            if st.session_state.preview_report_id == selected_record.report_id:
                                st.session_state.preview_report_id = None
                            if selected_record.report_id in st.session_state.bulk_selected_ids:
                                st.session_state.bulk_selected_ids.remove(selected_record.report_id)
                            st.session_state.owner_selected_report_id = None
                            st.session_state.editing_report_id = None
                            st.rerun()

                h0, h1, h2, h3, h4 = st.columns([0.7, 3, 1, 1, 1])
                h0.markdown("<div class='owner-head-center'><b>勾选</b></div>", unsafe_allow_html=True)
                h1.markdown("<div class='owner-head-center'><b>标题</b></div>", unsafe_allow_html=True)
                h2.markdown("<div class='owner-head-center'><b>类型</b></div>", unsafe_allow_html=True)
                h3.markdown("<div class='owner-head-center'><b>场景</b></div>", unsafe_allow_html=True)
                h4.markdown("<div class='owner-head-center'><b>店铺</b></div>", unsafe_allow_html=True)

                with st.container(height=570, border=True):
                    for record in page_reports:
                        r0, r1, r2, r3, r4 = st.columns([0.7, 3, 1, 1, 1])
                        is_selected = st.session_state.owner_selected_report_id == record.report_id
                        if st.session_state.bulk_mode:
                            row_chk_key = f"row_chk_bulk_{record.report_id}"
                            st.session_state[row_chk_key] = record.report_id in st.session_state.bulk_selected_ids
                        else:
                            row_chk_key = f"row_chk_single_{record.report_id}"
                            st.session_state[row_chk_key] = is_selected

                        r0.checkbox(
                            "选择该条目",
                            key=row_chk_key,
                            label_visibility="collapsed",
                            help="未开启批量模式时用于单选；开启后用于批量选择",
                            on_change=_on_bulk_row_toggle if st.session_state.bulk_mode else _on_single_row_toggle,
                            args=(record.report_id,) if st.session_state.bulk_mode else (record.report_id, record.display_name),
                        )

                        is_editing = selected_record and (st.session_state.editing_report_id == record.report_id)
                        if is_editing:
                            if st.session_state.owner_selected_rename != record.display_name and not st.session_state.owner_selected_rename.strip():
                                st.session_state.owner_selected_rename = record.display_name
                            r1.text_input("标题", key="owner_selected_rename", max_chars=40, label_visibility="collapsed")
                        else:
                            r1.markdown(f"<div class='owner-nowrap owner-cell-center'>{record.display_name}</div>", unsafe_allow_html=True)

                        r2.markdown(f"<div class='owner-nowrap owner-cell-center'>{'普通报告' if record.report_type == 'base' else '总结报告'}</div>", unsafe_allow_html=True)
                        r3.markdown(f"<div class='owner-nowrap owner-cell-center'>{record.scenario_type}</div>", unsafe_allow_html=True)
                        r4.markdown(f"<div class='owner-nowrap owner-cell-center'>{record.shop_name or '未指定'}</div>", unsafe_allow_html=True)

                        st.markdown("<hr style='margin: 0.2rem 0;'>", unsafe_allow_html=True)


def render_student_interview(config_loader, session_persistence, report_generator, report_repository):
    scenario = query_get("scenario", "")
    shop = query_get("shop", "")

    scenarios = config_loader.get_available_scenarios()
    if not scenario or scenario not in scenarios:
        st.title("🎓 校园消费生态访谈")
        st.error("链接无效：缺少合法场景参数。请使用商家提供的专属链接。")
        st.stop()

    if "session_id" not in st.session_state:
        st.session_state.session_id = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "controller" not in st.session_state:
        st.session_state.controller = None
    if "scenario_config" not in st.session_state:
        st.session_state.scenario_config = None
    if "student_link_signature" not in st.session_state:
        st.session_state.student_link_signature = None
    if "ai_processing" not in st.session_state:
        st.session_state.ai_processing = False
    if "pending_user_input" not in st.session_state:
        st.session_state.pending_user_input = None

    link_signature = (scenario, shop)
    if st.session_state.student_link_signature != link_signature:
        st.session_state.session_id = None
        st.session_state.messages = []
        st.session_state.controller = None
        st.session_state.scenario_config = None
        st.session_state.student_link_signature = link_signature
        st.session_state.ai_processing = False
        st.session_state.pending_user_input = None

    if not st.session_state.session_id:
        create_new_interview(config_loader, session_persistence, scenario, shop or None)

    st.title("🎓 校园消费生态访谈")
    st.caption(f"场景：{scenario} | 店铺：{shop or '该商铺'}")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if st.session_state.ai_processing and st.session_state.pending_user_input:
        with st.chat_message("assistant"):
            with st.spinner("AI 正在思考，请稍候..."):
                prompt = st.session_state.pending_user_input
                session = session_persistence.load_session(st.session_state.session_id)
                if session and st.session_state.controller:
                    if isinstance(session.state, str):
                        session.state = InterviewState(session.state)

                    result = st.session_state.controller.process_response(session, prompt)
                    if result.get("next_question"):
                        st.markdown(result["next_question"])
                        st.session_state.messages.append({"role": "assistant", "content": result["next_question"]})

                    session.conversation_history = st.session_state.messages
                    if session.is_complete or (
                        hasattr(session, "state") and session.state and hasattr(session.state, "value") and session.state.value == "completed"
                    ):
                        session.end_time = datetime.now()
                        session.is_complete = True
                        st.success("✅ 感谢你的反馈，访谈已完成")

                        if not session.report_id:
                            config = config_loader.load_scenario(session.scenario_type, shop_name=session.shop_name)
                            report_md = report_generator.generate_report(session, config)
                            record = report_repository.create_base_report(
                                scenario_type=session.scenario_type,
                                shop_name=session.shop_name,
                                session_id=session.session_id,
                                content_markdown=report_md,
                            )
                            session.report_id = record.report_id

                    session_persistence.save_session(session)
                else:
                    st.error("会话初始化失败，请重新打开商家链接")

        st.session_state.pending_user_input = None
        st.session_state.ai_processing = False
        st.rerun()

    prompt = st.chat_input("请输入你的回答...", disabled=st.session_state.ai_processing)
    if prompt and (not st.session_state.ai_processing):
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.pending_user_input = prompt
        st.session_state.ai_processing = True
        st.rerun()


config_loader, session_persistence, report_generator, report_exporter, report_repository = init_components()

if "last_session_cleanup_ts" not in st.session_state:
    st.session_state.last_session_cleanup_ts = 0.0
now_ts = datetime.now().timestamp()
if now_ts - st.session_state.last_session_cleanup_ts > 1800:
    if hasattr(session_persistence, "cleanup_incomplete_sessions"):
        session_persistence.cleanup_incomplete_sessions(max_age_hours=24)
    st.session_state.last_session_cleanup_ts = now_ts

if "session_id" not in st.session_state:
    st.session_state.session_id = None
mode = query_get("mode", "owner")
if mode == "owner":
    update_query_params("owner")
    render_owner_dashboard(config_loader, report_generator, report_exporter, report_repository)
else:
    render_student_interview(config_loader, session_persistence, report_generator, report_repository)
