# -*- coding: utf-8 -*-
"""
【这个文件是干嘛的】
回答一个质疑："看回答看不出到底用没用知识库，是不是 AI 自己瞎编的？"

这个脚本把中间过程全部打印出来：
    用户问题 -> 检索挑中了哪几条 -> 实际发给 AI 的原文长什么样
全程不调用 AI 接口，不花钱，不需要 API key。跑完自己看，一目了然。

用法：  python 证明用到知识库.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_stub"))

import kb
import case_guard
import llm

QUESTIONS = [
    "美国客户收到货说有划痕要退全部货款，我该怎么办",
    "客户破产了货还在海上，能拦下来吗",
    "How do I enforce a CIETAC award against a US buyer?",
    "我想在北京买套房，首付要多少",     # 故意问知识库外的
]


def main():
    items = kb.load()
    print("知识库装载：共 %d 条（来源 kb_raw.txt，法学组交付）\n" % len(items))

    for q in QUESTIONS:
        print("=" * 72)
        print("【用户问题】" + q)

        pins = case_guard.pins(q)
        provisions = kb.retrieve(q, items, pin=pins)

        if not provisions:
            print("\n【检索结果】一条都没命中（都低于 %.1f 分）" % kb.MIN_SCORE)
            print("【接下来】程序直接返回「超出知识库范围」，")
            print("          根本不会调用 AI —— 所以 AI 没机会瞎编。\n")
            continue

        idf = kb._idf(items)
        print("\n【检索挑中了这几条】（分数越高越相关，%.1f 分以下直接不要）" % kb.MIN_SCORE)
        for p in provisions:
            item = [x for x in items if x["no"] == p["no"]][0]
            mark = ""
            for k in pins:
                if p["no"] in kb.PINNED.get(k, []):
                    mark = "  ← 必带条文（%s 类问题强制带上）" % k
            print("   第%-3d条  %6.2f分  %s%s"
                  % (p["no"], kb._score(item, q, idf), p["title"], mark))

        msg = llm.build_user_message(q, provisions)
        print("\n【实际发给 AI 的原文】↓↓↓ 全文照抄，一个字没删")
        print("   " + "-" * 66)
        for ln in msg.splitlines():
            print("   | " + ln)
        print("   " + "-" * 66)
        print("【看这里】上面这一大段全是从知识库抄过去的。")
        print("          AI 收到的就是这些，它答的每一条都得在这里面找得到。\n")

    print("=" * 72)
    print("结论：")
    print("  1. 每次提问，程序先在 20 条知识库里打分排序，挑出最相关的几条；")
    print("  2. 挑中的条文【原文】拼进发给 AI 的消息里，AI 才开始答；")
    print("  3. 一条都没挑中时，程序直接拒答，连 AI 都不调；")
    print("  4. AI 答完之后 citation_guard 还会核对一遍：")
    print("     它引的法条编号如果不在上面这些条文里，回答会被打回重来。")


main()
