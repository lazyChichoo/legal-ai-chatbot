# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv
from openai import OpenAI

from citation_guard import check, build_fix_message
from output_guard import enforce, check_language
from case_guard import directives as case_directives, check_all as case_check

load_dotenv()
client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com",
)

SYSTEM_PROMPT = """你是一个面向中小外贸从业者的中美跨境法律参考助手。

  【铁律，任何情况下不得违反】
  1. 你只能依据【参考条文】作答。条文里没写的规则一律不得使用——包括但不限于：该条文的适用范围、生效条件、例外情形、当事
  人所属国是否为缔约国、能否约定排除、与其他法律的关系。这些内容如果条文里没有原文，就当作你完全不知道，一个字都不许提。
  2. 严禁添加【参考条文】原文中没有的限定条件。凡是"前提是…""只有在…时""除非…""如果双方…""This applies
  if…""unless…""provided
  that…"这类限定语，只有当限定内容的原文就在【参考条文】里时才允许写；否则一律删除。宁可答得简单，也不许自己补限定。
  3. 每个法律结论后面必须紧跟出处，格式为（来源：条文编号）。出处只能从【参考条文】里已给出的编号中选，不许自造编号，也
  不许写"无相关条文"之类的假出处。
  4. 【参考条文】不足以回答用户问题时，只输出下面这一句，后面除免责声明外不许有任何其他内容：
     中文提问时：该问题超出当前知识库范围，建议咨询具备涉外执业资质的律师。
     英文提问时：This question is outside the current knowledge base. Please consult a qualified cross-border legal
  practitioner.
  5. 你最多可以给一条实务建议，必须单独成段。中文回答时以【实务提示】开头，英文回答时以 [Practical tip]
  开头，二选一，绝不许两个同时出现。这一段只许讲商业习惯，不许讲任何法律规则。
  6.用户用什么语言提问，你就用什么语言回答。整段回答自始至终必须是同一种语言，包括小标题和免责声明在内，绝不许中英混排。
  7. 回答结尾必须另起一行加免责声明：
     中文：本回复仅为普法参考，不构成法律意见，具体案件请咨询执业律师。
     English: This response is for general legal information only and does not constitute legal advice.
  8.只引用真正用得上的条文。【参考条文】里给了但和本题无关的，一个字都不许提，不许为了显得有依据而硬凑。

  【反例——绝对不许这样写】
  假设【参考条文】只给了"合同不需要书面形式"这一条，你写出"这适用于双方均为缔约国的情形，除非双方另有约定"——这是错误的，
  因为"缔约国""另有约定"这两个规则并不在参考条文里，是你自己脑补的。正确写法是只说"合同不需要书面形式（来源：…）"，其余
  一个字都不加。

  【输出前自检】
  写完后逐句检查：这句话陈述的每一个事实、条件、例外，能否在【参考条文】里找到对应原文？找不到的，整句删掉，不要改写、不
  要弱化保留。【实务提示】那一段不受此限。

  【回答风格】
  对方是没有法务的外贸小老板，说人话，先给结论再讲依据，不超过 300 字。
  """


def _is_chinese(text):
    """问题里有汉字就当作中文提问。"""
    for ch in text:
        if "一" <= ch <= "鿿":
            return True
    return False


def build_user_message(question, provisions, contract_text=None):
    lines = ["【参考条文】"]
    for p in provisions:
        lines.append("[" + p["source"] + "] " + p["text"])
    lines.append("")
    lines.append("【用户问题】")
    lines.append(question)
    lines.append("")

    # 法律硬规则：金额闸门 / 停运权追问 / CISG-UCC 分叉 / 拒付三要件
    extra = case_directives(question, contract_text)
    if extra:
        lines.append(extra)
        lines.append("")

    # 语言指令放最后一句，模型更听得进去
    if _is_chinese(question):
        lines.append("【本次回答语言】必须全程使用中文，包括小标题在内。")
    else:
        lines.append("【Answer language】Reply entirely in English, headings included. Do not use any Chinese.")
    return "\n".join(lines)


# 兜底话术只写正文，免责声明一律由 output_guard.enforce() 统一贴，
# 免得两处各留一份、改了一处漏一处。
FALLBACK_CN = "该问题超出当前知识库范围，建议向具备涉外执业资质的律师当面核实。"
FALLBACK_EN = ("This question is outside the current knowledge base. "
               "Please consult a qualified cross-border legal practitioner.")


def ask(question, provisions, contract_text=None, max_retry=1, verbose=True,
        trace=None):
    """
    trace: 传一个空 list 进来，就能拿到每一轮的审核明细
           [{"round":1, "raw":AI原话, "problems":[...], "passed":False}, ...]
           界面用它显示"程序拦了几次、拦了什么"。不传就跟以前一样。
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",
         "content": build_user_message(question, provisions, contract_text)},
    ]

    for attempt in range(max_retry + 1):
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.2,
        )
        reply = resp.choices[0].message.content

        problems = []

        cite_ok, cite_problems = check(reply, provisions)
        problems.extend(cite_problems)

        lang_ok, lang_problem = check_language(reply, question)
        if not lang_ok:
            problems.append(lang_problem)

        case_ok, case_problems = case_check(question, reply)
        problems.extend(case_problems)

        passed = cite_ok and lang_ok and case_ok
        if trace is not None:
            trace.append({
                "round": attempt + 1,
                "raw": reply,
                "problems": list(problems),
                "passed": passed,
            })

        if passed:
            return enforce(reply, question)

        if verbose:
            print("!! 第 %d 次生成被拦下：" % (attempt + 1))
            for p in problems:
                print("   - " + p)

        messages.append({"role": "assistant", "content": reply})
        messages.append({"role": "user", "content": build_fix_message(problems)})

    if verbose:
        print("!! 重试后仍不合格，改为输出兜底话术。")
    if trace is not None:
        trace.append({"round": None, "raw": None, "problems": ["重试后仍不合格，输出兜底话术"],
                      "passed": False})
    return enforce(FALLBACK_CN if _is_chinese(question) else FALLBACK_EN, question)


VERSION = "v5"
