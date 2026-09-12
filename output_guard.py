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


# ---------- 超范围回答：只许留那一句 ----------
# 铁律第 4 条要求：条文不足以回答时，只输出这一句，后面除免责声明外一个字都不许有。
# 实测模型不守：一边说"超出知识库范围"，一边接着给【实务提示】，还捎带一句
# 不相干的 UCC 提醒。这种回答比干脆拒答更糟——用户会以为后面那半是有依据的。
# 所以由程序兜底：只要认出这句话，后面全部砍掉，换成标准句。
OUT_OF_SCOPE_CN = "该问题超出当前知识库范围，建议咨询具备涉外执业资质的律师。"
OUT_OF_SCOPE_EN = ("This question is outside the current knowledge base. "
                   "Please consult a qualified cross-border legal practitioner.")

# ---------- 超范围拒答：分两种情况，话术不一样 ----------
# 判卷同学反馈：问"今天天气"回一句"超出当前知识库范围，建议咨询涉外律师"很怪
# —— 用户问的根本不是法律问题，让他去找律师没有意义。
# 这里按问题内容分两类，纯关键词判断，不调用 AI，一次 API 都不花。

SCOPE_LINE = "抱歉，本系统仅提供中美跨境货物买卖相关的合同审查、违约救济法律预审服务"

# ① 明显不是法律问题 —— 直接说不管这个，并指一条真正能解决的路
#    第二项是完整的"无法XX"短语，查询类和回答类动词不一样，硬套一个会别扭
_OFF_TOPIC = [
    (("天气", "气温", "下雨", "台风", "气象", "多少度", "下雪"),
     "无法查询天气", "你可以使用天气类 App、搜索引擎查询气象信息"),
    (("股票", "股价", "基金", "行情", "涨跌", "理财", "K线"),
     "无法查询股票行情", "你可以使用证券类 App 或财经网站查询"),
    (("汇率", "美元兑", "人民币兑", "换算成美元"),
     "无法查询汇率", "你可以使用银行 App 或财经网站查询实时汇率"),
    (("航班", "机票", "火车", "高铁", "车次", "几点的车"),
     "无法查询航班车次", "你可以使用出行类 App 查询"),
    (("菜谱", "做饭", "食谱", "怎么做菜", "晚饭吃", "午饭吃"),
     "无法回答餐饮问题", "你可以使用美食类 App 查询"),
    (("翻译成", "英文怎么说", "中文怎么说", "翻译一下"),
     "无法提供翻译服务", "你可以使用翻译类 App 或在线词典"),
    (("生病", "吃药", "医院", "医生", "症状", "挂号"),
     "无法回答医疗健康问题", "请咨询执业医师"),
    (("写代码", "编程", "报错", "bug", "python", "java", "代码"),
     "无法回答编程问题", "你可以查阅技术文档或开发者社区"),
]

# ② 是跨境买卖/法律问题，只是知识库没覆盖 —— 这种要老实说"没覆盖"，别推给别的 App。
#    词表要够口语：用户不会说"货物买卖合同纠纷"，只会说"客户不给钱""货扣着不发"。
_IN_DOMAIN = ("合同", "条款", "法律", "违约", "索赔", "赔偿", "仲裁", "起诉", "诉讼",
              "保全", "提单", "信用证", "关税", "报关",
              "货", "款", "钱", "付", "收", "发", "退",
              "买方", "卖方", "买家", "卖家", "客户", "老外", "供应商", "对方",
              "外贸", "出口", "进口", "订单", "批次", "结清", "尾款", "定金",
              "赖账", "欠", "拖", "催", "客人", "买主", "货主", "到港", "装船",
              "质量", "瑕疵", "验收", "交期", "违反")


def out_of_scope_reply(question):
    """检索一条都没命中时说什么。返回不含免责声明的正文，由 enforce() 补尾巴。"""
    q = question or ""
    for words, what, howto in _OFF_TOPIC:
        if any(w in q for w in words):
            return "%s，%s。%s。" % (SCOPE_LINE, what, howto)
    if any(w in q for w in _IN_DOMAIN):
        # 属于业务范围，但这一题知识库确实没有对应条文 —— 不能假装能答
        return ("这个问题属于跨境买卖法律范畴，但当前知识库中没有可直接引用的条文，"
                "系统不作推测。建议咨询具备涉外执业资质的律师，"
                "或把交易环节、争议点和合同约定描述得更具体一些再问一次。")
    return "%s，无法回答这个问题。建议咨询相应领域的专业人士。" % SCOPE_LINE


_OUT_MARKS = ["超出当前知识库范围", "超出知识库范围",
              "OUTSIDE THE CURRENT KNOWLEDGE BASE", "OUTSIDE THE KNOWLEDGE BASE"]


def is_out_of_scope(reply):
    """回答里出现了"超范围"那句话就算超范围回答。"""
    up = reply.upper()
    return any(m in reply or m in up for m in _OUT_MARKS)


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

    # 超范围回答：不管模型后面还写了什么，一律砍掉，只留标准那一句。
    if is_out_of_scope(body):
        return (OUT_OF_SCOPE_CN if use_cn else OUT_OF_SCOPE_EN) + "\n\n" + \
               (DISCLAIMER_CN if use_cn else DISCLAIMER_EN)

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
