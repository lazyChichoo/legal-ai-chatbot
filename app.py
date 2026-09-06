import streamlit as st
import tempfile
import os
import ingest
import bot
import contract_prescreen

# 页面配置
st.set_page_config(
    page_title="法小盾——面向对美出口卖方的跨境违约救济AI预审系统",
    page_icon="⚖️",
    layout="wide"
)

# ── 可选访问口令：环境变量 APP_PASSWORD 有值时才启用，本地默认不设、直接可用 ──
_pw = os.environ.get("APP_PASSWORD", "")
if _pw and not st.session_state.get("_auth_ok"):
    st.title("⚖️ 法小盾")
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

# 尝试导入聊天后端（容错，导入失败不崩溃页面）
chat_available = True

# 初始化会话状态，保存聊天记录
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content":"欢迎使用法小盾。请描述你遇到的跨境交易纠纷，系统会依据知识库条文给出带出处的预审意见。"}
    ]
# 侧边栏：知识库上传模块【你的核心功能，完整】
with st.sidebar:
    st.title("📚 知识库管理")
    st.markdown("支持上传txt / docx知识库文件，导入Chroma向量库")
    uploaded_file = st.file_uploader("上传知识库文件", type=["txt","docx"])
    if uploaded_file is not None:
        st.info(f"已选择文件：{uploaded_file.name}")
        if st.button("导入到向量库", use_container_width=True):
            try:
                with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_f:
                    tmp_f.write(uploaded_file.getvalue())
                    temp_file_path = tmp_f.name
                with st.spinner("正在解析文档，写入Chroma向量库..."):
                    chunk_count = ingest.ingest(
                        source=temp_file_path,
                        reset=False
                    )
                st.success(f"✅导入完成！生成 {chunk_count} 个知识切块。")
                os.unlink(temp_file_path)
            except Exception as e:
                st.error(f"❌导入失败：{str(e)}")
    st.divider()
    st.markdown("""
> 底层检索：Chroma初筛 + TF‑IDF精排
> 项目初始化命令：`python ingest.py --source kb_raw.txt --reset`
""")
# 页面主标题
st.title("⚖️ 法小盾")
st.caption("面向对美出口卖方的跨境违约救济 AI 预审系统")

# 主页面tab
tab_chat, tab_contract = st.tabs(["💬法律问答","📄合同风险预审"])
# 聊天页面
with tab_chat:
    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).write(msg["content"])
    user_input = st.chat_input("请输入你的跨境法律问题")
    if user_input:
        st.chat_message("user").write(user_input)
        st.session_state.messages.append({"role":"user","content":user_input})
        with st.chat_message("assistant"):
            if chat_available:
                with st.spinner("AI检索知识库生成回答..."):
                    info = bot.answer_detailed(user_input)
                    if info["scene_header"]:
                        st.caption(info["scene_header"])
                    resp = info["answer"]
                    st.write(resp)

                    # ========== 组长加分任务：法条来源 + 重写历史 折叠面板 ==========
                    with st.expander("🔍 查看本次依据法条与重写记录"):
                        st.markdown("**📑AI参考的知识库法条：**")
                        if info["provisions"]:
                            for p in info["provisions"]:
                                st.markdown("**第 %d 条 · %s**" % (p["no"], p["title"]))
                                st.caption("法律依据：" + p["source"])
                            st.info("以上是本次唯一喂给 AI 的材料，知识库里其余条文它看不到。")
                        else:
                            st.caption("本次没有命中任何法条，系统直接拒答，未调用 AI")

                        st.divider()
                        st.markdown("**✏️AI重写历史记录：**")
                        blocked = [t for t in info["trace"] if not t["passed"]]
                        if not info["called_api"]:
                            st.caption("本次未调用 AI，没有审核记录")
                        elif not blocked:
                            st.caption("AI 一次通过，程序没有拦截")
                        else:
                            for t in blocked:
                                if t["round"]:
                                    st.markdown("**第 %d 轮被程序打回，原因：**" % t["round"])
                                else:
                                    st.markdown("**两轮都没通过，改为输出拒答话术：**")
                                for prob in t["problems"]:
                                    st.markdown("- " + prob)
                                if t["raw"]:
                                    st.caption("AI 当时写的原话（已被拦下，没给用户看）：")
                                    st.code(t["raw"], language=None)
                    # ========== 加分代码结束 ==========
                st.session_state.messages.append({"role":"assistant","content":resp})
            else:
                st.info("聊天后端接口待确认，知识库上传功能可测试。")
# 合同预审tab
with tab_contract:
    st.subheader("合同风险预审")
    contract_text = st.text_area("粘贴合同文本", height=300)
    if st.button("开始风险审查", use_container_width=True):
        if not contract_text.strip():
            st.warning("请粘贴合同内容")
        else:
            report_result = contract_prescreen.report(contract_text)
            st.text(report_result)
