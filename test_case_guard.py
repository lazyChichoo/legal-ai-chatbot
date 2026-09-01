# -*- coding: utf-8 -*-
"""离线测试 case_guard，不花 API 钱。直接 python test_case_guard.py"""

import case_guard as cg

fail = 0


def check(name, got, want):
    global fail
    if got == want:
        print("  OK   %s" % name)
    else:
        fail += 1
        print("  FAIL %s\n       实际=%r\n       期望=%r" % (name, got, want))


print("== 一、金额闸门 ==")
拦 = ["赔偿金额为 $50,000。", "买方应支付 10万美元。", "损失约十万美元。",
     "合同价款 USD 120,000 未付。", "违约金人民币50000元。"]
放 = [
    "赔偿额按合同价与转售价之间的差额计算，另加合理的附带费用。",
    "依据 UCC § 2-706 转售并主张差价。",
    "买方应在收到货物后 30 天内提出书面异议。",
    "违约金上限为合同总价的百分之三十。",
    "逾期付款可另行主张利息，年利率按 6% 计。",
    "见《联合国国际货物销售合同公约》第三十九条。",
]
for s in 拦:
    ok, _ = cg.check_no_amount(s)
    check("该拦下：" + s[:16], ok, False)
for s in 放:
    ok, probs = cg.check_no_amount(s)
    check("该放行：" + s[:16], (ok, probs), (True, []))

print()
print("== 二、停运权闸门 ==")
q1 = "买方拖欠货款，我能不能把在途的货拦下来？"
check("识别为停运题", cg.is_transit_question(q1), True)
check("三件事全缺", len(cg.transit_facts_missing(q1)), 2)  # "在途"命中了货物位置
q2 = ("货已装船在途，全套正本提单还在我手里，付款方式是 L/C，"
      "买方现在说不要货了，我能行使停运权吗？")
check("事实齐全就不再追问", cg.transit_facts_missing(q2), [])
bad = "你可以立即通知承运人停止交付货物，依据 CISG 第七十一条第二款。"
ok, _ = cg.check_transit_reply(q1, bad)
check("事实不全却下结论 → 拦下", ok, False)
good = ("要判断能不能停运，先得知道三件事：货物现在在哪、全套正本提单谁持有、"
        "付款方式是 T/T 还是 L/C。请补充这三项信息。")
ok, _ = cg.check_transit_reply(q1, good)
check("规规矩矩追问 → 放行", ok, True)
check("非停运题不触发", cg.check_transit_reply("买方拒付怎么办", bad), (True, ""))

print()
print("== 三、法律适用分叉 ==")
c1 = ("Article 15. Governing Law. This Contract shall be governed by the laws of "
      "the State of New York, USA. The United Nations Convention on Contracts for "
      "the International Sale of Goods shall not apply.")
v, _ = cg.detect_governing_law(c1)
check("英文明确排除 CISG", v, "cisg_excluded")

c2 = "第十五条 法律适用：本合同适用美国纽约州法律，排除适用《联合国国际货物销售合同公约》。"
v, _ = cg.detect_governing_law(c2)
check("中文明确排除 CISG", v, "cisg_excluded")

c3 = ("Article 15. This Contract shall be governed by the laws of the State of "
      "California, without regard to conflict of laws principles.")
v, ev = cg.detect_governing_law(c3)
check("只选州法没排除 → 仍走 CISG", v, "state_law_only")

v, _ = cg.detect_governing_law("")
check("没给合同 → 默认 CISG", v, "unknown")

print()
print("== 四、拒付三要件 ==")
check("识别拒付题", cg.is_rejection_question("买方以质量不符为由拒付货款"), True)
check("普通题不触发", cg.is_rejection_question("CISG 和 UCC 有什么区别"), False)

print()
print("== 五、指令拼装 ==")
d = cg.directives(q1, None)
check("停运题带上追问指令", "停运权关键事实核对" in d, True)
check("同时带上默认 CISG 指令", "默认适用 CISG" in d, True)
d2 = cg.directives("买方以质量不符拒付，我能要回货款吗？", c1)
check("拒付题带上三要件", "三要件核对" in d2, True)
check("排除 CISG 的合同走 UCC", "不许引用 CISG" in d2, True)
check("不该带停运指令", "停运权关键事实" in d2, False)

# 2026-09-01 打真接口打出来的两个假阳性，都是"中文放行、英文拦截"的不对称
print()
print("== 六、中英不对称的假阳性（真接口实测踩到的）==")
import citation_guard as cig

# ① "UCC Article 2" 是《统一商法典》第二编，篇章名，不是法条号
check("UCC Article 2 不算引用编号", cig.extract_refs("under UCC Article 2 the perfect tender rule applies"), set())
check("中文'第二编'本来就不算", cig.extract_refs("按《统一商法典》(UCC) 第二编判断"), set())
check("真 UCC 条号照样认得", ("UCC", "2-601") in cig.extract_refs("see UCC 2-601"), True)
check("CISG Art.2 不受牵连", ("CISG", "2") in cig.extract_refs("CISG Article 2 excludes consumer sales"), True)

_EN_Q = "The buyer rejected my goods claiming non-conformity. Is there a notice deadline?"
_EN_OK = ("Under Art.39 the buyer must give notice within a reasonable time. "
          "Under Art.40 the seller cannot rely on Art.38 and Art.39 if it knew of the defect. "
          "Under Art.44 the buyer may reduce the price under Art.50 and claim damages, "
          "excluding lost profits.")
# ② 英文写 lost profits / profits 都算讲到了利润损失，不许卡在一种写法上
check("英文 'lost profits' 算讲全了", cg.check_reject_reply(_EN_Q, _EN_OK)[0], True)
check("英文 'loss of profit' 也算", cg.check_reject_reply(_EN_Q, _EN_OK.replace("lost profits", "loss of profit"))[0], True)
check("真漏了利润这半句还是要拦",
      cg.check_reject_reply(_EN_Q, _EN_OK.replace(" and claim damages, excluding lost profits", ""))[0], False)

print()
print("=" * 40)
print("全部通过" if fail == 0 else "有 %d 项没过" % fail)
