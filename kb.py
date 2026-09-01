# -*- coding: utf-8 -*-
"""
知识库装载 + 检索层。

职责只有两件：
1. 把 kb_raw.txt（法学组交付的 20 条）解析成程序能用的结构；
2. 拿到一个用户问题，挑出该喂给 AI 的几条，组装成 llm.ask() 要的
   provisions 格式：[{"source": ..., "text": ...}, ...]

一条铁规矩（关系到 citation_guard 会不会误杀）：
    provisions 里的 "source" 必须原样放【法律依据】那一行，
    绝对不许写成"知识库第9条"这种。
    因为 citation_guard 只从 source 里提取允许出现的法条编号；
    source 写成"第9条"，会导致 CISG 40/44/50 全被判成编造出处。
"""

import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
KB_PATH = os.path.join(_HERE, "kb_raw.txt")

# 一条知识里认哪些字段
_FIELDS = ["编号", "标题", "场景标签", "风险等级", "典型问法",
           "回答", "法律依据", "合同审查点", "关键词", "风险提示"]

_FIELD_PAT = re.compile(r"^【(" + "|".join(_FIELDS) + r")】[ \t]*(.*)$")
_SPLIT_PAT = re.compile(r"^[─—\-]{10,}\s*$")


def _parse_block(block):
    """把一段文字解析成一条知识。认不出编号的返回 None。"""
    item = {f: "" for f in _FIELDS}
    cur = None
    for line in block.splitlines():
        m = _FIELD_PAT.match(line)
        if m:
            cur = m.group(1)
            # 同名字段重复出现（法学组第9条有过两行【标题】），保留先出现的那个
            if item[cur]:
                cur = None
                continue
            item[cur] = m.group(2).strip()
        elif cur:
            item[cur] += ("\n" + line.rstrip())

    if not item["编号"]:
        return None

    n = re.search(r"\d+", item["编号"])
    item["no"] = int(n.group()) if n else 0
    item["关键词表"] = [w.strip() for w in re.split(r"[,，、]", item["关键词"]) if w.strip()]
    for f in _FIELDS:
        item[f] = item[f].strip()
    return item


def load(path=None):
    """读取知识库，返回列表，按编号排序。"""
    with open(path or KB_PATH, "r", encoding="utf-8") as f:
        raw = f.read()

    blocks, cur = [], []
    for line in raw.splitlines():
        if _SPLIT_PAT.match(line):
            blocks.append("\n".join(cur))
            cur = []
        else:
            cur.append(line)
    blocks.append("\n".join(cur))

    items = [x for x in (_parse_block(b) for b in blocks) if x]
    items.sort(key=lambda x: x["no"])
    return items


# ---------- 必带条文 ----------
# 某类问题不管检索排名如何，这几条必须塞进去。
# 理由：case_guard 会强制 AI 说出特定法条编号，如果知识库检索没把
# 载有那些编号的条目带上，citation_guard 会判它编造出处，回答被打回，
# 最后吐兜底话术。两道防线必须对齐。
PINNED = {
    # 拒付 / 瑕疵 / 拒收 —— case_guard 的 REJECT_DIRECTIVE 要求引用 CISG 40、44、50
    "reject": [9, 13],
    # 停运 —— case_guard 的 TRANSIT_DIRECTIVE 涉及 CISG 71、UCC 2-705
    "transit": [3, 20],
}


# ------------------------------------------------------------
# 英文检索词
# ------------------------------------------------------------
# 【为什么要有这张表】
# 法学组的 kb_raw.txt 检索字段全是中文，纯英文提问一条都命中不了，
# 实测 8 道英文题只有 2 道能出答案。这题目是"对美出口"，英文问不出来说不过去。
#
# 【词是哪来的、为什么放这儿】
# 词源是法学组 2026-08-31 交付的《中英法律术语对照表》（101 条，见 法学组交付/）。
# 这张表放在 kb.py 里而不是塞进 kb_raw.txt —— kb_raw.txt 是法学组的交付物，
# 我们只读不改，她们下次更新知识库直接覆盖就行，不会把我们加的东西冲掉。
#
# 【只影响"捞哪几条"，不影响"答什么"】
# 这些词只参与检索打分，不会进到喂给 AI 的内容里，也不参与 citation_guard 的条文核对。
EN_TERMS = {
    1:  ["rejection of goods", "buyer's rejection", "wrongful rejection", "refuse to accept",
         "seller's remedies", "remedies clause", "resale", "action for price", "lien",
         "custom-made", "reject the whole"],
    2:  ["action for price", "claim for payment", "unpaid", "outstanding balance",
         "overdue payment", "late payment", "interest", "statutory interest", "balance due"],
    3:  ["stoppage in transit", "written stoppage notice", "carrier", "in transit",
         "insolvency", "insolvent", "bankruptcy", "suspension of performance",
         "bill of lading", "port of destination"],
    4:  ["lien", "right of retention", "withhold delivery", "installment delivery",
         "suspension of performance", "defense of simultaneous performance", "unpaid balance"],
    5:  ["resale", "cover", "mitigation of damages", "duty to mitigate", "substitute transaction",
         "price differential", "difference in price", "commercially reasonable"],
    6:  ["incidental damages", "incidental expenses", "storage cost", "warehousing",
         "raw material", "direct damages", "foreseeable loss"],
    7:  ["loss of profit", "lost profits", "consequential damages", "foreseeability",
         "foreseeable loss", "expected profit", "market price"],
    8:  ["liquidated damages", "penalty", "estimated damages", "late payment penalty",
         "unenforceable", "penalty clause", "20%"],
    9:  ["minor defect", "non-conformity", "surface defect", "scratch", "cosmetic",
         "perfect tender rule", "revocation of acceptance", "fundamental breach",
         "substantial impairment", "reject the entire", "whole lot"],
    10: ["letter of credit", "discrepancy", "discrepancy in documents", "ucp600",
         "independence principle", "negotiation", "soft clause", "dishonor", "presentation"],
    11: ["remedies clause", "seller's remedies", "missing clause", "no remedy clause",
         "contract review", "silent on remedies"],
    12: ["liquidated damages", "penalty", "damages clause", "no penalty clause",
         "burden of proof", "actual loss"],
    13: ["inspection period", "period for notice of non-conformity", "notice of defect",
         "deemed acceptance", "constructive acceptance", "reasonable time", "time limit"],
    14: ["title retention", "reservation of title", "retention of title", "romalpa",
         "right of repossession", "right to reclaim", "passing of risk", "ucc-1 filing",
         "security interest"],
    15: ["governing law", "choice of law", "applicable law", "exclusion of cisg",
         "excluding the cisg", "opt out", "party autonomy"],
    16: ["force majeure", "port strike", "shipping delay", "exemption", "impediment",
         "hardship", "epidemic", "pandemic"],
    17: ["incoterms", "fob", "free on board", "cif", "cost insurance and freight",
         "passing of risk", "transfer of risk", "port of shipment", "port of destination"],
    18: ["arbitral award", "final award", "recognition and enforcement", "new york convention",
         "faa", "federal arbitration act", "petition to confirm award", "hkiac", "cietac",
         "seat of arbitration", "public policy", "enforce the award"],
    19: ["long-arm jurisdiction", "jurisdiction", "forum selection", "cost of defense",
         "attorney fees", "new york state court", "litigation in the us", "service of process"],
    20: ["stoppage in transit", "preservation of evidence", "property preservation",
         "pre-litigation", "written notice", "checklist", "72 hours", "urgent",
         "first 72 hours", "emergency"],
}


# ------------------------------------------------------------
# 打分：这条知识跟这个问题有多相关
# ------------------------------------------------------------
# v3 之前是拿整段比对：知识库写"美国客户说不要货了，货还在洛杉矶港口"，
# 用户得一字不差地这么问才算命中，换个说法就 0 分。考卷实测 40 题只对一半。
# 现在改成按"词"比对：中文切成两字一组（合同/同没/没写…），英文按单词。
# 再按"这个词有多特别"加权 —— 20 条里只有 1 条提到"停运"，那"停运"就很值钱；
# 20 条都提到"合同"，那"合同"基本不加分。这套算法叫 TF-IDF，几十年前就有了，
# 全程不调 AI，同一个问题问一百遍挑出来的条文完全一样。

import math

_CJK = re.compile(r"[\u4e00-\u9fff]+")
_EN = re.compile(r"[a-z][a-z0-9\-\.]{2,}")

# 英文虚词：谁的句子里都有，留着只会把分数带偏。
# （中文那边不需要这张表 —— 两字一组切出来的"的话""可以"这类，靠稀有度加权自然就被压到接近 0 分。）
_EN_STOP = set("""
the and for not with from that this you your are was were has have had can could will would
shall should must may might any all its his her their our but out use does did what when
where which who how why into over under than then they them there here been being such only
also more most some each per via upon about after before still just now还
""".split())

# 低于这个分就当"没命中"，宁可回答"超出知识库范围"，也不硬凑一条不相关的。
MIN_SCORE = 2.0


def _tokens(text):
    """把一段话切成可比对的词：中文两字一组，英文整词。"""
    text = text.lower()
    got = set()
    for run in _CJK.findall(text):
        for i in range(len(run) - 1):
            got.add(run[i:i + 2])
    for w in _EN.findall(text):
        if w in _EN_STOP:
            continue
        got.add(_stem(w))
    return got


def _stem(w):
    """把英文词尾削平：rejected/rejecting/rejects 都归成 reject。
    土办法，不完美（比如 goods -> good），但两边用的是同一套规则，比对结果一致就行。"""
    w = w.rstrip(".").replace("'s", "")
    for suf in ("ing", "ed", "es", "s"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[:-len(suf)]
    return w


def _search_text(item):
    """一条知识里，允许拿来做检索的字段。正文和法律依据不参与，避免整段法条把分数带偏。"""
    parts = [item["标题"], item["典型问法"]] + list(item["关键词表"])
    parts += EN_TERMS.get(item["no"], [])       # 英文词也进来做单词级兜底
    return "。".join(parts)


def _idf(items):
    """算每个词的稀有度：20 条里出现得越少，越能说明问题。"""
    df = {}
    for x in items:
        for t in _tokens(_search_text(x)):
            df[t] = df.get(t, 0) + 1
    n = float(len(items)) or 1.0
    return dict((t, math.log(n / d)) for t, d in df.items())


def _score(item, question, idf=None):
    """土办法打分，看得懂、可复现。分三部分加起来："""
    if idf is None:
        idf = _idf(load())
    q = question.lower()
    qt = _tokens(question)

    # ① 关键词整词命中：最硬的证据，一个 3 分
    s = 0.0
    for w in item["关键词表"]:
        if len(w) >= 2 and w.lower() in q:
            s += 3.0

    # ①b 英文词组命中，同样 3 分。
    # 英文按整个词组比对，不拆成单词 —— 拆开的话 "the""and" 这种谁都有的词会把分数带偏，
    # 而 "stoppage in transit""letter of credit" 整个出现才真说明问的是这件事。
    for w in EN_TERMS.get(item["no"], []):
        if w in q:
            s += 3.0

    # ② 词重合，按稀有度加权：这是 v3 新加的，也是命中率提上来的主力
    shared = qt & _tokens(_search_text(item))
    s += sum(idf.get(t, 0.0) for t in shared)

    # ③ 标题/典型问法整段命中：老规矩留着，命中就是强信号
    for ch in re.findall(r"[\u4e00-\u9fff]{4,}", item["标题"]):
        if ch in question:
            s += 2.0
    for ch in re.findall(r"[\u4e00-\u9fff]{4,}", item["典型问法"]):
        if ch in question:
            s += 1.0
    return s


def to_provision(item):
    """一条知识 -> llm.ask() 要的格式。source 必须是【法律依据】原文。"""
    body = item["回答"]
    if item["风险提示"]:
        body += "\n【风险提示】" + item["风险提示"]
    return {
        "source": item["法律依据"],
        "text": "（知识库第%d条·%s）%s" % (item["no"], item["标题"], body),
        "no": item["no"],
        # 下面两个字段只给"本题属于哪个场景"那一行用，不参与喂给 AI 的内容。
        # citation_guard 只读 source，llm 只读 source 和 text，多带字段是安全的。
        "title": item["标题"],
        "scene": item["场景标签"],
    }


def retrieve(question, items=None, top_k=3, pin=None):
    """
    question : 用户问题
    pin      : PINNED 的键组成的列表，如 ["reject"]；由 case_guard 的判定结果决定
    返回 provisions 列表
    """
    items = items if items is not None else load()
    by_no = {x["no"]: x for x in items}

    chosen = []
    seen = set()

    for key in (pin or []):
        for no in PINNED.get(key, []):
            if no in by_no and no not in seen:
                seen.add(no)
                chosen.append(by_no[no])

    idf = _idf(items)
    scored = sorted(((_score(x, question, idf), x) for x in items),
                    key=lambda p: (-p[0], p[1]["no"]))
    for sc, x in scored:
        if len(chosen) >= max(top_k, len(seen)):
            break
        if x["no"] in seen:
            continue
        if sc < MIN_SCORE:
            break
        seen.add(x["no"])
        chosen.append(x)

    # 排序：最相关的排第一。
    # 必带条文（pin）是安全网 —— 保证该讲的法条一定喂给 AI，
    # 但"本题属于哪个场景"该由相关度说了算，不该由安全网说了算。
    # 例：信用证拒付题会触发"拒收"必带条文，可它的主场景是信用证那一条，不是拒收那一条。
    chosen.sort(key=lambda x: (-_score(x, question, idf), x["no"]))
    return [to_provision(x) for x in chosen]


VERSION = "v3"
