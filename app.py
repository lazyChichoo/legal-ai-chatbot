import os
import html as html_lib
import tempfile

import streamlit as st

import bot
import contract_prescreen
import ingest
import kb

st.set_page_config(
    page_title="法小盾——面向对美出口卖方的跨境违约救济AI预审系统",
    page_icon="⚖️",
    layout="wide"
)

# ============================================================
# 样式
# ============================================================
st.markdown("""
<style>
div.block-container { padding-top: 2.6rem; padding-bottom: 1rem; }

/* 输入框贴底。它必须是标签页里最后一个元素，sticky 才生效 */
div[data-testid="stChatInput"] {
    position: sticky !important;
    bottom: 0 !important;
    z-index: 99;
    padding: 10px 0 4px 0;
    background: var(--background-color, #fff);
}

/* 合同风险报告 */
.rep {
    font-size: 13.5px;
    line-height: 1.85;
    font-variant-numeric: tabular-nums;
    word-break: break-word;
    overflow-wrap: anywhere;
}
.rep .rule      { border-top: 1px solid #e6e8eb; margin: 10px 0; }
.rep .rule.strong { border-top: 2px solid #c8ccd2; margin: 12px 0; }
.rep .lbl       { font-weight: 600; color: #3d4450; }
.rk {
    display: inline-block; padding: 1px 9px; border-radius: 10px;
    font-size: 12px; font-weight: 600; letter-spacing: .3px; margin-right: 6px;
}
.rk.hi  { background: #fdecea; color: #b3261e; border: 1px solid #f5c6c2; }
.rk.mid { background: #fff6e5; color: #96590d; border: 1px solid #f7dfae; }
.rk.ok  { background: #e9f6ec; color: #1c6b34; border: 1px solid #bfe3c8; }

/* 法条原文小卡片 */
.prov {
    font-size: 13px; line-height: 1.8; color: #3d4450;
    background: #f7f8fa; border-left: 3px solid #b9c0cb;
    padding: 9px 12px; border-radius: 0 6px 6px 0; margin: 4px 0 14px 0;
}
/* 知识库概览 */
.kbrow { font-size: 12.8px; line-height: 1.75; color: #4a515c; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# 小工具
# ============================================================
HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE_PATH = os.path.join(HERE, "样例合同_买方格式.txt")

LABELS = ("发现　　", "发现", "什么后果", "建议怎么补", "法律依据", "原文", "说明", "证据")


def _esc_br(text):
    """转义成安全 HTML，并保住换行和缩进。"""
    out = html_lib.escape(text or "")
    out = out.replace("\n", "<br>").replace("  ", "&nbsp;&nbsp;")
    return out


def render_report(text):
    """把纯文本报告转成 HTML。

    必须自己转，不能直接把原文塞进 markdown：
      1. 报告里的 ------ 分隔线会被 markdown 当成"上一行是标题"的下划线，
         整段风险描述会被吞进一个大标题，换行和缩进全丢；
      2. 报告里会原样引用合同片段，不转义的话合同里的 <标签> 会被浏览器当真标签执行。
    """
    rows = []
    for line in (text or "").split("\n"):
        bare = line.strip()
        if bare and set(bare) <= set("="):
            rows.append('<div class="rule strong"></div>')
            continue
        if bare and set(bare) <= set("-"):
            rows.append('<div class="rule"></div>')
            continue

        cell = html_lib.escape(line).replace("  ", "&nbsp;&nbsp;")
        for tag, cls in (("[高风险]", "hi"), ("[中风险]", "mid"), ("[已覆盖]", "ok")):
            cell = cell.replace(tag, '<span class="rk %s">%s</span>' % (cls, tag[1:-1]))
        for lb in LABELS:
            if ("%s：" % lb) in cell:
                cell = cell.replace("%s：" % lb, '<span class="lbl">%s：</span>' % lb, 1)
                break
        rows.append(cell + "<br>")
    return '<div class="rep">%s</div>' % "".join(rows)


WELCOME = {
    "role": "assistant",
    "content": "欢迎使用法小盾。请描述你遇到的跨境交易纠纷，系统会依据知识库条文给出带出处的预审意见。",
    "scene_header": None, "provisions": None, "trace": None, "called_api": None,
}

QUICK_ASKS = [
    ("买方拒收货物", "买方无正当理由拒收货物，卖方有哪些救济选择？"),
    ("买家破产追款", "美国客户破产了，我的货款还能要回来吗？"),
    ("不可抗力条款", "合同里要不要写不可抗力条款？"),
    ("范围外提问", "今天北京天气怎么样？"),
]


# ============================================================
# 访问口令
# ============================================================
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


if "messages" not in st.session_state:
    st.session_state.messages = [dict(WELCOME)]


# ============================================================
# 侧边栏
# ============================================================
with st.sidebar:
    st.header("知识库")

    try:
        _items = kb.load()
    except Exception:
        _items = []

    if _items:
        _by_scene = {}
        for _x in _items:
            _by_scene.setdefault(_x["场景标签"], []).append(_x)
        st.markdown("当前共 **%d 条**结构化法律知识，覆盖 %d 类场景。"
                    % (len(_items), len(_by_scene)))
        for _scene, _group in _by_scene.items():
            with st.expander("%s（%d 条）" % (_scene, len(_group))):
                st.markdown(
                    '<div class="kbrow">%s</div>' % "<br>".join(
                        "第 %d 条 · %s" % (_g["no"], html_lib.escape(_g["标题"]))
                        for _g in _group),
                    unsafe_allow_html=True)
        st.caption("回答只能引用上面这些条文，引用编号由程序逐条核对。")
    else:
        st.warning("知识库读取失败，请检查 kb_raw.txt 是否存在。")

    st.divider()
    with st.expander("扩充知识库（开发用）"):
        st.caption(
            "上传的文档只写入向量库；系统回答时读取的是 kb_raw.txt，"
            "因此新内容不会立刻出现在回答里，需要把条目补进 kb_raw.txt 后重建索引。"
            "格式要求：每条包含【编号】【标题】【场景标签】【法律依据】【关键词】"
            "【典型问法】【回答】。"
        )
        uploaded_file = st.file_uploader("选择知识库文件", type=["txt", "docx"])
        if uploaded_file is not None and st.button("写入向量库", use_container_width=True):
            temp_file_path = None
            try:
                with tempfile.NamedTemporaryFile(
                        mode="wb", delete=False,
                        suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_f:
                    tmp_f.write(uploaded_file.getvalue())
                    temp_file_path = tmp_f.name
                with st.spinner("解析中..."):
                    chunk_count = ingest.ingest(source=temp_file_path, reset=False)
                st.success("已写入向量库，共 %d 条片段。" % chunk_count)
                st.caption("提醒：回答仍以 kb_raw.txt 为准。")
            except Exception as exc:
                st.error("导入失败：%s" % exc)
            finally:
                if temp_file_path and os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)

    st.divider()
    with st.expander("开发人员技术信息"):
        st.markdown("- 检索方案：Chroma 词级向量粗筛 + TF-IDF 精排")
        st.markdown("- 重建索引：`python ingest.py --source kb_raw.txt --reset`")
    st.caption("本工具仅作参考，不能替代执业律师的正式法律意见。")


# ============================================================
# 主体
# ============================================================
st.title("法小盾")
st.caption("面向对美出口卖方的跨境违约救济 AI 预审系统")
st.info("免责声明：系统输出仅为普法预审参考，不构成正式法律意见。涉及真实涉外案件，请务必咨询涉外执业律师。")

tab_chat, tab_contract = st.tabs(["法律问答", "合同风险预审"])


# ---------------------------- 法律问答 ----------------------------
with tab_chat:
    pending = None

    _cols = st.columns(len(QUICK_ASKS) + 1)
    for _col, (_label, _question) in zip(_cols, QUICK_ASKS):
        if _col.button(_label, use_container_width=True, key="q_%s" % _label):
            pending = _question
    if _cols[-1].button("清空对话", use_container_width=True, key="q_clear"):
        st.session_state.messages = [dict(WELCOME)]
        st.rerun()

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg.get("scene_header"):
                st.caption(msg["scene_header"])
            st.write(msg["content"])

            if msg["role"] != "assistant" or msg.get("provisions") is None:
                continue
            with st.expander("查看本次依据法条与重写记录"):
                st.markdown("**AI 参考的知识库法条：**")
                if msg["provisions"]:
                    for p in msg["provisions"]:
                        st.markdown("**第 %s 条 · %s**" % (p["no"], p["title"]))
                        st.caption("场景：%s ｜ 法律依据：%s" % (p["scene"], p["source"]))
                        st.markdown('<div class="prov">%s</div>' % _esc_br(p["text"]),
                                    unsafe_allow_html=True)
                    st.info("以上是本次 AI 仅可使用的参考材料，知识库其余内容本次不会被调用。")
                else:
                    st.caption("本次没有命中任何知识库法条，系统直接拒答，未调用大模型。")

                st.divider()
                st.markdown("**AI 重写历史记录（输出防护校验）：**")
                if not msg.get("called_api"):
                    st.caption("本次未调用大模型，无审核记录。")
                else:
                    blocked = [t for t in (msg.get("trace") or []) if not t["passed"]]
                    if not blocked:
                        st.caption("AI 回答一次校验通过，没有被拦截重写。")
                    for t in blocked:
                        if t["round"]:
                            st.markdown("**第 %s 轮输出被程序打回，拦截原因：**" % t["round"])
                        else:
                            st.markdown("**多次校验失败，切换为安全拒答话术：**")
                        for prob in t["problems"]:
                            st.markdown("- %s" % prob)
                        if t["raw"]:
                            st.caption("AI 原始输出（已拦截，未展示给用户）：")
                            st.code(t["raw"], language=None)

    # 输入框必须放在最后：它是 sticky 贴底的，排在中间会浮在对话上方。
    typed = st.chat_input("请输入你的跨境法律问题，例如：买家拖欠货款我该如何维权？")
    if typed:
        pending = typed

    if pending:
        st.session_state.messages.append({"role": "user", "content": pending})
        try:
            with st.spinner("正在检索知识库，生成预审回答..."):
                info = bot.answer_detailed(pending)
            st.session_state.messages.append({
                "role": "assistant",
                "content": info["answer"],
                "scene_header": info.get("scene_header"),
                "provisions": info.get("provisions"),
                "trace": info.get("trace"),
                "called_api": info.get("called_api"),
            })
        except Exception:
            # 额度用尽、网络中断等：给一句人话，不要把报错栈甩到评委脸上
            st.session_state.messages.append({
                "role": "assistant",
                "content": "抱歉，AI 服务暂时不可用（可能是接口额度用尽或网络中断），"
                           "请稍后重试。合同风险预审不依赖 AI，可以正常使用。",
                "scene_header": None, "provisions": None, "trace": None, "called_api": None,
            })
        st.rerun()


# ---------------------------- 合同风险预审 ----------------------------
with tab_contract:
    st.subheader("合同风险预审")
    st.caption("按法学组《卖方违约救济合同审查规则清单》逐条扫描。纯规则引擎，不调用大模型，不产生费用。")

    if st.session_state.pop("_load_sample", False):
        try:
            with open(SAMPLE_PATH, encoding="utf-8") as fh:
                st.session_state["contract_text"] = fh.read()
        except Exception as exc:
            st.session_state["_sample_err"] = str(exc)

    _err = st.session_state.pop("_sample_err", None)
    if _err:
        st.warning("示例合同载入失败：%s" % _err)

    st.text_area("粘贴合同全部文本", height=300, key="contract_text",
                 placeholder="把你的合同复制粘贴到这里，或点下方「载入示例合同」...")

    c1, c2, _ = st.columns([1.1, 1.1, 2.4])
    if c1.button("载入示例合同", use_container_width=True,
                 disabled=not os.path.exists(SAMPLE_PATH)):
        st.session_state["_load_sample"] = True
        st.rerun()
    submit_btn = c2.button("开始风险审查", use_container_width=True, type="primary")

    if submit_btn:
        contract_text = st.session_state.get("contract_text", "")
        if not contract_text.strip():
            st.warning("请先粘贴合同文本，或点「载入示例合同」。")
        else:
            try:
                with st.spinner("正在按规则清单逐条扫描..."):
                    report_result = contract_prescreen.report(contract_text)
                st.divider()
                st.subheader("合同风险预审报告")
                st.markdown(render_report(report_result), unsafe_allow_html=True)
                st.download_button("下载报告（txt）", data=report_result.encode("utf-8"),
                                   file_name="合同风险预审报告.txt", mime="text/plain")
            except Exception as exc:
                st.error("合同审查失败：%s" % exc)
