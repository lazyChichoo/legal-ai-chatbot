# -*- coding: utf-8 -*-
"""
输出格式强制器

作用：AI 生成完之后，程序动手把格式掰正，不指望它自觉。
     1) 免责声明按提问语言强制替换（AI 写错了就删掉重贴）
     2) 英文回答里的"（来源：xxx）"统一改成"(Source: xxx)"

纯本地字符串处理，不调 API。
"""

import re

DISCLAIMER_CN = "本回复仅为普法参考，不构成法律意见，具体案件请咨询执业律师。"
DISCLAIMER_EN = ("This response is for general legal information only and "
                 "does not constitute legal advice.")

# 认出"这一行是免责声明"的特征词，中英各留几个变体
_DISCLAIMER_MARKS = [
    "仅为普法参考", "不构成法律意见", "咨询执业律师",
    "GENERAL LEGAL INFORMATION", "DOES NOT CONSTITUTE LEGAL ADVICE",
]


def is_chinese(text):
    """问题里有汉字就当作中文提问。"""
    for ch in text:
        if "一" <= ch <= "鿿":
            return True
    return False


def _strip_disclaimer(reply):
    """把 AI 自己写的免责声明整行删掉（不管写的中文还是英文、写了几遍）。"""
    kept = []
    for line in reply.splitlines():
        up = line.upper()
        if any(mark in line or mark in up for mark in _DISCLAIMER_MARKS):
            continue
        kept.append(line)
    return "\n".join(kept).rstrip()


def _cn_source_to_en(reply):
    """英文回答里把（来源：xxx）改成 (Source: xxx)。"""
    return re.sub(r"[（(]\s*来源\s*[:：]\s*(.+?)\s*[)）]", r"(Source: \1)", reply)


def enforce(reply, question):
    """
    reply    : AI 生成的回答
    question : 用户原问题（用来判断该用哪种语言）
    返回：掰正格式后的回答
    """
    use_cn = is_chinese(question)

    body = _strip_disclaimer(reply)
    if not use_cn:
        body = _cn_source_to_en(body)

    disclaimer = DISCLAIMER_CN if use_cn else DISCLAIMER_EN
    return body + "\n\n" + disclaimer


# ---------- 语言一致性检查 ----------

def check_language(reply, question):
    """
    用户用什么语言提问，回答正文就必须是什么语言。
    返回 (是否合格, 问题说明)
    """
    body = _strip_disclaimer(reply)
    # 出处括号里出现外语法名是正常的，先剔掉再判断
    body = re.sub(r"[（(]\s*(?:来源|Source)\s*[:：].*?[)）]", "", body, flags=re.I)

    cjk = sum(1 for ch in body if "一" <= ch <= "鿿")

    if is_chinese(question):
        if cjk < 10:
            return False, "用户用中文提问，回答正文却不是中文，必须整段改用中文重写。"
    else:
        if cjk > 5:
            return False, "用户用英文提问，回答正文却出现了中文，必须整段改用英文重写（including all headings）。"
    return True, ""


VERSION = "v2"
