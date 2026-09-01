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


# ---------- 本题属于哪个场景 ----------
# 法学组口径：场景就是知识库那 20 条本身，大类写在每条的【场景标签】里
#（实体救济 10 条 / 合同审查 6 条 / 程序应急 4 条）。
# 这一行完全由程序算出来——哪几条被检索命中是程序自己挑的，照实报即可，
# 不经过 AI，也就不存在编造场景的可能。
SCENE_EN = {
    "实体救济": "substantive remedies",
    "合同审查": "contract review",
    "程序应急": "procedure & emergency response",
}


def scenes(provisions):
    """把命中的条文整理成场景清单：[{"no":9,"title":...,"scene":...}, ...]，
    排第一个的就是本题的主场景。"""
    return [{"no": p["no"], "title": p.get("title", ""),
             "scene": p.get("scene", "")} for p in provisions]


def scene_header(provisions, question):
    """
    场景行的文字版，贴在回答最前面。
    一条都没命中就返回空串 —— 那说明超出知识库范围，本来就没有场景可报。

    英文提问时只报编号和大类，不翻译条目标题：知识库只有中文标题，
    硬翻等于我自己造一版法律术语译名，等法学组给了中英对照表再补。
    """
    if not provisions:
        return ""
    use_cn = output_guard.is_chinese(question)
    lines = []
    for i, p in enumerate(provisions):
        if use_cn:
            tag = "【本题场景】" if i == 0 else "【相关场景】"
            lines.append("%s知识库第%d条 · %s（%s）"
                         % (tag, p["no"], p.get("title", ""), p.get("scene", "")))
        else:
            tag = "[Scenario]" if i == 0 else "[Related] "
            en = SCENE_EN.get(p.get("scene", ""), p.get("scene", ""))
            lines.append("%s Knowledge base entry #%d (%s)" % (tag, p["no"], en))
    return "\n".join(lines)


def answer(question, contract_text=None, top_k=3, verbose=False, items=None,
           show_scene=True):
    """
    question      : 用户问题（中文或英文）
    contract_text : 合同全文，没有就传 None（用于判断适用 CISG 还是美国州法）
    top_k         : 最多带几条知识库条文（必带条文不占这个名额）
    show_scene    : 回答开头是否带"本题属于哪个场景"，界面要自己排版就传 False
    返回：最终回答字符串
    """
    pin = case_guard.pins(question)
    provisions = kb.retrieve(question, items=items, top_k=top_k, pin=pin)

    if not provisions:
        use_cn = output_guard.is_chinese(question)
        base = llm.FALLBACK_CN if use_cn else llm.FALLBACK_EN
        return output_guard.enforce(base, question)

    reply = llm.ask(question, provisions, contract_text, verbose=verbose)
    if show_scene:
        head = scene_header(provisions, question)
        if head:
            reply = head + "\n\n" + reply
    return reply


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


def answer_detailed(question, contract_text=None, top_k=3, items=None):
    """
    给界面用：一次拿到最终回答 + 全部审核明细。
    返回 dict：
      answer        最终回答（注意：这里【不带】场景行，跟 bot.answer() 不一样，
                    界面用下面两个字段自己排版，免得同一句话显示两遍）
      scenes        本题命中的场景清单，排第一个的是主场景
                    [{"no":9,"title":"…","scene":"实体救济"}, ...]
      scene_header  上面那份的现成文字版，懒得自己排版就直接贴在回答前面
      provisions    本次喂给 AI 的条文（含知识库编号）
      pins          触发了哪些必带条文规则
      law           合同法律适用的判断结果
      trace         每一轮的审核明细（程序拦了什么）
      called_api    有没有真的调用 AI（超范围时为 False）
    """
    pin = case_guard.pins(question)
    provisions = kb.retrieve(question, items=items, top_k=top_k, pin=pin)
    verdict, evidence = case_guard.detect_governing_law(contract_text)

    info = {
        "provisions": provisions,
        "scenes": scenes(provisions),
        "scene_header": scene_header(provisions, question),
        "pins": pin,
        "law": {"verdict": verdict, "evidence": evidence},
        "trace": [],
        "called_api": False,
    }

    if not provisions:
        use_cn = output_guard.is_chinese(question)
        base = llm.FALLBACK_CN if use_cn else llm.FALLBACK_EN
        info["answer"] = output_guard.enforce(base, question)
        return info

    trace = []
    info["called_api"] = True
    info["answer"] = llm.ask(question, provisions, contract_text,
                             verbose=False, trace=trace)
    info["trace"] = trace
    return info


# 法律适用判断结果的人话说明，界面直接显示
LAW_LABEL = {
    "cisg_excluded": "合同已明确排除 CISG，本题按美国《统一商法典》(UCC) 第二编回答",
    "state_law_only": "合同只选了美国某州法但没排除 CISG —— 仍然适用 CISG（这是高频误解）",
    "unknown": "没有提供合同法律适用条款，按缔约国默认适用 CISG",
}


VERSION = "v3"
