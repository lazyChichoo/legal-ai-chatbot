import streamlit as st

st.set_page_config(page_title="跨境违约救济AI预审系统", layout="wide")

st.title("面向对美出口卖方的跨境违约救济AI预审系统")
st.divider()

# 分左右两栏
col_left, col_right = st.columns([1,1])

with col_left:
    st.subheader("📝输入区：合同文本 / 违约情况描述")
    contract_text = st.text_area(
        "请粘贴合同内容，或者描述买方违约情况",
        placeholder="例：美国客户无理由拒收货物；请粘贴外贸合同文本……",
        height=340
    )
    submit_btn = st.button("提交预审", type="primary")


with col_right:
    st.subheader("📋预审体检报告【输出区】")

    # 风险规则，后续法学同学给内容直接替换这里
    risk_rules = [
        {"name":"违约救济条款","keyword":["remedy","救济","违约救济","转售","停运权","留置权"],"level":"高危","tip":"缺失救济条款，发生买方拒收拖欠时维权手段受限"},
        {"name":"违约金约定条款","keyword":["liquidated damages","违约金"],"level":"中危","tip":"缺少违约金约定，损害赔偿计算难度上升"},
        {"name":"货物检验期条款","keyword":["inspection","检验期","检验时间"],"level":"中危","tip":"无检验期约定，买方极易以质量理由恶意拒付货款"},
        {"name":"拒收处理条款","keyword":["rejection","拒收"],"level":"低危","tip":"缺少买方拒收后的处置约定，减损举证困难"}
    ]
    level_emoji = {"高危":"🔴","中危":"🟠","低危":"🟡","无风险":"🟢"}

    if submit_btn:
        text_input = contract_text.strip()
        if not text_input:
            st.warning("请粘贴合同/案情文本再提交！")
        else:
            risk_list = []
            for rule in risk_rules:
                hit = any(word in text_input for word in rule["keyword"])
                if not hit:
                    risk_list.append(rule)

            if len(risk_list) == 0:
                st.success("🟢 本次扫描未识别关键风险")
            else:
                st.markdown("#### 1.风险识别")
                for item in risk_list:
                    st.markdown(f"{level_emoji[item['level']]} **{item['level']}风险：{item['name']}**")
                    st.caption(item["tip"])

                st.divider()
                st.markdown("#### 2.救济权利提示")
                st.info("基于CISG、UCC：针对买方拒收、拖欠货款，卖方可行使停运权、货物留置、转售货物、主张损害赔偿。请结合完整合同进一步评估。")
    else:
        st.info("点击【提交预审】生成风险报告")