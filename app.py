import streamlit as st
import tempfile
import os
import ingest

# 页面配置
st.set_page_config(
    page_title="中美跨境法律AI助手",
    page_icon="⚖️",
    layout="wide"
)

# 尝试导入聊天后端（容错，导入失败不崩溃页面）
chat_available = False
chat_func = None
try:
    from chat import chat
    chat_available = True
except ImportError:
    pass

# 初始化会话状态，保存聊天记录
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content":"欢迎使用中美跨境法律AI助手。侧边栏可以上传扩充知识库。"}
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
                    resp = chat(user_input)
                    st.write(resp)
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
            st.info("合同预审后端待对接完成")
