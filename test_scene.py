# -*- coding: utf-8 -*-
"""
场景识别离线验收：本题属于知识库哪一条。

法学组口径：场景就是知识库那 20 条，大类写在【场景标签】里。
这一层不调 AI，所以不联网、不花钱。跑法：
    python test_scene.py
"""
import os
import sys
# 这一行必须在 import openai 之前：保证拿到的是 _stub/openai.py 那个假 AI 替身，
# 而不是机器上装的真 SDK。少了它，装过 openai 的电脑会报
# "module 'openai' has no attribute 'REPLIES'"，还以为是代码坏了。
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_stub"))

import openai   # _stub/openai.py 替身，第 5 组要用
import bot
import kb

FAIL = []


def ck(name, cond, why=""):
    print(("  [通过] " if cond else "  [失败] ") + name + ("" if cond else "  <- " + why))
    if not cond:
        FAIL.append(name)


ITEMS = kb.load()


def head(q, top_k=3):
    prov = kb.retrieve(q, items=ITEMS, top_k=top_k,
                       pin=__import__("case_guard").pins(q))
    return bot.scene_header(prov, q), bot.scenes(prov)


print("=== 第 1 组：知识库本身的场景标签 ===")
ck("一共 20 条", len(ITEMS) == 20, "实际 %d 条" % len(ITEMS))
ck("每条都有场景标签", all(x["场景标签"] for x in ITEMS),
   "缺标签的：%s" % [x["no"] for x in ITEMS if not x["场景标签"]])
tags = {}
for x in ITEMS:
    tags.setdefault(x["场景标签"], []).append(x["no"])
ck("只有三类场景", set(tags) == {"实体救济", "合同审查", "程序应急"}, str(set(tags)))
ck("实体救济 10 条（第1-10条）", tags.get("实体救济") == list(range(1, 11)),
   str(tags.get("实体救济")))
ck("合同审查 6 条（第11-16条）", tags.get("合同审查") == list(range(11, 17)),
   str(tags.get("合同审查")))
ck("程序应急 4 条（第17-20条）", tags.get("程序应急") == list(range(17, 21)),
   str(tags.get("程序应急")))
ck("每类都在 SCENE_EN 里有英文说法",
   set(tags) <= set(bot.SCENE_EN), "缺：%s" % (set(tags) - set(bot.SCENE_EN)))

print()
print("=== 第 2 组：典型问题认得出主场景 ===")
h, sc = head("客户说沙发有个小划痕，整批货都不要了，这合法吗？")
ck("拒收瑕疵题 -> 主场景第9条", sc and sc[0]["no"] == 9, str([s["no"] for s in sc]))
ck("拒收瑕疵题 -> 标为实体救济", sc and sc[0]["scene"] == "实体救济", str(sc[:1]))
ck("拒收瑕疵题 -> 场景行以【本题场景】开头", h.startswith("【本题场景】"), h[:30])

h, sc = head("货在海上，听说美国客户公司要破产，我能叫船公司别交货吗？")
ck("停运题 -> 命中第3条", 3 in [s["no"] for s in sc], str([s["no"] for s in sc]))

h, sc = head("合同没写所有权保留，钱没收到货权就转移了吗？")
ck("所有权保留题 -> 主场景第14条", sc and sc[0]["no"] == 14, str([s["no"] for s in sc]))
ck("所有权保留题 -> 标为合同审查", sc and sc[0]["scene"] == "合同审查", str(sc[:1]))

h, sc = head("仲裁赢了美国买方，裁决在美国能强制执行吗？")
ck("仲裁执行题 -> 主场景第18条", sc and sc[0]["no"] == 18, str([s["no"] for s in sc]))
ck("仲裁执行题 -> 标为程序应急", sc and sc[0]["scene"] == "程序应急", str(sc[:1]))

print()
print("=== 第 3 组：排版与边界 ===")
h, sc = head("客户说沙发有个小划痕，整批货都不要了，这合法吗？")
ck("多条命中时只有一个【本题场景】", h.count("【本题场景】") == 1, h)
ck("其余的标成【相关场景】", h.count("【相关场景】") == len(sc) - 1, h)
ck("场景行里带了条目标题", "拒收" in h, h)
ck("场景行行数 = 命中条数", len(h.splitlines()) == len(sc),
   "%d 行 / %d 条" % (len(h.splitlines()), len(sc)))

h, sc = head("今天广州天气怎么样？")
ck("超出知识库范围 -> 没有场景可报", h == "" and sc == [], repr(h))
ck("空条文列表也不炸", bot.scene_header([], "随便问问") == "")

print()
print("=== 第 4 组：英文提问不许混中文 ===")
# 注意：这里挑的是一道英文检索确实能命中的题。
# 知识库的关键词、标题、典型问法全是中文，所以大部分英文提问检索不到东西——
# 那是检索层的已知缺口（见 kb.py 的说明），不是场景行本身的问题。
qen = "Buyer rejected the whole lot over a tiny scratch. Is that legal?"
prov = kb.retrieve(qen, items=ITEMS, top_k=3,
                   pin=__import__("case_guard").pins(qen))
hen = bot.scene_header(prov, qen)
ck("英文提问也能认出场景", hen != "", "一条都没命中")
ck("英文场景行里没有汉字",
   not any("一" <= c <= "鿿" for c in hen), hen)
ck("英文场景行用 [Scenario] 开头", hen.startswith("[Scenario]"), hen[:30])
ck("英文场景行里有大类说法", "remedies" in hen or "review" in hen or "procedure" in hen, hen)
ck("英文场景行报出了条目编号", "#9" in hen, hen)

print()
print("=== 第 5 组：接到主流程里 ===")
Q = "客户说沙发有个小划痕，整批货都不要了，这合法吗？"
GOOD = ("根据CISG第25条，轻微瑕疵不构成根本违约。\n"
        "例外一（CISG第40条）：卖方明知瑕疵仍发货的，不得援引第38条、第39条抗辩。\n"
        "例外二（CISG第44条）：买方有合理理由延迟通知的，仍可按第50条要求减价，"
        "或要求损害赔偿（但不含利润损失），但不能拒收全部货物。")

openai.REPLIES[:] = [GOOD]
openai.SENT[:] = []
out = bot.answer(Q, verbose=False)
ck("answer() 默认带场景行", out.startswith("【本题场景】"), out[:40])
ck("场景行没顶掉正文", "第40条" in out and "第44条" in out, out[:120])
ck("免责声明还在最后", out.rstrip().endswith("开发团队不承担法律责任。"), out[-40:])

openai.REPLIES[:] = [GOOD]
openai.SENT[:] = []
out2 = bot.answer(Q, verbose=False, show_scene=False)
ck("show_scene=False 时不带场景行", not out2.startswith("【本题场景】"), out2[:40])

openai.REPLIES[:] = [GOOD]
openai.SENT[:] = []
info = bot.answer_detailed(Q)
ck("answer_detailed 给出 scenes", info["scenes"] and info["scenes"][0]["no"] == 9,
   str(info["scenes"]))
ck("answer_detailed 给出 scene_header", info["scene_header"].startswith("【本题场景】"),
   info["scene_header"][:30])
ck("answer_detailed 的 answer 不重复贴场景行",
   not info["answer"].startswith("【本题场景】"), info["answer"][:40])

openai.REPLIES[:] = []
openai.SENT[:] = []
info2 = bot.answer_detailed("今天广州天气怎么样？")
ck("超范围时 scenes 为空", info2["scenes"] == [], str(info2["scenes"]))
ck("超范围时 scene_header 为空", info2["scene_header"] == "", repr(info2["scene_header"]))
ck("超范围时一次 API 都没调", info2["called_api"] is False and len(openai.SENT) == 0)

print()
print("=" * 46)
if FAIL:
    print("失败 %d 项：%s" % (len(FAIL), "；".join(FAIL)))
else:
    print("全部通过")
print("=" * 46)
