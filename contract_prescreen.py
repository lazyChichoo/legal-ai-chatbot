# -*- coding: utf-8 -*-
"""
contract_prescreen.py —— 合同初筛（读合同 → 比对规则清单 → 出风险报告）

规则来源：法学组《卖方违约救济合同审查规则清单》（2026-08-30 交付，6 条规则 + 扫描速查表）。
这里一行 AI 都不调，纯关键词扫描：同一份合同扫一百遍结果完全一样，答辩时能当场演示。

对外三个入口：
    read_contract(path)   把 .txt / .md / .docx 读成纯文本
    scan(text)            返回结构化结果（给界面同学用）
    report(text)          返回排版好的文字报告（给命令行 / 直接看）
"""

import os
import re
import zipfile


# ============================================================
# 一、规则表 —— 逐条对应规则清单，改规则只改这里
# ============================================================

HIGH = "高风险"
MID = "中风险"

# 每条规则：
#   no        规则编号
#   level     风险等级
#   title     缺什么
#   keywords  扫描关键词（OR 关系，命中任意一个即视为"合同里有这块内容"）
#   consequence / suggestion / law  报告里三段话
RULES = [
    {
        "no": 1,
        "level": HIGH,
        "title": "缺少卖方救济条款",
        "keywords": ["remedies", "seller's remedies", "sellers remedies",
                     "转售", "resale", "留置", "lien", "停运", "stoppage",
                     "价金请求", "price action"],
        "consequence": "法定权利仍然存在，但买方可能争议转售价格不合理、未给予履约机会等，"
                       "大幅增加卖方举证难度和诉讼成本。",
        "suggestion": "增加条款：如买方无正当理由拒收，卖方有权选择："
                      "①请求支付全部价款；②以合理方式转售并索赔差价及费用；"
                      "③留置后续批次货物直至欠款结清。",
        "law": "UCC §2-703；CISG Art.61",
    },
    {
        "no": 2,
        "level": MID,
        "title": "缺少违约金条款",
        "keywords": ["liquidated damages", "违约金", "约定损害赔偿",
                     "late payment penalty", "penalty clause"],
        "consequence": "违约时只能按实际损失索赔，卖方须自行举证损失金额（利润、附带费用等），"
                       "举证困难、耗时长、赔偿金额不确定。",
        "suggestion": "增加条款：任何一方违约的，应向守约方支付合同金额___%的约定违约金。"
                      "双方确认该金额系基于违约时预估损害的合理估算。"
                      "违约金不足以弥补实际损失的，守约方有权继续索赔差额。",
        "law": "UCC §2-718；CISG Art.74",
    },
    {
        "no": 3,
        "level": MID,
        "title": "缺少检验期与异议期条款",
        "keywords": ["inspection", "检验", "claim period", "异议期",
                     "notice of defect", "质量异议", "inspection period",
                     "验收期限"],
        "consequence": "买方可能在收货后任意时间提出质量异议，合理时间认定产生争议，"
                       "卖方难以主张买方已丧失声称不符的权利。",
        "suggestion": "增加条款：买方应在货物到达目的港后___日内完成检验，"
                      "并在发现瑕疵后___日内向卖方发出书面异议通知，详细说明不符之处。"
                      "逾期未提出书面异议的，视为货物完全符合合同约定。",
        "law": "UCC §2-602；CISG Art.38；CISG Art.39",
    },
    {
        "no": 4,
        "level": HIGH,
        "title": "缺少所有权保留条款",
        "keywords": ["title retention", "retention of title", "所有权保留",
                     "款清前所有权", "ownership reserved", "title does not pass",
                     "所有权归卖方"],
        "consequence": "货物所有权在交付时即转移给买方，即使买方尚未付款。"
                       "卖方无法行使取回权或留置权，只能依赖价金请求和损害赔偿追款。",
        "suggestion": "增加条款：在买方全额支付货款之前，货物所有权归卖方所有。"
                      "买方未付清全部款项的，卖方有权取回货物，且买方应承担取回费用。"
                      "所有权保留不影响风险转移和买方对货物的妥善保管义务。",
        "law": "中国《民法典》第641条；UCC Article 2（title retention）",
    },
    {
        "no": 5,
        "level": MID,
        "title": "缺少法律适用条款",
        "keywords": ["governing law", "适用法律", "适用法",
                     "this agreement shall be governed by", "applicable law",
                     "准据法"],
        "consequence": "CISG 自动适用（中美均为缔约国），对卖方相对有利；"
                       "但如买方格式合同排除 CISG，则适用美国州法 UCC，"
                       "UCC 完美交付规则对卖方更不利。",
        "suggestion": "增加条款：本合同适用《联合国国际货物销售合同公约》（CISG）。"
                      "如 CISG 未规定的事项，适用中华人民共和国法律。"
                      "或约定争议提交 CIETAC / HKIAC 仲裁。",
        "law": "CISG Art.1；中国《法律适用法》第41条",
    },
    {
        "no": 6,
        "level": MID,
        "title": "不可抗力条款过于笼统",
        "keywords": ["force majeure", "不可抗力", "免责",
                     "excused from performance"],
        # 规则 6 是唯一的"反向"规则：命中上面的关键词说明合同里【有】不可抗力条款，
        # 但如果没有列举具体情形，条款就是一句空话 —— 那才触发风险。
        "consequence": "港口罢工、海运延误、疫情等是否属于不可抗力产生重大争议，"
                       "双方可能陷入长期诉讼，卖方可能被迫承担本可免责的损失。",
        "suggestion": "增加条款：不可抗力包括但不限于：战争、地震、洪水、火灾、政府禁令、流行病。"
                      "以下情形不属于不可抗力：港口罢工、海运延误、船期变更、原材料涨价。"
                      "遭受不可抗力的一方应在___日内书面通知对方，并提供官方证明。",
        "law": "CISG Art.79；中国《民法典》第180条",
    },
]

# 规则 6 用：算不算"列举了具体情形"
_FM_SPECIFIC = [
    "战争", "war", "地震", "earthquake", "洪水", "flood", "火灾", "fire",
    "政府禁令", "government order", "government prohibition", "禁运", "embargo",
    "流行病", "疫情", "epidemic", "pandemic", "自然灾害", "natural disaster",
    "act of god", "台风", "typhoon", "海啸", "tsunami", "暴动", "riot",
    "恐怖", "terrorism", "terrorist",
]

# 规则 6 用：有没有写"反面排除"（哪些不算不可抗力）
_FM_EXCLUDE = [
    "不属于不可抗力", "不构成不可抗力", "不视为不可抗力",
    "shall not constitute force majeure", "does not constitute force majeure",
    "shall not be deemed force majeure",
]


# ============================================================
# 二、扫描
# ============================================================

_ASCII_KW = re.compile(r"^[A-Za-z][A-Za-z\' -]*[A-Za-z]$")
_KW_CACHE = {}


def _kw_pattern(kw):
    """英文关键词编译成带词边界的正则，编译结果缓存下来。"""
    pat = _KW_CACHE.get(kw)
    if pat is None:
        pat = re.compile(r"\b" + re.escape(kw) + r"\b", re.I)
        _KW_CACHE[kw] = pat
    return pat


def _find_hits(text, keywords):
    """
    在合同里找关键词。返回 [(关键词, 出现位置), ...]，同一个词只记第一次。

    中文直接按子串比。
    英文必须整词匹配，不能按子串 —— 踩过的坑：
      "lien"（留置）会命中 "client"，"war"（战争）会命中 "warehouse"，
      一个仓库地址就能让规则误判成"合同里写了留置权"。
    """
    upper = text.upper()
    hits = []
    for kw in keywords:
        if _ASCII_KW.match(kw):
            m = _kw_pattern(kw).search(text)
            pos = m.start() if m else -1
        else:
            pos = upper.find(kw.upper())
        if pos >= 0:
            hits.append((kw, pos))
    return sorted(hits, key=lambda h: h[1])


def _excerpt(text, pos, span=45):
    """截命中关键词前后一小段原文，报告里给人看'到底命中在哪'。"""
    start = max(0, pos - span // 3)
    end = min(len(text), pos + span)
    piece = text[start:end].replace("\n", " ").replace("\r", " ")
    piece = re.sub(r"\s+", " ", piece).strip()
    return ("…" if start > 0 else "") + piece + ("…" if end < len(text) else "")


def _check_rule(rule, text):
    """
    扫一条规则，返回 dict：
      no / level / title / triggered / hits / detail
    triggered=True 表示这条是风险项，False 表示合同里已经写到了。
    """
    hits = _find_hits(text, rule["keywords"])
    out = {
        "no": rule["no"],
        "level": rule["level"],
        "title": rule["title"],
        "hits": [{"keyword": k, "pos": p, "excerpt": _excerpt(text, p)}
                 for k, p in hits],
        "consequence": rule["consequence"],
        "suggestion": rule["suggestion"],
        "law": rule["law"],
        "note": "",
    }

    if rule["no"] != 6:
        # 规则 1-5：关键词全部未命中 → 触发
        out["triggered"] = not hits
        out["detail"] = ("合同全文未出现任何相关表述"
                         if not hits else
                         "已写到（命中 %d 个关键词）" % len(hits))
        return out

    # 规则 6：先看有没有不可抗力条款，再看有没有列举具体情形
    # 2026-09-01 法学组答复：合同【完全没有】不可抗力条款，定为中风险。
    # 在此之前这一支不判定（规则清单只写了"有但笼统"），现按法学组口径触发。
    if not hits:
        out["triggered"] = True
        out["title"] = "缺少不可抗力条款"      # 这一支不是"笼统"，是整条没有，标题要改
        out["detail"] = "合同里完全没有不可抗力条款"
        out["note"] = "法学组认定：完全缺失不可抗力条款属中风险。"
        out["suggestion"] = ("合同里没有不可抗力条款，建议整条补入 —— "
                             + rule["suggestion"].replace("增加条款：", "", 1))
        out["consequence"] = ("战争、疫情、政府禁令等意外事件发生时，卖方无条款可援引，"
                              "可能被认定为违约并承担全部损失。"
                              "虽然 CISG Art.79 有法定免责，但举证门槛高、适用范围窄，"
                              "远不如合同明确约定可靠。")
        return out

    spec = _find_hits(text, _FM_SPECIFIC)
    out["specific"] = [k for k, _ in spec]
    if not spec:
        out["triggered"] = True
        out["detail"] = "有不可抗力条款，但没有列举任何具体情形"
        return out

    out["triggered"] = False
    out["detail"] = "已列举具体情形：" + "、".join(k for k, _ in spec[:8])
    if not _find_hits(text, _FM_EXCLUDE):
        out["note"] = ("只做了正面列举，没有反面排除（没写明港口罢工、海运延误等【不算】不可抗力）。"
                       "规则清单没把这一项列为独立风险，这里只作提示。")
    return out


# 附加提示：不在规则清单的 6 条里，是从知识库第 15 条补的。
# 单独放在 notes 里，法学组要是不认，删掉这一段即可，不影响 6 条主规则。
# 注意：这里必须允许跨行。真实合同就是会把一句话拆成两三行，
# 早先把 \n 也排除掉，结果 "…Sale of Goods\nshall not apply." 整句认不出来。
# 换行在匹配前统一压成空格，句号仍然当边界，防止把两句话连起来误判。
_CISG_EXCLUDE_PAT = re.compile(
    r"(?:exclude[sd]?|shall not apply|does not apply|不适用|排除)"
    r"[^。.；;]{0,120}"
    r"(?:CISG|United Nations Convention|联合国国际货物销售合同公约|销售合同公约)"
    r"|(?:CISG|United Nations Convention|联合国国际货物销售合同公约|销售合同公约)"
    r"[^。.；;]{0,120}"
    r"(?:is excluded|are excluded|shall not apply|does not apply|不适用|被排除|予以排除)",
    re.I)


def _extra_notes(text):
    notes = []
    m = _CISG_EXCLUDE_PAT.search(re.sub(r"\s+", " ", text))
    if m:
        notes.append({
            "level": HIGH,
            "title": "合同明确排除了 CISG",
            "detail": "原文：" + re.sub(r"\s+", " ", m.group(0)).strip(),
            "why": "排除 CISG 后本合同走美国州法 UCC。UCC 的'完美交付规则'允许买方因"
                   "任何微小不符拒收全部货物，对卖方明显不利。这一条不在规则清单的 6 条里，"
                   "是按知识库第 15 条补的提示。",
        })
    return notes


def scan(text):
    """
    扫描合同，返回结构化结果（界面同学直接用这个）：
      {
        "length":  合同字数,
        "rules":   [每条规则的结果, ...]        顺序 = 规则 1..6
        "risks":   [triggered 的那些, 高风险在前],
        "passed":  [没触发的那些],
        "notes":   [附加提示],
        "summary": {"高风险": n, "中风险": n, "通过": n},
      }
    """
    text = text or ""
    results = [_check_rule(r, text) for r in RULES]
    risks = [r for r in results if r["triggered"]]
    risks.sort(key=lambda r: (0 if r["level"] == HIGH else 1, r["no"]))
    passed = [r for r in results if not r["triggered"]]
    return {
        "length": len(text),
        "rules": results,
        "risks": risks,
        "passed": passed,
        "notes": _extra_notes(text),
        "summary": {
            HIGH: sum(1 for r in risks if r["level"] == HIGH),
            MID: sum(1 for r in risks if r["level"] == MID),
            "通过": len(passed),
        },
    }


# ============================================================
# 三、出报告
# ============================================================

_MARK = {HIGH: "[高风险]", MID: "[中风险]"}


def report(text, show_passed=True):
    """把 scan() 的结果排成一份能直接给人看的风险报告。"""
    r = scan(text)
    L = []
    L.append("=" * 56)
    L.append("合同风险初筛报告")
    L.append("=" * 56)
    L.append("合同长度：%d 字" % r["length"])
    L.append("扫描规则：%d 条（法学组《卖方违约救济合同审查规则清单》）" % len(RULES))
    L.append("")
    s = r["summary"]
    L.append("汇总：高风险 %d 项 / 中风险 %d 项 / 已覆盖 %d 项"
             % (s[HIGH], s[MID], s["通过"]))
    L.append("")

    if not r["risks"]:
        L.append("本次扫描未发现缺失项，6 条规则全部命中。")
    for item in r["risks"]:
        L.append("-" * 56)
        L.append("%s 规则%d · %s" % (_MARK[item["level"]], item["no"], item["title"]))
        L.append("  发现　　：" + item["detail"])
        L.append("  什么后果：" + item["consequence"])
        L.append("  建议怎么补：" + item["suggestion"])
        L.append("  法律依据：" + item["law"])
        if item.get("note"):
            L.append("  备注　　：" + item["note"])

    for n in r["notes"]:
        L.append("-" * 56)
        L.append("%s %s（附加提示）" % (_MARK[n["level"]], n["title"]))
        L.append("  " + n["detail"])
        L.append("  " + n["why"])

    if show_passed and r["passed"]:
        L.append("-" * 56)
        L.append("[已覆盖] 以下规则合同里已经写到：")
        for item in r["passed"]:
            L.append("  规则%d · %s —— %s" % (item["no"], item["title"], item["detail"]))
            for h in item["hits"][:2]:
                L.append("      命中「%s」第 %d 字：%s"
                         % (h["keyword"], h["pos"], h["excerpt"]))
            if item.get("note"):
                L.append("      备注：" + item["note"])

    L.append("=" * 56)
    L.append("本报告为程序按规则清单逐条扫描的结果，仅作初步风险提示，")
    L.append("不构成正式法律意见，不可替代执业律师服务。")
    return "\n".join(L)


# ============================================================
# 四、读合同文件
# ============================================================

_W_P = re.compile(r"</w:p\s*>")
_W_T = re.compile(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", re.S)
_W_BR = re.compile(r"<w:(?:br|tab)\s*/>")
_TAG = re.compile(r"<[^>]+>")


def _docx_to_text(path):
    """
    不装任何第三方库，直接把 .docx 当 zip 拆开读正文。
    docx 本质就是个 zip，正文在 word/document.xml 里。
    """
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    lines = []
    for para in _W_P.split(xml):
        para = _W_BR.sub(" ", para)
        chunks = _W_T.findall(para)
        if not chunks:
            continue
        line = "".join(_TAG.sub("", c) for c in chunks)
        line = (line.replace("&amp;", "&").replace("&lt;", "<")
                    .replace("&gt;", ">").replace("&quot;", '"')
                    .replace("&apos;", "'"))
        lines.append(line)
    return "\n".join(lines)


def _plain_to_text(path):
    """纯文本文件，编码挨个试：UTF-8 → 带 BOM 的 UTF-8 → GBK。"""
    raw = open(path, "rb").read()
    for enc in ("utf-8", "utf-8-sig", "gbk", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "ignore")


def read_contract(path):
    """读一份合同，返回纯文本。支持 .txt / .md / .docx。"""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        return _docx_to_text(path)
    if ext in (".txt", ".md", ""):
        return _plain_to_text(path)
    if ext == ".doc":
        raise ValueError("旧版 .doc 读不了，请在 Word 里另存为 .docx 或 .txt 再试。")
    if ext == ".pdf":
        raise ValueError("PDF 暂不支持，请复制正文存成 .txt，或另存为 .docx。")
    raise ValueError("不认识的文件类型：%s（支持 .txt / .md / .docx）" % ext)


def check_file(path, show_passed=True):
    """一步到位：给个文件路径，返回风险报告文字。"""
    return report(read_contract(path), show_passed=show_passed)


VERSION = "v1"


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法：python contract_prescreen.py 合同文件.docx")
        raise SystemExit(1)
    print(check_file(sys.argv[1]))
