# -*- coding: utf-8 -*-
"""
【这个文件是干嘛的】
回答一个更刁的质疑：
    "知识库是发给 AI 了，可 AI 会不会根本不看，自己凭本事答？"

做法：同一个问题问两遍。
    第一遍：用真的知识库
    第二遍：把知识库里一个数字偷偷改掉（20-30% 改成 7%），别的一个字不动
如果第二遍的回答跟着变成 7%，就证明 AI 是照着本地知识库答的 —— 因为
真实的美国法里没有"7%"这个说法，AI 自己编不出来，只可能是从文件里抄的。

会真的调用 DeepSeek 接口，2 次，几分钱。需要 .env 里有 API key。

用法：  python 篡改测试.py
"""
import os
import re
import sys

# 必须确保用的是真 SDK，不是 _stub 里的假替身
sys.path = [p for p in sys.path if "_stub" not in p]

import kb
import llm

QUESTION = "合同里的违约金写多少比例合适？"

TAMPER_FROM = "违约金比例一般不超过预估实际损失的20-30%"
TAMPER_TO = "违约金比例一般不超过预估实际损失的7%"


def load_tampered():
    """读一份被改过的知识库（只在内存里改，不动硬盘上的文件）。"""
    with open(kb.KB_PATH, "r", encoding="utf-8") as f:
        raw = f.read()
    if TAMPER_FROM not in raw:
        print("！知识库里找不到要改的那句话，测试没法做。")
        print("  可能是法学组更新了 kb_raw.txt，请改 TAMPER_FROM 再跑。")
        sys.exit(1)
    raw = raw.replace(TAMPER_FROM, TAMPER_TO)

    tmp = kb.KB_PATH + ".tampered"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(raw)
    items = kb.load(tmp)
    os.remove(tmp)              # 用完立刻删，绝不留在硬盘上污染真知识库
    return items


def run(label, items):
    print("=" * 70)
    print(label)
    print("=" * 70)
    provisions = kb.retrieve(QUESTION, items)
    print("检索挑中：" + ", ".join("第%d条" % p["no"] for p in provisions))

    # 把喂给 AI 的原文里那个比例打出来，确认篡改真的生效了
    for p in provisions:
        for line in p["text"].splitlines():
            if "违约金比例一般不超过" in line:
                print("喂给 AI 的原文写的是：" + line.strip()[:40] + " …")

    reply = llm.ask(QUESTION, provisions, verbose=False)
    print("\n【AI 的回答】")
    for ln in reply.splitlines():
        print("  " + ln)
    print()
    return reply


def main():
    print("问题：" + QUESTION + "\n")
    a = run("第一遍：真的知识库（原文写 20-30%）", kb.load())
    b = run("第二遍：偷偷把 20-30% 改成 7%，别的没动", load_tampered())

    print("=" * 70)
    print("【结论】")

    # 【别再犯一次】老版本这里写的是 ("20%" in a)，结果被 AI 在实务提示里
    # 自己发明的"10%-20%"匹配到了，明明没照抄条文却报"是"，给了个假绿灯。
    # 现在只认区间连写（20-30% / 20%-30% / 20%到30%），不认孤零零一个 20%。
    hit2030 = bool(re.search(r"20\s*[%％]?\s*[-—~－到至]\s*30\s*[%％]", a))
    hit7 = bool(re.search(r"(?<!\d)7\s*[%％]", b))

    print("  第一遍回答里出现 20-30% 这个区间：" + ("是" if hit2030 else "否"))
    print("  第二遍回答里出现 7%              ：" + ("是" if hit7 else "否"))

    # 顺带查一遍：两次回答里有没有条文里根本没有的比例（AI 自己编的）
    import citation_guard as cg
    for label, reply, ki in (("第一遍", a, kb.load()), ("第二遍", b, load_tampered())):
        ok, why = cg.check_numbers(reply, kb.retrieve(QUESTION, ki))
        print("  %s 有没有编造的比例        ：%s" % (label, "没有" if ok else "有！" + why[0]))

    print()
    if hit7:
        print("  ✅ 改了知识库，回答就跟着变。")
        print("     真实美国法里没有「7%」这个说法，AI 自己编不出来，")
        print("     只可能是从本地 kb_raw.txt 里抄的 —— 知识库确实在起作用。")
    else:
        print("  ⚠ 第二遍没跟着变，需要人工看一眼上面两段回答的差别。")
        print("     （也可能是 AI 这次没提具体比例，多跑一次看看。）")


main()
