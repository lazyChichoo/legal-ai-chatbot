# -*- coding: utf-8 -*-
"""
端到端离线验收：问题 -> 检索 -> AI（替身）-> 三道防线 -> 回答

不联网、不花钱。跑法：
    python test_e2e.py
"""
import os
import sys
# 这一行必须在 import openai 之前：保证拿到的是 _stub/openai.py 那个假 AI 替身，
# 而不是机器上装的真 SDK。少了它，装过 openai 的电脑会报
# "module 'openai' has no attribute 'REPLIES'"，还以为是代码坏了。
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_stub"))

import openai   # 这里导入的是 _stub/openai.py 替身
import bot

FAIL = []


def case(name, question, replies, expect):
    openai.REPLIES[:] = replies
    openai.SENT[:] = []
    out = bot.answer(question, verbose=False)
    ok, why = expect(out, openai.SENT)
    print(("  OK   " if ok else "  FAIL ") + name + ("" if ok else "  <- " + why))
    if not ok:
        FAIL.append(name)


DISC = "开发团队不承担法律责任。"

print("=== 1. 拒付题：AI 漏讲例外，应被打回重写 ===")
case(
    "第一版漏讲例外 -> 第二版补齐后放行",
    "客户说沙发有个小划痕，整批货都不要了，还要拒付，这合法吗？",
    [
        # 第一次：只说对卖方有利的一半
        "根据CISG第25条，轻微瑕疵不构成根本违约，买方无权拒收全部货物。",
        # 第二次：补齐两个例外
        "根据CISG第25条，轻微瑕疵不构成根本违约。\n"
        "例外一（CISG第40条）：卖方明知瑕疵仍发货的，不得援引第38条、第39条抗辩。\n"
        "例外二（CISG第44条）：买方有合理理由延迟通知的，仍可按第50条要求减价，"
        "或要求损害赔偿（但不含利润损失），但不能拒收全部货物。",
    ],
    lambda out, sent: (
        ("第40条" in out and "第44条" in out and "第50条" in out
         and out.endswith(DISC) and len(sent) == 2),
        "两个例外没补齐或没重试；实际调用次数=%d" % len(sent)),
)

print()
print("=== 2. 拒付题：AI 编了一个知识库里没有的条文，应被打回 ===")
case(
    "编造 CISG 第99条 -> 打回 -> 改正后放行",
    "客户以质量不符为由拒付，我该怎么办？",
    [
        "根据CISG第99条，买方拒付无效。",
        "根据CISG第25条判断是否根本违约。\n"
        "例外一（CISG第40条）：卖方明知瑕疵不得抗辩。\n"
        "例外二（CISG第44条）：买方有合理理由的，保留第50条减价权，"
        "并可要求损害赔偿（不含利润损失）。",
    ],
    lambda out, sent: (
        ("第99条" not in out and "第40条" in out and len(sent) == 2),
        "编造的条文没被拦住；实际调用次数=%d" % len(sent)),
)

print()
print("=== 3. 拒付题：AI 报出具体赔偿金额，应被打回 ===")
case(
    "回答里出现 5万美元 -> 打回",
    "客户以质量不符拒付，我能索赔多少钱？",
    [
        "你可以索赔50,000美元。根据CISG第40条、第44条。",
        "赔偿额的算法是：合同价减去转售价，加合理附带费用。\n"
        "例外一 CISG第40条；例外二 CISG第44条，保留第50条减价权，"
        "并可要求损害赔偿（不含利润损失）。",
    ],
    lambda out, sent: (
        ("50,000" not in out and "美元" not in out and len(sent) == 2),
        "金额没被拦住；实际调用次数=%d" % len(sent)),
)

print()
print("=== 4. 停运题：关键事实不全，回答必须是追问而不是下结论 ===")
case(
    "直接下结论 -> 打回 -> 改成追问后放行",
    "货在海上，听说美国客户要破产，我能叫船公司别交货吗？",
    [
        "可以，你有权停运。",
        "要判断这件事，得先弄清三件事：\n"
        "1. 货物现在在哪；\n2. 全套正本提单现在谁持有；\n3. 付款方式是 T/T 还是 L/C。\n"
        "请补充后我再给结论。",
    ],
    lambda out, sent: (
        ("提单" in out and len(sent) == 2 and "有权停运" not in out),
        "追问流程没走通；实际调用次数=%d" % len(sent)),
)

print()
print("=== 4.5 拒付题：只说减价、吞掉损害赔偿，应被打回 ===")
case(
    "只说减价 -> 打回 -> 补齐损害赔偿后放行",
    "客户以质量不符拒付，我该怎么办？",
    [
        "例外一（CISG第40条）：卖方明知瑕疵不得抗辩。\n"
        "例外二（CISG第44条）：买方有合理理由的，仍可要求减价（第50条），但无权拒收全部。",
        "例外一（CISG第40条）：卖方明知瑕疵不得抗辩。\n"
        "例外二（CISG第44条）：买方仍可按第50条减价，并可要求损害赔偿（不含利润损失）。",
    ],
    lambda out, sent: (
        ("损害赔偿" in out and "利润" in out and len(sent) == 2),
        "只说减价没被拦住；实际调用次数=%d" % len(sent)),
)

print()
print("=== 5. 超出知识库范围：一次 API 都不该调 ===")
case(
    "问天气 -> 直接返回超范围提示，不调 API",
    "今天天气怎么样？",
    ["不该被调用"],
    lambda out, sent: (
        (len(sent) == 0 and "超出" in out and out.endswith(DISC)),
        "不该调 API 却调了 %d 次" % len(sent)),
)

print()
print("=== 6. 免责声明：AI 自己写了旧版，程序应换成法学组固定稿 ===")
case(
    "旧版声明被替换成固定稿",
    "客户拖欠货款，利息怎么算？",
    ["根据CISG第62条、第78条，可以主张利息。\n本回复仅为普法参考，不构成法律意见。"],
    lambda out, sent: (
        ("普法参考" not in out and out.endswith(DISC) and out.count("不承担法律责任") == 1),
        "免责声明没被换成固定稿"),
)

print()
print("=== 7. 超范围回答后面还带私货，程序必须砍干净（真接口实测踩到的）===")
_DIRTY = ("\u8be5\u95ee\u9898\u8d85\u51fa\u5f53\u524d\u77e5\u8bc6\u5e93\u8303\u56f4\uff0c"
          "\u5efa\u8bae\u54a8\u8be2\u5177\u5907\u6d89\u5916\u6267\u4e1a\u8d44\u8d28\u7684\u5f8b\u5e08\u3002\n\n"
          "\u3010\u5b9e\u52a1\u63d0\u793a\u3011\u9009\u6ce8\u518c\u5730\u65f6\uff0c"
          "\u53ef\u5148\u6bd4\u8f83\u4e24\u5dde\u7684\u5e74\u8d39\u548c\u7533\u62a5\u6d41\u7a0b\u3002")
case(
    "超范围却附赠实务提示 -> 私货被砍掉",
    "买方以质量不符拒付，我能要回货款吗？",
    [_DIRTY],
    lambda out, sent: (
        ("实务提示" not in out and "超出当前知识库范围" in out and out.endswith(DISC)),
        "私货没砍干净：" + out[:120]),
)
case(
    "英文超范围同样只留一句",
    "Can I register a company in Delaware?",
    ["This question is outside the current knowledge base. "
     "Please consult a qualified cross-border legal practitioner.\n\n"
     "[Practical tip] Compare the annual fees of both states first."],
    lambda out, sent: (
        ("Practical tip" not in out and "outside the current knowledge base" in out),
        "英文私货没砍掉：" + out[:120]),
)

print()
print("=== 8. AI 编造知识库里没有的比例，程序必须打回（真接口实测踩到的）===")
# 实测：条文写"违约金不超过预估损失的20-30%"，AI 正文只字不提，
# 转头在【实务提示】里自己发明了"10%-20%"。知识库里连 10 这个数都没有。
case(
    "实务提示里编了 10%-20% -> 打回 -> 改成照抄 20-30% 后放行",
    "合同里的违约金写多少比例合适？",
    [
        "违约金必须是对损害的合理预估（来源：UCC §2-718）。\n"
        "【实务提示】建议按合同金额的10%-20%约定违约金。",
        "违约金比例一般不超过预估实际损失的20-30%，且必须是对损害的合理预估"
        "（来源：UCC §2-718）。",
    ],
    lambda out, sent: (
        ("20-30%" in out and "10%" not in out and len(sent) == 2),
        "编造的比例没被打回；实际调用次数=%d；输出=%s" % (len(sent), out[:120])),
)
case(
    "照抄条文里的 20-30% 一次通过，不该被误杀",
    "合同里的违约金写多少比例合适？",
    ["违约金比例一般不超过预估实际损失的20-30%（来源：UCC §2-718）。"],
    lambda out, sent: (
        ("20-30%" in out and len(sent) == 1),
        "把条文里本来就有的比例误杀了；实际调用次数=%d" % len(sent)),
)
case(
    "回答里一个百分比都不写，也不该被拦",
    "合同里的违约金写多少比例合适？",
    ["违约金必须是对违约损害的合理预估，而非惩罚（来源：UCC §2-718）。"],
    lambda out, sent: (
        (len(sent) == 1 and "合理预估" in out),
        "没有百分比的回答被误杀了；实际调用次数=%d" % len(sent)),
)

print()
print("=" * 40)
print("全部通过" if not FAIL else "失败 %d 项：%s" % (len(FAIL), FAIL))
raise SystemExit(1 if FAIL else 0)
