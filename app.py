# -*- coding: utf-8 -*-
"""
跨境违约救济 AI 预审系统 —— 网页界面

跑法（在项目文件夹里）：
    streamlit run app.py

没装过 streamlit 的先装一次：
    pip install streamlit
"""

import streamlit as st

import bot
import case_guard
import citation_guard
import kb

st.set_page_config(page_title="跨境违约救济AI预审系统", page_icon="⚖️", layout="wide")


@st.cache_data
def load_kb():
    """知识库只读一次，问一次读一次太浪费。"""
    return kb.load()


ITEMS = load_kb()

# ---------------- 侧边栏：合同 ----------------

with st.sidebar:
    st.header("合同（可不填）")
    st.caption(
        "把合同里的**法律适用条款**贴进来，系统会判断该走 CISG 还是美国州法。"
        "不填就按缔约国默认走 CISG。"
    )

    up = st.file_uploader("上传合同文本（.txt）", type=["txt"])
    default_text = ""
    if up is not None:
        raw = up.read()
        for enc in ("utf-8", "gbk", "utf-16"):
            try:
                default_text = raw.decode(enc)
                break
            except Exception:
                continue
        if not default_text:
            st.error("这个文件的编码认不出来，请把内容直接粘贴到下面的框里。")

    contract_text = st.text_area(
        "或者直接粘贴合同条款", value=default_text, height=200,
        placeholder="例：This Agreement shall be governed by the laws of the State of New York, "
                    "excluding the United Nations Convention on Contracts for the "
                    "International Sale of Goods.",
    )

    if contract_text.strip():
        verdict, evidence = case_guard.detect_governing_law(contract_text)
        msg = bot.LAW_LABEL[verdict]
        if verdict == "cisg_excluded":
            st.warning("⚖️ " + msg)
        elif verdict == "state_law_only":
            st.info("⚖️ " + msg)
        else:
            st.info("⚖️ " + msg)
        if evidence:
            st.caption("依据的原文：" + evidence[:120])

    st.divider()
    st.caption("知识库：%d 条   " % len(ITEMS))
    st.caption("守门程序：出处核验 / 语言与免责声明 / 法律硬规则")

# ---------------- 主区 ----------------

st.title("⚖️ 跨境违约救济 AI 预审系统")
st.caption("面向对美出口卖方 · 中美跨境货物买卖 · CISG 与 UCC")

EXAMPLES = [
    "客户说沙发有个小划痕，整批货都不要了，还要拒付，这合法吗？",
    "货在海上，听说美国客户要破产，我能叫船公司别交货吗？",
    "合同没写检验期，客户半年后说质量不行还能拒收吗？",
    "客户收货两个月不打尾款，我能起诉要钱吗？利息怎么算？",
]

if "question" not in st.session_state:
    st.session_state.question = ""

st.write("**常见问题**（点一下就填进去）")
cols = st.columns(2)
for i, ex in enumerate(EXAMPLES):
    if cols[i % 2].button(ex, key="ex%d" % i, use_container_width=True):
        st.session_state.question = ex

question = st.text_area(
    "你的问题", key="question", height=100,
    placeholder="用大白话说就行，比如：客户拿质量说事不肯付尾款，我能怎么办？",
)

go = st.button("开始预审", type="primary", use_container_width=True)

if go:
    if not question.strip():
        st.warning("先说说遇到什么事了。")
        st.stop()

    with st.spinner("正在检索知识库并预审…（AI 答得不合规会被程序打回重写，可能要多等几秒）"):
        try:
            info = bot.answer_detailed(
                question, contract_text=contract_text or None, items=ITEMS)
        except Exception as e:
            st.error("调用失败：%s\n\n检查一下 .env 里的 API key 是否正确、网络是否通。" % e)
            st.stop()

    st.divider()
    st.subheader("预审意见")
    st.markdown(info["answer"])

    # ---------- 审核过程 ----------
    trace = info["trace"]
    blocked = sum(1 for t in trace if not t["passed"])

    if not info["called_api"]:
        head = "审核过程 · 未调用 AI（问题超出知识库范围）"
    elif blocked:
        head = "审核过程 · 程序拦下并要求重写 %d 次" % blocked
    else:
        head = "审核过程 · 一次通过"

    with st.expander(head, expanded=False):
        st.markdown("##### 1. 这道题命中了知识库哪几条")
        if info["provisions"]:
            for p in info["provisions"]:
                st.markdown("- **第 %d 条** —— 法律依据：%s" % (p["no"], p["source"]))
        else:
            st.markdown("- 一条都没命中，所以直接返回超范围提示，**没有花钱调用 AI**。")

        if info["pins"]:
            names = {"reject": "拒付/瑕疵题 → 强制带上第 9、13 条",
                     "transit": "停运题 → 强制带上第 3、20 条"}
            st.markdown("##### 2. 必带条文规则")
            for k in info["pins"]:
                st.markdown("- " + names.get(k, k))
            st.caption(
                "为什么要强制：硬规则会命令 AI 引用特定条文号，"
                "如果检索没把载有这些编号的条目带上，出处核验会把它当成编造出处打回去，"
                "两道防线会互相打架。")

        st.markdown("##### 3. 法律适用判断")
        st.markdown("- " + bot.LAW_LABEL[info["law"]["verdict"]])

        allowed = set()
        for p in info["provisions"]:
            allowed |= citation_guard.extract_refs(p["source"])
        if allowed:
            st.markdown("##### 4. 本次允许出现的条文编号")
            txt = "、".join(
                "%s 第%s条" % (law or "未标明", num)
                for law, num in sorted(allowed, key=lambda r: (r[0] or "", r[1])))
            st.code(txt, language=None)
            st.caption("回答里出现这个名单以外的编号，一律判定为编造出处、打回重写。")

        if trace:
            st.markdown("##### 5. 逐轮审核结果")
            for t in trace:
                if t["passed"]:
                    st.success("第 %s 轮：通过" % t["round"])
                else:
                    label = ("第 %s 轮：被拦下" % t["round"]) if t["round"] else "最终：仍不合格"
                    st.error(label)
                    for prob in t["problems"]:
                        st.markdown("- " + prob)
                    if t["raw"]:
                        st.caption("AI 当时写的原话：")
                        st.text(t["raw"])

st.divider()
st.caption(
    "本系统提供的法律信息仅供参考，不构成正式法律意见，不可替代执业律师服务。"
    "风险等级仅为初步提示，不代表确定性法律判断。涉及重大法律事项，请咨询执业律师。"
    "因使用本系统信息产生的损失，开发团队不承担法律责任。"
)
