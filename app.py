import streamlit as st

# 页面全局基础配置
st.set_page_config(
    page_title="面向对美出口卖方的跨境违约救济AI预审系统",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 页面大标题
st.title("面向对美出口卖方的跨境违约救济AI预审系统")
st.markdown("---")

# 左右分栏：左边输入占45%宽度，右边报告占55%宽度
col_left, col_right = st.columns([0.45, 0.55])

# =========左侧输入区域=========
with col_left:
    st.subheader("📝 输入区：合同文本 / 违约情况描述")
    user_input = st.text_area(
        "请粘贴合同内容，或者描述买方违约情况",
        placeholder="例：美国客户无理由拒收货物；请粘贴外贸合同文本……",
        height=320,
        key="user_input_box"
    )
    submit_button = st.button("提交预审", type="primary", key="submit_btn")

    if submit_button:
        st.info("✅已收到输入，等待后端接口接入（第一周UI占位）")

# =========右侧预审体检报告输出区=========
with col_right:
    st.subheader("📋预审体检报告【输出区】")
    st.info("【总评统计卡片 · 待后端接入】")
    st.markdown("---")

    st.markdown("#### 1.风险识别")
    st.text_area("", value="待接口返回数据填充……", disabled=True, height=110, key="res_risk")

    st.markdown("#### 2.救济权利")
    st.text_area("", value="待接口返回数据填充……", disabled=True, height=110, key="res_right")

    st.markdown("#### 3.法律依据")
    st.text_area("", value="待接口返回数据填充……", disabled=True, height=110, key="res_law")

    st.markdown("#### 4.合同审查")
    st.text_area("", value="待接口返回数据填充……", disabled=True, height=110, key="res_contract")

    # 法条出处折叠区
    with st.expander("📚引用法条来源（折叠查看）"):
        st.write("法条来源信息待接入……")

# =========页面最底部固定免责声明=========
st.markdown("---")
st.caption("""
⚠️免责声明：本系统输出内容仅供涉外贸易普法参考，**不构成正式法律意见**，不能替代执业涉外律师专业服务；
禁止用于诉讼立案、诉状撰写；遇到重大纠纷请聘请专业涉外律师。
""")
