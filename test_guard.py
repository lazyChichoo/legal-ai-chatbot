# -*- coding: utf-8 -*-
"""
出处校验器的离线测试 —— 不调 API、不花钱、秒出结果。
直接跑：python test_guard.py
"""

from citation_guard import check

# 假装这次检索到了这两条
PROVISIONS = [
    {"source": "《联合国国际货物销售合同公约》(CISG) 第三十九条",
     "text": "买方对货物不符合同，必须在发现或理应发现后一段合理时间内通知卖方，"
             "说明不符合同情形的性质，否则丧失声称货物不符合同的权利。"},
    {"source": "UCC § 2-706",
     "text": "Seller may resell the goods concerned and recover the difference "
             "between the resale price and the contract price."},
]

CASES = [
    ("正常引用中文条文",
     "买方超过合理期间未提出异议的，丧失以质量不符主张权利的资格（来源：CISG 第39条）。",
     True),

    ("正常引用 UCC",
     "You may resell the goods and claim the price difference (Source: UCC §2-706).",
     True),

    ("编造条文编号",
     "卖方可以宣告合同无效（来源：CISG 第99条）。",
     False),

    ("假出处话术",
     "根据一般法律原则，你可以要求买方赔偿（来源：无相关条文可依据）。",
     False),

    ("中文数字写法也要能认出来",
     "买方须及时通知（来源：《联合国国际货物销售合同公约》第三十九条）。",
     True),

    ("混进一个没给过的条文",
     "你可以转售（来源：UCC §2-706），并要求利息（来源：CISG 第78条）。",
     False),
]

passed = 0
for name, reply, should_pass in CASES:
    ok, problems = check(reply, PROVISIONS)
    result = "通过" if ok else "拦下"
    expect = "通过" if should_pass else "拦下"
    mark = "OK  " if ok == should_pass else "FAIL"
    print("[%s] %-16s 期望%s，实际%s" % (mark, name, expect, result))
    if problems:
        for p in problems:
            print("        └─ " + p)
    if ok == should_pass:
        passed += 1

print()
print("%d / %d 条测试通过" % (passed, len(CASES)))
