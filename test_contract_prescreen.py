# -*- coding: utf-8 -*-
"""
contract_prescreen 的离线自测。不联网、不调 API，随便跑。
用法：python test_contract_prescreen.py
"""

import os
import zipfile

import contract_prescreen as cc

OK = FAIL = 0
TMP = []


def check(name, cond, extra=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  [通过] " + name)
    else:
        FAIL += 1
        print("  [失败] " + name + ("  " + extra if extra else ""))


def nos(items):
    return sorted(i["no"] for i in items)


print("\n=== 第 1 组：空合同 / 白纸一张 ===")
r = cc.scan("")
check("空合同：规则 1-6 全部报缺失", nos(r["risks"]) == [1, 2, 3, 4, 5, 6], str(nos(r["risks"])))
# 2026-09-01 法学组答复：完全没有不可抗力条款 = 中风险，所以规则 6 现在也要触发
check("空合同：规则 6 触发（完全没有不可抗力条款）",
      6 in nos(r["risks"]))
check("空合同：规则 6 判为中风险",
      [x for x in r["risks"] if x["no"] == 6][0]["level"] == cc.MID)
check("空合同：规则 6 说的是「完全没有」不是「过于笼统」",
      "完全没有" in [x for x in r["risks"] if x["no"] == 6][0]["detail"])
check("空合同：高风险 2 项（规则 1、4）", r["summary"][cc.HIGH] == 2)
check("空合同：中风险 4 项（规则 2、3、5、6）", r["summary"][cc.MID] == 4)
check("None 也不炸", cc.scan(None)["length"] == 0)


print("\n=== 第 2 组：六条全写到的合同 ===")
FULL = """
销售合同 SALES CONTRACT

第 8 条 卖方救济 Seller's Remedies
如买方无正当理由拒收，卖方有权请求支付全部价款，或以合理方式转售并索赔差价，
并对后续批次货物行使留置权。Seller may exercise stoppage in transit.

第 9 条 违约金 Liquidated Damages
任何一方违约的，应向守约方支付合同金额 10% 的约定违约金。

第 10 条 检验与异议 Inspection
买方应在货物到达目的港后 15 日内完成检验，并在发现瑕疵后 7 日内发出书面异议通知。

第 11 条 所有权保留
在买方全额支付货款之前，货物所有权归卖方所有。Title does not pass until full payment.

第 12 条 适用法律 Governing Law
本合同适用《联合国国际货物销售合同公约》(CISG)。

第 13 条 不可抗力 Force Majeure
不可抗力包括但不限于：战争、地震、洪水、火灾、政府禁令、流行病。
以下情形不属于不可抗力：港口罢工、海运延误、船期变更、原材料涨价。
"""
r = cc.scan(FULL)
check("完整合同：一条风险都不报", r["risks"] == [], str(nos(r["risks"])))
check("完整合同：6 条全部标为已覆盖", len(r["passed"]) == 6)
check("完整合同：没有附加提示", r["notes"] == [])
rep = cc.report(FULL)
check("报告里写了「未发现缺失项」", "未发现缺失项" in rep)


print("\n=== 第 3 组：规则 6 —— 有不可抗力条款但笼统 ===")
VAGUE = FULL.replace(
    "不可抗力包括但不限于：战争、地震、洪水、火灾、政府禁令、流行病。\n"
    "以下情形不属于不可抗力：港口罢工、海运延误、船期变更、原材料涨价。",
    "因不可抗力导致无法履行的，遭受方免责。")
r = cc.scan(VAGUE)
check("笼统不可抗力：规则 6 触发", 6 in nos(r["risks"]), str(nos(r["risks"])))
check("笼统不可抗力：只有规则 6 触发", nos(r["risks"]) == [6], str(nos(r["risks"])))
r6 = [x for x in r["risks"] if x["no"] == 6][0]
check("规则 6 说清了原因", "没有列举任何具体情形" in r6["detail"])

# 只做正面列举、没写反面排除 —— 不触发风险，但要给提示
HALF = FULL.replace(
    "以下情形不属于不可抗力：港口罢工、海运延误、船期变更、原材料涨价。", "")
r = cc.scan(HALF)
r6 = [x for x in r["rules"] if x["no"] == 6][0]
check("只正面列举：规则 6 不触发", not r6["triggered"])
check("只正面列举：留了'没写反面排除'的备注", "反面排除" in r6["note"])


print("\n=== 第 4 组：大小写 / 中英混写都要认出来 ===")
check("GOVERNING LAW 全大写能命中",
      5 not in nos(cc.scan("ARTICLE 12. GOVERNING LAW: New York law.")["risks"]))
check("Retention of Title 能命中",
      4 not in nos(cc.scan("Clause 9 Retention of Title applies.")["risks"]))
check("只写中文'检验'也能命中",
      3 not in nos(cc.scan("买方应于到货后检验货物。")["risks"]))
check("没写的还是要报出来",
      1 in nos(cc.scan("ARTICLE 12. GOVERNING LAW: New York law.")["risks"]))


print("\n=== 第 4.5 组：英文关键词不许按子串乱命中（真踩过的坑）===")
WH = "Payment: T/T 30 days after arrival at Buyer's warehouse."
r6 = [x for x in cc.scan(WH + " 5. FORCE MAJEURE 因不可抗力免责。")["rules"]
      if x["no"] == 6][0]
check("warehouse 不算 war（战争）", r6["triggered"], str(r6.get("specific")))
check("client 不算 lien（留置）",
      1 in nos(cc.scan("Notice to Buyer's client shall be in writing.")["risks"]))
check("整词还是要命中：Seller may exercise a lien",
      1 not in nos(cc.scan("Seller may exercise a lien over the goods.")["risks"]))
check("firearm 不算 fire（火灾）",
      [x for x in cc.scan("不可抗力免责。Firearms are excluded from the goods.")["rules"]
       if x["no"] == 6][0]["triggered"])


print("\n=== 第 5 组：附加提示 —— 合同排除了 CISG ===")
EXCL = FULL.replace(
    "本合同适用《联合国国际货物销售合同公约》(CISG)。",
    "The United Nations Convention on Contracts for the International Sale of "
    "Goods shall not apply to this Agreement.")
r = cc.scan(EXCL)
check("排除 CISG：出附加提示", len(r["notes"]) == 1, str(r["notes"]))
check("排除 CISG：标为高风险", r["notes"] and r["notes"][0]["level"] == cc.HIGH)
check("中文写法也认：'排除适用CISG'",
      len(cc.scan("双方约定排除适用CISG。")["notes"]) == 1)
check("正常适用 CISG 不误报", cc.scan(FULL)["notes"] == [])
MULTILINE = ("This Agreement shall be governed by the laws of the State of New York.\n"
             "The United Nations Convention on Contracts for the International Sale of\n"
             "Goods shall not apply.")
check("排除条款被换行拆成三行也要认出来",
      len(cc.scan(MULTILINE)["notes"]) == 1, str(cc.scan(MULTILINE)["notes"]))


print("\n=== 第 6 组：报告排版 ===")
rep = cc.report("这是一份什么条款都没有的合同。")
for must in ["合同风险初筛报告", "[高风险]", "[中风险]",
             "什么后果", "建议怎么补", "法律依据", "不构成正式法律意见"]:
    check("报告里有「%s」" % must, must in rep)
check("报告里带了规则编号", "规则1" in rep and "规则4" in rep)


print("\n=== 第 7 组：读文件 ===")
p_txt = "_t_contract.txt"
open(p_txt, "w", encoding="utf-8").write(FULL)
TMP.append(p_txt)
check("读 UTF-8 txt", "所有权保留" in cc.read_contract(p_txt))

p_gbk = "_t_contract_gbk.txt"
open(p_gbk, "wb").write(FULL.encode("gbk"))
TMP.append(p_gbk)
check("读 GBK txt（Windows 记事本另存的默认编码）",
      "所有权保留" in cc.read_contract(p_gbk))

# 手搓一个最小 docx：docx 就是个 zip，正文在 word/document.xml
p_docx = "_t_contract.docx"
body = "".join(
    '<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>' % line
    for line in FULL.strip().split("\n"))
doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
       '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
       '<w:body>%s</w:body></w:document>' % body)
with zipfile.ZipFile(p_docx, "w") as z:
    z.writestr("word/document.xml", doc.encode("utf-8"))
TMP.append(p_docx)
txt = cc.read_contract(p_docx)
check("读 docx：拿到正文", "所有权保留" in txt)
check("读 docx：段落没粘成一坨", txt.count("\n") >= 10, repr(txt[:60]))
check("读 docx 后扫描结果和 txt 一致",
      nos(cc.scan(txt)["risks"]) == nos(cc.scan(FULL)["risks"]))
check("check_file 一步到位", "合同风险初筛报告" in cc.check_file(p_txt))

try:
    cc.read_contract("x.pdf")
    check("PDF 要给出人话提示", False)
except ValueError as e:
    check("PDF 要给出人话提示", "PDF" in str(e))
try:
    cc.read_contract("x.doc")
    check("旧版 .doc 要给出人话提示", False)
except ValueError as e:
    check("旧版 .doc 要给出人话提示", "另存为" in str(e))

for f in TMP:
    if os.path.exists(f):
        os.remove(f)


print("\n" + "=" * 46)
print("通过 %d 项，失败 %d 项" % (OK, FAIL))
print("全部通过" if FAIL == 0 else "有失败项，看上面")
print("=" * 46)
