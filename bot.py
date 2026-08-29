# -*- coding: utf-8 -*-
"""
系统主入口：一个问题进来，一段带出处的回答出去。

串起来的顺序（对应"AI 负责想，程序负责管"）：
    问题
     -> case_guard.pins()    判断这题属于哪类，决定哪些条文必须带
     -> kb.retrieve()        从知识库挑条文（相关的 + 必带的）
     -> llm.ask()            交给 AI，出来时已经过三道防线：
                                citation_guard 查出处真假
                                output_guard   查语言 + 贴固定免责声明
                                case_guard     查法律硬规则
    回答

检索一条都没命中时直接返回超范围提示，不浪费一次 API 调用。
"""

import case_guard
import citation_guard
import kb
import llm
import output_guard

# 超范围文案直接用 llm 里那份，全系统只有一处措辞


def answer(question, contract_text=None, top_k=3, verbose=False, items=None):
    """
    question      : 用户问题（中文或英文）
    contract_text : 合同全文，没有就传 None（用于判断适用 CISG 还是美国州法）
    top_k         : 最多带几条知识库条文（必带条文不占这个名额）
    返回：最终回答字符串
    """
    pin = case_guard.pins(question)
    provisions = kb.retrieve(question, items=items, top_k=top_k, pin=pin)

    if not provisions:
        use_cn = output_guard.is_chinese(question)
        base = llm.FALLBACK_CN if use_cn else llm.FALLBACK_EN
        return output_guard.enforce(base, question)

    return llm.ask(question, provisions, contract_text, verbose=verbose)


def explain(question, contract_text=None, top_k=3, items=None):
    """调试用：只看这题会命中哪些条文、触发哪些硬规则，不调 API。"""
    pin = case_guard.pins(question)
    provisions = kb.retrieve(question, items=items, top_k=top_k, pin=pin)
    return {
        "必带标签": pin,
        "命中条目": [p["no"] for p in provisions],
        "允许出现的编号": sorted(
            set().union(*[citation_guard.extract_refs(p["source"])
                          for p in provisions]) if provisions else set(),
            # 法律名可能是 None（认不出是哪部法），排序时当空串处理
            key=lambda r: (r[0] or "", r[1])),
        "硬规则指令": case_guard.directives(question, contract_text),
    }


VERSION = "v1"
