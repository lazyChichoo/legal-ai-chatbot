# -*- coding: utf-8 -*-
"""
输出格式强制器

作用：AI 生成完之后，程序动手把格式掰正，不指望它自觉。
     1) 免责声明按提问语言强制替换（AI 写错了就删掉重贴）
     2) 英文回答里的"（来源：xxx）"统一改成"(Source: xxx)"

纯本地字符串处理，不调 API。
"""

import re

# 法学组交付的固定免责声明，一字不改。
# 这段是程序贴上去的，不是让 AI 自己写的——AI 写的版本一律先删掉再贴这个。
DISCLAIMER_CN = (
    "本系统提供的法律信息仅供参考，不构成正式法律意见，不可替代执业律师服务。"
    "风险等级仅为初步提示，不代表确定性法律判断。涉及重大法律事项，请咨询执业律师。"
    "因使用本系统信息产生的损失，开发团队不承担法律责任。"
)

# 英文版是对上面那段的翻译，法学组尚未出具官方英文本，待其确认后替换。
DISCLAIMER_EN = (
    "The legal information provided by this system is for reference only. "
    "It does not constitute formal legal advice and cannot replace the services "
    "of a licensed attorney. Risk ratings are preliminary indications only and do "
    "not represent definitive legal conclusions. For significant legal matters, "
    "please consult a licensed attorney. The development team accepts no legal "
    "liability for any loss arising from use of information provided by this system."
)

# 认出"这一行是免责声明"的特征词，中英各留几个变体。
# 旧版本的特征词也留着，免得 AI 写出旧话术时删不掉。
# 每个词都必须"只可能出现在免责声明里"。
# 教训：早先放了"咨询执业律师"这种日常短语，结果正文里
# "建议咨询执业律师"整行被当成声明删掉，回答只剩一句声明。
_DISCLAIMER_MARKS = [
    # 新版（法学组固定稿）
    "法律信息仅供参考", "不构成正式法律意见", "不可替代执业律师服务",
    "风险等级仅为初步提示", "开发团队不承担法律责任",
    "PROVIDED BY THIS SYSTEM IS FOR REFERENCE ONLY",
    "CANNOT REPLACE THE SERVICES",
    "RISK RATINGS ARE PRELIMINARY",
    "ACCEPTS NO LEGAL LIABILITY",
    # 旧版（防止模型沿用旧话术）
    "仅为普法参考", "不构成法律意见",
    "GENERAL LEGAL INFORMATION ONLY", "DOES NOT CONSTITUTE LEGAL ADVICE",
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


VERSION = "v3"
