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
    """看编号前面这一小段文字里提到了哪部法。认不出来就返回 None。"""
    left = text[max(0, pos - window):pos]
    for law, words in _LAW_KEYS:
        for w in words:
            if w in left:
                return law
    return None


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

def build_fix_message(problems):
    lines = ["你上一条回答不合格，具体问题如下："]
    for p in problems:
        lines.append("- " + p)
    lines.append("")
    lines.append("请整段重写这条回答。出处只能使用【参考条文】里原样给出的编号，"
                 "一个字都不许改、不许自造；如果参考条文不足以回答，"
                 "就按铁律第 4 条只输出那一句超范围提示；"
                 "回答语言必须与用户提问的语言完全一致，全文不许混用两种语言。")
    return "\n".join(lines)


VERSION = "v2"
