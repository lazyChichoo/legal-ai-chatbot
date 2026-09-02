# -*- coding: utf-8 -*-
"""
出处校验器（第二道防线）

作用：AI 回答生成后，检查里面出现的每一个法条编号，
     是不是真的在本次提供的【参考条文】里。
     不是的话就判定为"编造出处"，打回去让 AI 重写。

不联网、不调 API，纯本地字符串检查。
"""

import re

# ---------- 1. 基础工具 ----------

_CN_DIGIT = {"〇": 0, "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
             "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _cn_to_int(s):
    """把'十一''四十一''一百零五'这种中文数字转成 11 / 41 / 105。转不了就返回 None。"""
    if not s:
        return None
    if s.isdigit():
        return int(s)
    section = 0
    num = 0
    for ch in s:
        if ch in _CN_DIGIT:
            num = _CN_DIGIT[ch]
        elif ch == "十":
            section += (num if num else 1) * 10
            num = 0
        elif ch == "百":
            section += (num if num else 1) * 100
            num = 0
        else:
            return None
    result = section + num
    return result if result > 0 else None


def _norm(text):
    """全角转半角、英文转大写，方便后面统一匹配。"""
    out = []
    for ch in text:
        code = ord(ch)
        if code == 0x3000:
            out.append(" ")
        elif 0xFF01 <= code <= 0xFF5E:
            out.append(chr(code - 0xFEE0))
        else:
            out.append(ch)
    return "".join(out).upper()


# 哪些字样代表哪部法
_LAW_KEYS = [
    ("UCC", ["UCC", "统一商法典", "UNIFORM COMMERCIAL CODE"]),
    ("CISG", ["CISG", "销售合同公约", "国际货物销售"]),
    ("NYC", ["纽约公约", "外国仲裁裁决", "NEW YORK CONVENTION"]),
]


def _law_near(text, pos, window=40):
    """
    看编号前面这一小段文字里提到了哪部法。认不出来就返回 None。

    必须取【离编号最近】的那个法律名，不能按 _LAW_KEYS 的先后顺序认。
    反例：知识库第13条写的是
        "UCC 2-606（接受货物）、2-602（拒收通知）；CISG Art.38（检验）"
    按顺序认会把 Art.38 记成 UCC 38，导致 AI 正确引用"CISG第38条"时被误判成编造出处。
    """
    start = max(0, pos - window)
    left = text[start:pos]
    best_law, best_at = None, -1
    for law, words in _LAW_KEYS:
        for w in words:
            at = left.rfind(w)
            if at > best_at:
                best_law, best_at = law, at
    return best_law


# ---------- 2. 从一段文字里揪出所有法条编号 ----------

def extract_refs(text):
    """返回一个集合，元素形如 ('CISG', '39')、('UCC', '2-706')、(None, '41')。"""
    t = _norm(text)
    refs = set()

    # UCC 的 2-706 / §2-706 / 2—706
    for m in re.finditer(r"2\s*[-–—]\s*(\d{3})", t):
        refs.add(("UCC", "2-" + m.group(1)))

    # 英文的 Article 39 / Art. 39
    for m in re.finditer(r"\bART(?:ICLE)?\.?\s*(\d{1,3})\b", t):
        refs.add((_law_near(t, m.start()), m.group(1)))

    # 中文的 第39条 / 第三十九条
    for m in re.finditer(r"第\s*([0-9]{1,3}|[〇零一二三四五六七八九十百两]{1,6})\s*条", t):
        n = _cn_to_int(m.group(1))
        if n:
            refs.add((_law_near(t, m.start()), str(n)))

    # "UCC Article 2" 说的是《统一商法典》第二编（买卖编），那是篇章名，不是法条号。
    # UCC 的法条一律写成 2-601 这种带横杠的形式，所以裸数字的 UCC 引用根本不是出处，丢掉。
    # 【为什么非改不可】实测同一个意思，中文写"《统一商法典》第二编"因为不是"第X条"而漏过，
    # 英文写 "UCC Article 2" 却被判成编造出处，回答被打回、重试还是被打回，最后吐兜底话术。
    # 中英两种命运不一致，等于英文提问天然吃亏。这里必须对齐。
    refs = set((law, num) for (law, num) in refs
               if not (law == "UCC" and "-" not in num))

    return refs


# 这些是 AI 编假出处时爱用的话术，出现即判违规
_FAKE_SOURCE = [
    "无相关条文", "无对应条文", "无具体条文", "无法律依据", "未提供条文",
    "根据一般法律原则", "根据国际惯例", "根据商业惯例",
    "NO RELEVANT PROVISION", "GENERAL LEGAL PRINCIPLE", "COMMON PRACTICE",
]


# ---------- 3. 主检查函数 ----------

def check(reply, provisions):
    """
    reply      : AI 生成的回答（字符串）
    provisions : 本次喂给 AI 的条文列表，每项形如 {"source": "...", "text": "..."}

    返回 (是否通过, 问题列表)
    """
    problems = []

    # 3.1 允许出现的编号 = 从参考条文的 source 里提取出来的
    allowed = set()
    for p in provisions:
        allowed |= extract_refs(p.get("source", ""))

    # 3.2 假出处话术
    r_norm = _norm(reply)
    for bad in _FAKE_SOURCE:
        if _norm(bad) in r_norm:
            problems.append("出现了假出处话术：" + bad)

    # 3.3 逐个编号比对
    for ref in extract_refs(reply):
        if not _ref_allowed(ref, allowed):
            law, num = ref
            problems.append("引用了参考条文里没有的编号：%s 第%s条" % (law or "（未标明法律）", num))

    return (len(problems) == 0, problems)


def _ref_allowed(ref, allowed):
    """编号必须对得上；法律名认不出来的时候放宽，只比编号。"""
    law, num = ref
    for a_law, a_num in allowed:
        if num != a_num:
            continue
        if law is None or a_law is None or law == a_law:
            return True
    return False


# ---------- 4. 给 AI 的纠错话 ----------

# ============================================================
# 百分数核对：AI 不许编知识库里没有的比例
# ============================================================
# 【为什么非要程序管】先试过写进铁律（"条文里的数字必须照抄、不许自己另给一个"），
# 真接口实测没管住：条文明写"违约金不超过预估损失的20-30%"，AI 正文里只字不提，
# 转头在【实务提示】里自己发明了一个"10%-20%"。知识库里连 10 这个数都没有。
# 用户分不清哪个比例有依据、哪个是编的，这比不给数字更危险。
# 结论：凡是必须一字不差的东西，交给程序，别指望 AI 自觉。
#
# 【只管百分数，不管所有数字】法条编号（§2-718）、天数、金额写法太杂，
# 一刀切会误杀。比例是最容易被编、后果最直接的，先把这一类焊死。
#
# 【实务提示那一段也算】铁律 5 给实务提示开了"不受自检限制"的口子，
# 上面那个 10%-20% 正是从这个口子钻出来的。这里不留例外。

_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*[%％]")
_NUM = re.compile(r"\d+(?:\.\d+)?")


def _allowed_numbers(provisions):
    """喂给 AI 的条文里出现过的所有数字。"""
    got = set()
    for p in provisions:
        for m in _NUM.finditer((p.get("source") or "") + (p.get("text") or "")):
            got.add(m.group())
    return got


def check_numbers(reply, provisions):
    """
    回答里出现的百分数，数字必须在【参考条文】里出现过。
    返回 (是否合格, 问题列表)。
    """
    allowed = _allowed_numbers(provisions)
    bad = sorted({m.group(1) for m in _PCT.finditer(reply)} - allowed,
                 key=lambda x: (len(x), x))
    if not bad:
        return True, []
    return False, ["回答里的比例 %s 在【参考条文】里没有出现过，是编的。"
                   "比例只能照抄条文里写明的数字，条文没给就一个百分比都不要写。"
                   % "、".join(v + "%" for v in bad)]


def build_fix_message(problems):
    lines = ["你上一条回答不合格，具体问题如下："]
    for p in problems:
        lines.append("- " + p)
    lines.append("")
    lines.append("请整段重写这条回答。出处只能使用【参考条文】里原样给出的编号，"
                 "一个字都不许改、不许自造；任何百分比都只能照抄【参考条文】里写明的数字，"
                 "包括【实务提示】那一段在内，条文没给就一个百分比都不要写；"
                 "如果参考条文不足以回答，"
                 "就按铁律第 4 条只输出那一句超范围提示；"
                 "回答语言必须与用户提问的语言完全一致，全文不许混用两种语言。")
    return "\n".join(lines)


VERSION = "v3"
