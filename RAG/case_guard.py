# -*- coding: utf-8 -*-
"""
case_guard.py —— 法律硬规则守门（法学组 2026-08-20 确认的口径）

三件事在这里由程序管，不靠 AI 自觉：
  1. 绝不输出具体赔偿金额，只讲计算方法
  2. 涉及停运权，关键事实问不清就不给结论
  3. 先判合同有没有排除 CISG，再决定走 CISG 还是 UCC
"""

import re


# ============================================================
# 一、金额闸门：只讲怎么算，不讲多少钱
# ============================================================

_AMOUNT_PATTERNS = [
    # $50,000 / ￥100000
    r"[\$￥¥€£＄]\s*\d[\d,，]*(?:[.．]\d+)?",
    # USD 50,000 / 人民币 100000
    r"(?:USD|RMB|CNY|EUR|GBP|HKD|JPY|人民币|美元)\s*\d[\d,，]*(?:[.．]\d+)?",
    # 50,000美元 / 10万元 / 3.5万美金
    r"\d[\d,，]*(?:[.．]\d+)?\s*(?:万|亿)?\s*"
    r"(?:美元|美金|人民币|欧元|英镑|日元|港币|元|USD|RMB|CNY|EUR|GBP|dollars?)",
    # 十万美元 / 三万元
    r"[一二三四五六七八九十百千万亿零两]{1,10}\s*(?:美元|美金|人民币|元)",
]


def find_amounts(text):
    """找出文本里所有像"一笔钱"的写法，返回列表。"""
    hits = []
    for pat in _AMOUNT_PATTERNS:
        for m in re.finditer(pat, text, flags=re.I):
            s = m.group(0).strip()
            if s not in hits:
                hits.append(s)
    return hits


def check_no_amount(reply):
    """回答里不许出现具体金额。返回 (是否合格, 问题列表)"""
    hits = find_amounts(reply)
    if not hits:
        return True, []
    return False, [
        "回答里出现了具体金额：%s。损害赔偿只能讲计算方法（用哪个价差、"
        "算到哪个时间点、含哪些附带费用），一个数字都不许给出来。"
        % "、".join(hits[:5])
    ]


# ============================================================
# 二、停运权闸门：三件事问不清，不许给结论
# ============================================================

_TRANSIT_WORDS = [
    # 书面说法
    "停运", "中止交付", "停止交付", "中止发货", "中止履行", "退运", "阻止提货",
    # 用户口语说法（真实提问长这样）
    "拦截", "拦下", "拦住", "拦回", "拦货", "截留", "截住", "扣货", "扣下",
    "叫停", "追回货", "把货要回", "不让他提货", "不给他发",
    # 2026-08-29 补：真实提问里最常见的说法漏在表外，导致停运题走不进追问流程
    "别交货", "别发货", "别放货", "不要交货", "不要发货", "先别发", "暂缓发货",
    "暂停发货", "暂停交货", "停止发货", "别给他", "不交给他", "退回来",
    "叫船公司", "通知船公司", "通知承运人", "让船公司", "找船公司",
    "STOPPAGE", "STOP DELIVERY", "STOP IN TRANSIT", "SUSPEND DELIVERY",
    "WITHHOLD DELIVERY", "HOLD THE SHIPMENT", "STOP THE SHIPMENT",
]

# 三个关键事实，每项给若干"说明用户已经交代过"的线索词
_TRANSIT_FACTS = [
    ("货物现在在哪", ["还没发", "未发货", "在途", "已发货", "已装船", "到港", "目的港",
                  "已交承运人", "承运人", "仓库", "已交付买方", "买方已提货",
                  "IN TRANSIT", "SHIPPED", "NOT SHIPPED", "ARRIVED"]),
    ("正本提单谁拿着", ["提单", "B/L", "BILL OF LADING", "单据在", "正本"]),
    ("付款方式", ["T/T", "TT", "L/C", "LC", "信用证", "D/P", "D/A", "电汇",
              "赊销", "预付", "尾款", "OA", "付款方式"]),
]


def is_transit_question(question):
    """这道题是不是在问停运权 / 中止交付。"""
    q = question.upper()
    return any(w.upper() in q for w in _TRANSIT_WORDS)


def transit_facts_missing(question):
    """返回用户还没交代的关键事实名称列表。"""
    q = question.upper()
    missing = []
    for name, clues in _TRANSIT_FACTS:
        if not any(c.upper() in q for c in clues):
            missing.append(name)
    return missing


TRANSIT_DIRECTIVE = """
【本题触发：停运权关键事实核对】
本题涉及停运权 / 中止交付。用户还没交代清楚下面这些事：{missing}
在这些事没问清之前，你绝对不许给任何救济结论、不许说"你可以停运"或"你不能停运"。
本次回答只做一件事：
  1. 先用一两句话说明为什么下面三件事决定结论；
  2. 逐条列出要用户补充的信息——货物现在在哪（还没交承运人 / 在途 / 已到目的港 / 已交给买方）、
     全套正本提单现在谁持有（卖方 / 银行 / 买方）、付款方式（T/T 预付或尾款 / L/C / D/P / D/A / 赊销）；
  3. 然后停止。不要给建议，不要列救济步骤。
"""


def check_transit_reply(question, reply):
    """停运题且事实不全时，回答必须是在追问，而不是在下结论。"""
    if not is_transit_question(question):
        return True, ""
    if not transit_facts_missing(question):
        return True, ""
    r = reply.upper()
    asked = 0
    if "提单" in reply or "B/L" in r or "BILL OF LADING" in r:
        asked += 1
    if "付款方式" in reply or "L/C" in r or "T/T" in r or "信用证" in reply:
        asked += 1
    if "货" in reply or "GOODS" in r or "SHIP" in r:
        asked += 1
    if asked >= 2:
        return True, ""
    return False, ("本题涉及停运权且关键事实不全，回答必须是向用户追问"
                   "「货在哪 / 正本提单谁持有 / 付款方式」这三件事，不许直接下结论。")


# ============================================================
# 三、法律适用分叉：CISG 还是 UCC
# ============================================================

_CISG_WORDS = ["CISG", "销售合同公约", "国际货物销售", "VIENNA CONVENTION",
               "CONVENTION ON CONTRACTS FOR THE INTERNATIONAL SALE"]

_EXCLUDE_WORDS = ["EXCLUD", "SHALL NOT APPLY", "DOES NOT APPLY", "NOT BE GOVERNED",
                  "OPT OUT", "排除", "不适用", "不予适用", "均不适用", "予以排除"]

_STATE_LAW_PAT = re.compile(
    r"(LAWS?\s+OF\s+THE\s+STATE\s+OF\s+([A-Z\s]{3,20}))|"
    r"(适用\s*[美国]{0,2}\s*([一-鿿]{2,6})\s*州(?:的)?法律)",
    re.I)


def detect_governing_law(contract_text):
    """
    看合同里的法律适用条款，返回 (结论, 证据原文)。
    结论三选一：
      "cisg_excluded" —— 明确排除了 CISG，走 UCC / 州法
      "state_law_only" —— 只选了某州法律但没排除 CISG，实际仍适用 CISG（高频误解）
      "unknown"       —— 没找到法律适用条款，按缔约国默认走 CISG
    """
    if not contract_text:
        return "unknown", ""
    t = contract_text.upper()

    for w in _CISG_WORDS:
        start = 0
        while True:
            pos = t.find(w, start)
            if pos < 0:
                break
            start = pos + 1
            window = t[max(0, pos - 150):pos + 150]
            if any(e in window for e in _EXCLUDE_WORDS):
                raw = contract_text[max(0, pos - 80):pos + 80]
                return "cisg_excluded", raw.strip()

    m = _STATE_LAW_PAT.search(contract_text)
    if m:
        return "state_law_only", m.group(0).strip()

    return "unknown", ""


LAW_DIRECTIVE = {
    "cisg_excluded": """
【本题法律适用已确定】
合同已明确排除《联合国国际货物销售合同公约》(CISG)，本题一律按美国《统一商法典》(UCC) 第二编回答，
不许引用 CISG 任何条文。合同排除条款原文：{evidence}
""",
    "state_law_only": """
【本题法律适用需要先说清楚】
合同只写了适用美国某州法律（原文：{evidence}），但没有明确排除 CISG。
中国和美国都是 CISG 缔约国，而 CISG 是美国联邦条约、本身就是该州法律的一部分，
所以这种写法**不能**排除 CISG——本案仍然适用 CISG。
回答必须先用一句话点明这一点，再按 CISG 给救济路径，最后提醒卖方：
若确实想走该州 UCC，合同必须写明"排除适用《联合国国际货物销售合同公约》"。
""",
    "unknown": """
【本题法律适用按默认处理】
用户没有提供合同的法律适用条款。中国和美国都是 CISG 缔约国，默认适用 CISG，请按 CISG 回答。
回答末尾必须加一句提醒：如果合同里写了"排除适用《联合国国际货物销售合同公约》"，
结论要改按美国相应州的《统一商法典》(UCC) 第二编重新判断，请把合同法律适用条款发来复核。
""",
}


# ============================================================
# 四、恶意拒付三要件
# ============================================================

# 一望即知就是"以货物有问题为由拒付"的说法，单独出现即触发
_REJECT_EXPLICIT = ["质量不符", "以质量为由", "货不对板", "挑毛病",
                    "质量问题", "NON-CONFORMIT"]

# "拒绝收/拒绝付"这一类
_REFUSE_WORDS = ["拒付", "拒收", "不付款", "不给钱", "不肯付", "不肯收",
                 "不要了", "退货", "退回来", "REJECT", "REFUSE TO PAY",
                 "REFUSE DELIVERY", "REFUSE TO ACCEPT"]

# "货有问题"这一类
_DEFECT_WORDS = ["质量", "瑕疵", "不符", "有问题", "划痕", "破损", "损坏",
                 "次品", "残次", "色差", "尺寸不对", "规格不对", "货不对",
                 "DEFECT", "QUALITY", "DAMAGED", "SCRATCH", "NON-CONFORMIT"]


def is_rejection_question(question):
    """
    只有"买方以货物有问题为由拒付/拒收"才算拒付三要件题。

    单纯欠钱不算——"客户拖欠尾款""两个月不打款"走的是价金请求权（第2条），
    硬套三要件会逼 AI 去讲毫不相干的瑕疵通知例外，讲不出来就被自己的
    防线打回，最后吐兜底话术。这里必须"拒绝"和"有瑕疵"两件事同时出现。
    """
    q = question.upper()
    if any(w.upper() in q for w in _REJECT_EXPLICIT):
        return True
    refuse = any(w.upper() in q for w in _REFUSE_WORDS)
    defect = any(w.upper() in q for w in _DEFECT_WORDS)
    return refuse and defect


REJECT_DIRECTIVE = """
【本题触发：买方拒付三要件核对】
买方以"质量不符"拒付，必须同时满足三个条件才站得住脚。回答必须按这三条逐条走：
  1. 检验期限——买方是否在合同约定期限内、没约定则在实际可行的最短时间内检验了货物；
  2. 通知——买方是否在约定期限内、没约定则在发现或理应发现后的合理时间内，
     书面通知了卖方，并且说明了不符合同情形的性质；
  3. 严重程度——瑕疵是否达到 CISG 下的"根本违约"，或 UCC 下破坏了"完美交付"要求。
三条里只要有一条不满足，买方原则上就丧失以质量为由拒付的权利，卖方有权请求支付价金。
但必须同时说明两个例外，不许省略，并且必须写出条文编号：
  - 例外一（CISG 第40条）：若卖方在订约时已经知道或不可能不知道该瑕疵却没有告知买方，
    卖方不能援引第38条检验期与第39条通知期抗辩，买方即使迟延通知也不丧失权利；
  - 例外二（CISG 第44条）：若买方对未按第39条第(1)款及时通知有合理理由，
    买方仍保留两项权利，两项都必须写出来，不许只写减价：
      (a) 按第50条要求减价；
      (b) 要求损害赔偿——但不包括利润损失。
    该条并不恢复买方拒收全部货物或宣告合同无效的权利。
    注意：(b) 是对卖方不利的一半，漏讲会让卖方误判自己的风险敞口，绝对不许省。
最后提醒：以上是初步判断方向，具体结论取决于合同约定的检验期与通知期原文。
"""


# 拒付题的回答里，这两个例外必须出现——靠程序验收，不靠模型自觉
_REJECT_MUST = [
    (["第40条", "ART.40", "ARTICLE 40"], "例外一（CISG 第40条，卖方明知瑕疵不得抗辩）"),
    (["第44条", "ART.44", "ARTICLE 44"], "例外二（CISG 第44条，买方有合理理由延迟通知）"),
]


def check_reject_reply(question, reply):
    """拒付题必须讲全两个例外。返回 (是否合格, 问题列表)"""
    if not is_rejection_question(question):
        return (True, [])
    r = reply.upper().replace(" ", "")
    missing = []
    for keys, label in _REJECT_MUST:
        if not any(k.replace(" ", "") in r for k in keys):
            missing.append(label)

    # 讲了第44条，就必须把"还能要利润损失以外的损害赔偿"一起讲。
    # 实测模型爱把这半句吞掉，只说"可以减价"——那是只讲了对卖方有利的一半，
    # 卖方会误判成"买方最多砍点价"，实际还要挨一笔索赔。
    if any(k.replace(" ", "") in r for k in ["第44条", "ART.44", "ARTICLE 44"]):
        said_damages = ("损害赔偿" in reply) or ("DAMAGES" in r)
        said_profit = ("利润" in reply) or ("LOSSOFPROFIT" in r)
        if not (said_damages and said_profit):
            missing.append("例外二漏了一半：买方在第44条下除了减价，"
                           "还可以要求利润损失以外的损害赔偿，这句必须写出来")

    if not missing:
        return (True, [])
    return (False, ["拒付题漏讲了必须说明的例外：" + "；".join(missing) +
                    "。这个系统是给卖方用的，只讲对卖方有利的一半会让卖方误判，必须补齐。"])


# 哪类问题必须强制带上哪些知识库条目（给 kb.retrieve 的 pin 参数用）
def pins(question):
    """返回必带条文的标签列表，如 ["reject"]。"""
    tags = []
    if is_rejection_question(question):
        tags.append("reject")
    if is_transit_question(question):
        tags.append("transit")
    return tags


# ============================================================
# 五、对外的两个总入口
# ============================================================

def directives(question, contract_text=None):
    """
    根据问题内容，拼出本次要额外强制给模型的指令。
    没有触发任何规则就返回空字符串。
    """
    parts = []

    verdict, evidence = detect_governing_law(contract_text)
    parts.append(LAW_DIRECTIVE[verdict].format(evidence=evidence or "（无）"))

    if is_transit_question(question):
        missing = transit_facts_missing(question)
        if missing:
            parts.append(TRANSIT_DIRECTIVE.format(missing="、".join(missing)))

    if is_rejection_question(question):
        parts.append(REJECT_DIRECTIVE)

    return "\n".join(p.strip() for p in parts if p.strip())


def check_all(question, reply):
    """本模块负责的全部检查。返回 (是否合格, 问题列表)"""
    problems = []

    ok, probs = check_no_amount(reply)
    if not ok:
        problems.extend(probs)

    ok, prob = check_transit_reply(question, reply)
    if not ok:
        problems.append(prob)

    ok, probs = check_reject_reply(question, reply)
    if not ok:
        problems.extend(probs)

    return (len(problems) == 0, problems)


VERSION = "v7"
