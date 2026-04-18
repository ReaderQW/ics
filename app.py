# app.py - Sprint 2 增强版（修复版）
import streamlit as st
from datetime import datetime
import uuid
from src.config_loader import ConfigLoader
from src.controller import Controller
from src.session_persistence import SessionPersistence
from src.report import ReportGenerator
from src.report_exporter import ReportExporter
from src.models import InterviewSession, InterviewState

# 页面配置
st.set_page_config(
    page_title="校园消费生态智能访谈系统",
    page_icon="🎓",
    layout="wide"
)

# 初始化组件
@st.cache_resource
def init_components():
    config_loader = ConfigLoader()
    session_persistence = SessionPersistence()
    report_generator = ReportGenerator()
    report_exporter = ReportExporter()
    return config_loader, session_persistence, report_generator, report_exporter

config_loader, session_persistence, report_generator, report_exporter = init_components()

# 初始化session state
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "controller" not in st.session_state:
    st.session_state.controller = None
if "scenario_config" not in st.session_state:
    st.session_state.scenario_config = None

# 标题
st.title("🎓 校园消费生态智能访谈系统")
st.caption("Sprint 2 | 智能追问 | 多格式报告导出 | 会话恢复")

# 侧边栏
with st.sidebar:
    st.header("⚙️ 设置")
    
    # 场景选择
    scenarios = config_loader.get_available_scenarios()
    scenario_names = {
        "canteen": "🍚 食堂消费调研",
        "convenience_store": "🏪 便利店消费调研",
        "dry_cleaner": "👕 干洗店服务调研"
    }
    
    selected_scenario = st.selectbox(
        "选择访谈场景",
        scenarios,
        format_func=lambda x: scenario_names.get(x, x)
    )
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 新访谈", use_container_width=True):
            # 创建新会话 - 手动生成session_id
            new_session_id = str(uuid.uuid4())[:8]
            new_session = InterviewSession(
                session_id=new_session_id,
                scenario_type=selected_scenario
            )
            # 保存会话
            session_persistence.save_session(new_session)
            
            # 更新session state
            st.session_state.session_id = new_session_id
            st.session_state.messages = []
            
            # 加载场景配置
            st.session_state.scenario_config = config_loader.load_scenario(selected_scenario)
            st.session_state.controller = Controller(st.session_state.scenario_config)
            
            # 重新加载会话（确保数据一致）
            session = session_persistence.load_session(new_session_id)
            
            if session:
                # 确保state是枚举类型
                if isinstance(session.state, str):
                    session.state = InterviewState(session.state)
                
                # 获取开场白
                greeting = st.session_state.controller.get_next_question(session)
                if greeting:
                    st.session_state.messages.append({"role": "assistant", "content": greeting})
                
                # 保存更新后的会话
                session_persistence.save_session(session)
            else:
                st.error("创建会话失败，请重试")
            
            st.rerun()
    
    with col2:
        # 恢复历史会话
        sessions = session_persistence.get_all_sessions()
        if sessions:
            selected_session_id = st.selectbox(
                "恢复历史会话",
                [s['session_id'] for s in sessions],
                format_func=lambda x: f"{x} - {'完成' if next((s for s in sessions if s['session_id']==x), {}).get('is_complete') else '进行中'}"
            )
            if st.button("📂 恢复会话", use_container_width=True):
                session = session_persistence.load_session(selected_session_id)
                if session:
                    # 确保state是枚举类型
                    if isinstance(session.state, str):
                        session.state = InterviewState(session.state)
                    
                    st.session_state.session_id = session.session_id
                    st.session_state.messages = session.conversation_history
                    st.session_state.scenario_config = config_loader.load_scenario(session.scenario_type)
                    st.session_state.controller = Controller(st.session_state.scenario_config)
                    st.rerun()
                else:
                    st.error("无法加载会话")
    
    st.divider()
    
    # 报告导出
    st.header("📄 报告导出")
    if st.session_state.session_id:
        session = session_persistence.load_session(st.session_state.session_id)
        if session and session.is_complete:
            export_format = st.radio("选择格式", ["Markdown", "PDF", "Word"])
            if st.button("📥 导出报告", use_container_width=True):
                config = config_loader.load_scenario(session.scenario_type)
                report = report_generator.generate_report(session, config)
                
                if export_format == "Markdown":
                    # 确保有export_to_markdown方法，如果没有则直接保存
                    if hasattr(report_exporter, 'export_to_markdown'):
                        filename = report_exporter.export_to_markdown(report, session.session_id)
                    else:
                        # 备用方案：直接保存为md文件
                        import os
                        os.makedirs("reports", exist_ok=True)
                        filename = f"reports/report_{session.session_id}.md"
                        with open(filename, 'w', encoding='utf-8') as f:
                            f.write(report)
                    
                    with open(filename, 'r', encoding='utf-8') as f:
                        st.download_button("下载", f.read(), file_name=filename.split('/')[-1])
                elif export_format == "PDF":
                    filename = report_exporter.export_to_pdf(report, session.session_id)
                    with open(filename, 'rb') as f:
                        st.download_button("下载 PDF", f.read(), file_name=filename.split('/')[-1])
                else:
                    filename = report_exporter.export_to_word(report, session.session_id)
                    with open(filename, 'rb') as f:
                        st.download_button("下载 Word", f.read(), file_name=filename.split('/')[-1])
                st.success(f"报告已生成: {filename}")

# 主界面
st.header("💬 访谈对话")

# 显示历史消息
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 输入框
if st.session_state.session_id is not None:
    if prompt := st.chat_input("请输入你的回答..."):
        # 显示用户消息
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # 获取会话和控制器
        session = session_persistence.load_session(st.session_state.session_id)
        
        if session and st.session_state.controller:
            # 确保state是枚举类型
            if isinstance(session.state, str):
                session.state = InterviewState(session.state)
            
            # 处理响应
            result = st.session_state.controller.process_response(session, prompt)
            
            # 显示助手回复
            if result.get("next_question"):
                with st.chat_message("assistant"):
                    st.markdown(result["next_question"])
                st.session_state.messages.append({"role": "assistant", "content": result["next_question"]})
            
            # 更新会话
            session.conversation_history = st.session_state.messages
            
            # 检查是否完成
            if session.is_complete or (hasattr(session, 'state') and session.state and hasattr(session.state, 'value') and session.state.value == "completed"):
                session.end_time = datetime.now()
                session.is_complete = True
                st.success("✅ 访谈完成！可在左侧导出报告")
            
            # 保存会话
            session_persistence.save_session(session)
        else:
            st.error("会话或控制器未正确初始化，请重新开始访谈")
        
        st.rerun()
else:
    st.info("👈 请选择场景并开始新访谈，或恢复历史会话")

# 页脚
st.divider()
st.caption("Sprint 2 | 校园消费生态智能访谈系统 | 支持多格式报告导出")