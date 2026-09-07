import streamlit as st
import tempfile
import os
import ingest
import bot
import contract_prescreen

st.set_page_config(
    page_title="法小盾——面向对美出口卖方的跨境违约救济AI预审系统",
    page_icon="⚖️",
    layout="wide"
)

# CSS：输入框sticky贴底 + 合同报告，双重兜底取消加粗（strong / b标签全部强制普通字重）
st.markdown("""
<style>
div.block-container {
    padding-bottom: 20px;
}
/* 聊天输入框贴底，不脱离文档流，拖侧边栏不错位 */
div[data-testid="stChatInput"] {
    position: sticky !important;
    bottom: 0 !important;
    background-color: white;
    padding: 12px 16px;
    z-index: 999;
    box-shadow: 0 -1px 5px rgba(0,0,0,0.08);
    margin-top: 12px;
}
/* 合同报告字体控制 */
.contract-report-text {
    font-size: 14px !important;
    line-height: 1.65;
}
.contract-report-text h1 { font-size: 20px !important; }
.contract-report-text h2 { font-size: 17px !important; }
.contract-report-text h3 { font-size: 15px !important; }
.contract-report-text p {
    font-size: 14px !important;
    font-weight: 400 !important;
}
.contract-report-text strong,
.contract-report-text b {
    font-size: 14px !important;
    font-weight: 400 !important;
}
/* 全局兜底，所有markdown区域取消加粗视觉效果 */
div[data-testid="stMarkdown"] strong,
div[data-testid="stMarkdown"] b {
    font-weight: 400 !important;
}
</style>
""", unsafe_allow_html=True)

# 访问口令
_pw = os.environ.get("APP_PASSWORD", "")
if _pw and not st.session_state.get("_auth_ok"):
    st.title("法小盾")
    st.caption("面向对美出口卖方的跨境违约救济 AI 预审系统")
    st.caption("本站为参赛作品演示环境，请输入访问口令。")
    _typed = st.text_input("访问口令", type="password")
    if _typed:
        if _typed == _pw:
            st.session_state["_auth_ok"] = True
            st.rerun()
        else:
            st.error("口令不正确")
    st.stop()

# 初始化聊天记录：每条assistant消息保存完整info（法条、重写记录等），往回翻不丢失
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "欢迎使用法小盾。请描述你遇到的跨境交易纠纷，系统会依据知识库条文给出带出处的预审意见。",
            "scene_header": None,
            "provisions": None,
            "trace": None,
            "called_api": None
        }
    ]

# 侧边栏：知识库管理
with st.sidebar:
    st.header("知识库管理")
    st.markdown("上传法律文档，扩充系统可查询的法律知识库")
    uploaded_file = st.file_uploader("选择知识库文件", type=["txt", "docx"], help="支持txt、docx格式")
    if uploaded_file is not None:
        st.info("已选中文件：" + uploaded_file.name)
        if st.button("导入向量库", use_container_width=True, type="primary"):
            temp_file_path = None
            try:
                with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_f:
                    tmp_f.write(uploaded_file.getvalue())
                    temp_file_path = tmp_f.name
                with st.spinner("文档解析中，正在写入向量知识库..."):
                    chunk_count = ingest.ingest(source=temp_file_path, reset=False)
                st.success("导入完成！共生成 " + str(chunk_count) + " 条知识片段")
            except Exception as e:
                st.error("导入失败：" + str(e))
            finally:
                # 修复：无论成功失败都删除临时文件，不留垃圾
                if temp_file_path and os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
    st.divider()
    with st.expander("开发人员技术信息"):
        st.markdown("- 检索方案：Chroma初筛 + TF‑IDF精排")
        st.markdown("- 初始化命令：python ingest.py --source kb_raw.txt --reset")
    st.divider()
    st.markdown("提示：本工具仅作参考，不能替代执业律师的正式法律意见。")

# 页面标题
st.title("法小盾")
st.caption("面向对美出口卖方的跨境违约救济 AI 预审系统")
st.info("免责声明：系统输出仅为普法预审参考，不构成正式法律意见。涉及真实涉外案件，请务必咨询涉外执业律师。")

tab_chat, tab_contract = st.tabs(["法律问答", "合同风险预审"])

# ========== 法律问答 ==========
with tab_chat:
    user_input = st.chat_input("请输入你的跨境法律问题，例如：买家拖欠货款我该如何维权？")
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        try:
            with st.spinner("正在检索知识库，生成预审回答..."):
                info = bot.answer_detailed(user_input)
            st.session_state.messages.append({
                "role": "assistant",
                "content": info["answer"],
                "scene_header": info.get("scene_header"),
                "provisions": info.get("provisions"),
                "trace": info.get("trace"),
                "called_api": info.get("called_api")
            })
        except Exception as e:
            st.session_state.messages.append({
                "role": "assistant",
                "content": "抱歉，AI服务暂时不可用（可能是API额度用尽或网络中断），请稍后重试或联系管理员。",
                "scene_header": None,
                "provisions": None,
                "trace": None,
                "called_api": None
            })

    chat_container = st.container(height=500)
    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                if msg.get("scene_header"):
                    st.caption(msg["scene_header"])
                st.write(msg["content"])
                if msg["role"] == "assistant" and msg.get("provisions") is not None:
                    with st.expander("查看本次依据法条与重写记录"):
                        st.markdown("**AI参考的知识库法条：**")
                        if msg["provisions"]:
                            for p in msg["provisions"]:
                                st.markdown("**第 " + str(p["no"]) + " 条 · " + p["title"] + "**")
                                st.caption("法律依据：" + p["source"])
                            st.info("以上是本次AI仅可使用的参考材料，知识库其余内容本次不会被调用。")
                        else:
                            st.caption("本次没有命中任何知识库法条，系统直接拒答，未调用大模型")
                        st.divider()
                        st.markdown("**AI重写历史记录（输出防护校验）：**")
                        if not msg.get("called_api"):
                            st.caption("本次未调用大模型，无审核记录")
                        else:
                            blocked = [t for t in (msg.get("trace") or []) if not t["passed"]]
                            if not blocked:
                                st.caption("AI回答一次校验通过，没有被拦截重写")
                            else:
                                for t in blocked:
                                    if t["round"]:
                                        st.markdown("**第 " + str(t["round"]) + " 轮输出被程序打回，拦截原因：**")
                                    else:
                                        st.markdown("**多次校验失败，切换为安全拒答话术：**")
                                    for prob in t["problems"]:
                                        st.markdown("- " + prob)
                                    if t["raw"]:
                                        st.caption("AI原始输出（已拦截，未展示给用户）：")
                                        st.code(t["raw"], language=None)

# ========== 合同风险预审 ==========
with tab_contract:
    st.subheader("合同风险预审")
    st.markdown("粘贴外贸合同文本，系统自动扫描识别潜在法律风险点")
    contract_text = st.text_area("粘贴合同全部文本", height=320, placeholder="把你的合同复制粘贴到这里...")
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        submit_btn = st.button("开始风险审查", use_container_width=True, type="primary")
    if submit_btn:
        if not contract_text.strip():
            st.warning("请粘贴合同文本之后再点击审查")
        else:
            try:
                with st.spinner("正在扫描合同、比对法律知识库生成风险报告..."):
                    report_result = contract_prescreen.report(contract_text)
                st.divider()
                st.subheader("合同风险预审报告")
                st.markdown(f"""
<div class="contract-report-text">
{report_result}
</div>
""", unsafe_allow_html=True)
            except Exception as e:
                st.error("合同审查失败：" + str(e))
