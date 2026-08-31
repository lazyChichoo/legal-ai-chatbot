# -*- coding: utf-8 -*-
"""
考卷验收.py —— 拿法学组的考卷逐题检查"程序有没有把对的条文捞出来"

【这个脚本查什么、不查什么，先说清楚，别对外说过头】
查的是**检索这一环**：题目进来 -> case_guard.pins() 硬塞必带条文 -> kb.retrieve() 打分挑条文。
检查两件事：
  1. 主场景对不对 —— 排第一的是不是知识库第 N 条（考卷第 N 题就是照第 N 条出的）
  2. 条文够不够 —— 标准答案要求引用的条文，是不是都在捞出来的条文里
不查的是 AI 写出来的那段话写得好不好 —— 那要真调 API，另说。

但这一环恰恰是最关键的：捞不到的条文，citation_guard 根本不允许 AI 引用。
所以"条文覆盖率"= AI 最多能答对多少的天花板。

跑法：  python 考卷验收.py "考卷1.0.docx"
        python 考卷验收.py "考卷1.0.docx" "考卷2.0（长问法版）.docx"
        python 考卷验收.py                     # 不给文件名就读 法学组交付/ 里的 txt
考卷可以直接给 .docx，不用先转成文本 —— 内部借 倒成文本.py 拆开读。
"""

import os
import re
import sys

import case_guard
import kb

try:
    import 倒成文本
except ImportError:      # 没有那个工具就只支持 .txt
    倒成文本 = None

_HERE = os.path.dirname(os.path.abspath(__file__))
_PAPERS = [
    os.path.join(_HERE, "法学组交付", "考卷1.0_短问法版.txt"),
    os.path.join(_HERE, "法学组交付", "考卷2.0_长问法版.txt"),
]


# ============================================================
# 一、把"条文"这种五花八门的写法统一成一个个可比对的记号
# ============================================================
# 同一条法在考卷和知识库里写法可能略有差别（带不带括号注释、带不带"中国"两个字），
# 所以不做整段字符串比对，而是把两边都拆成"记号"再比集合。

# 法条写法五花八门，这里统一拆成一个个"记号"再比集合，不做整段字符串比对。
# 难点：知识库里常写成 "UCC §2-606（接受货物）、§2-602（拒收通知）" ——
# 第二个 §2-602 前面并没有 UCC 两个字。所以要顺着读，记住"当前在讲哪部法"。

_LAW = re.compile(r"CISG|UCC|UCP\s*600")
_ART = re.compile(r"Art\.?\s*(\d+)")
_SEC = re.compile(r"§\s*(\d+-\d+(?:\(\d+\))?)")
_UCP_ART = re.compile(r"UCP\s*600\s*第\s*(\d+)\s*条")

_RULES = [
    (re.compile(r"民法典》?\s*第\s*(\d+)\s*条"),     "民法典-%s"),
    (re.compile(r"法律适用法》?\s*第\s*(\d+)\s*条"), "法律适用法-%s"),
    (re.compile(r"民事诉讼法》?\s*第\s*(\d+)\s*条"), "民诉法-%s"),
    (re.compile(r"FAA[）)]?\s*第\s*(\d+)\s*条"),     "FAA-%s"),
    (re.compile(r"第\s*([IVX]+)\s*条"),               "纽约公约条-%s"),
]

# 不带编号的，出现即算
_FLAGS = [
    (re.compile(r"Incoterms"),                          "Incoterms2020"),
    (re.compile(r"长臂管辖"),                            "长臂管辖"),
    (re.compile(r"纽约公约"),                            "纽约公约"),
    (re.compile(r"民事诉讼法》?\s*涉外编"),              "民诉法-涉外编"),
    (re.compile(r"UCC\s*Article\s*2\s*[（(]?\s*title"), "UCC-Article2-所有权保留"),
]

# 顺着读的时候，这些记号同时匹配：法名 / Art.N / §x-y
_SCAN = re.compile(r"(CISG|UCC|UCP\s*600)|Art\.?\s*(\d+)|§\s*(\d+-\d+(?:\(\d+\))?)")


def cites(text):
    """从一段文字里抽出所有条文记号，返回集合。"""
    got = set()

    law = None
    for m in _SCAN.finditer(text):
        name, art, sec = m.group(1), m.group(2), m.group(3)
        if name:
            law = re.sub(r"\s+", "", name).upper()
        elif art:
            got.add("%s-%s" % (law or "CISG", art))     # Art.N 只在 CISG 里用
        elif sec:
            got.add("%s-%s" % ("UCC", sec))             # §x-y 只在 UCC 里用

    for m in _UCP_ART.findall(text):
        got.add("UCP600-%s" % m)
    for pat, tpl in _RULES:
        for m in pat.findall(text):
            got.add(tpl % m)
    for pat, tag in _FLAGS:
        if pat.search(text):
            got.add(tag)
    return got


# ============================================================
# 二、读考卷
# ============================================================

_Q_HEAD = re.compile(r"^第(\d+)题\s*$")
# 卷尾那张"考卷结构速查表"是给人看的汇总，不是题目，读到它就停
_TAIL = re.compile(r"^附[：:]|考卷结构速查表")
_ANSWER = re.compile(r"^标准答案应引用[：:](.+)$")
_LEVEL = re.compile(r"^风险等级[：:](.+)$")


def _read(path):
    """考卷正文。.docx 直接拆开读，.txt 按文本读。"""
    if path.lower().endswith(".docx"):
        if 倒成文本 is None:
            raise RuntimeError("读 .docx 需要 倒成文本.py 放在同一个文件夹里")
        return 倒成文本.docx_to_text(path)
    with open(path, encoding="utf-8") as f:
        return f.read()


def load_paper(path):
    """返回 [{"no":1, "question":"...", "want":"...", "level":"..."}, ...]"""
    items, cur = [], None
    if True:
        for raw in _read(path).splitlines():
            line = raw.strip()
            if _TAIL.search(line):
                break
            if not line:
                continue
            m = _Q_HEAD.match(line)
            if m:
                if cur:
                    items.append(cur)
                cur = {"no": int(m.group(1)), "question": "", "want": "", "level": ""}
                continue
            if cur is None:            # 卷首标题行
                continue
            m = _ANSWER.match(line)
            if m:
                cur["want"] = m.group(1).strip()
                continue
            m = _LEVEL.match(line)
            if m:
                cur["level"] = m.group(1).strip()
                continue
            cur["question"] += line
    if cur:
        items.append(cur)
    return items


# ============================================================
# 三、逐题跑
# ============================================================

def run_one(q, items):
    """跑一道题，返回这题的检查结果。全程不联网、不调 API。"""
    pin = case_guard.pins(q["question"])
    provs = kb.retrieve(q["question"], items=items, top_k=3, pin=pin)

    nos = [p["no"] for p in provs]
    main = nos[0] if nos else None
    found = set()
    for p in provs:
        found |= cites(p["source"])
    want = cites(q["want"])

    return {
        "no": q["no"],
        "pin": pin,
        "nos": nos,
        "main_ok": main == q["no"],
        "in_top": q["no"] in nos,
        "want": want,
        "missing": sorted(want - found),
        "cover": (len(want & found), len(want)),
    }


def run_paper(path, items):
    name = os.path.basename(path)
    paper = load_paper(path)
    print("=" * 70)
    print("《%s》  共 %d 题" % (name, len(paper)))
    print("=" * 70)

    rows = [run_one(q, items) for q in paper]

    print("题号 | 主场景 | 第N条在不在 | 条文覆盖 | 捞到的条 | 缺的条文")
    print("-" * 70)
    for r in rows:
        hit, total = r["cover"]
        print("%4d | %-6s | %-11s | %5s | %-10s | %s"
              % (r["no"],
                 "对" if r["main_ok"] else "错",
                 "在" if r["in_top"] else "不在",
                 "%d/%d" % (hit, total),
                 ",".join(str(n) for n in r["nos"]) or "空",
                 "、".join(r["missing"]) or "-"))

    n = len(rows)
    main_ok = sum(1 for r in rows if r["main_ok"])
    in_top = sum(1 for r in rows if r["in_top"])
    full = sum(1 for r in rows if not r["missing"])
    hit = sum(r["cover"][0] for r in rows)
    tot = sum(r["cover"][1] for r in rows)
    print("-" * 70)
    print("主场景判对        ：%d/%d  (%.0f%%)" % (main_ok, n, 100.0 * main_ok / n))
    print("对应条进了检索结果：%d/%d  (%.0f%%)" % (in_top, n, 100.0 * in_top / n))
    print("条文一条不缺      ：%d/%d  (%.0f%%)" % (full, n, 100.0 * full / n))
    print("条文总覆盖率      ：%d/%d  (%.0f%%)" % (hit, tot, 100.0 * hit / tot))
    print()
    return rows


def main(argv):
    papers = argv[1:] or _PAPERS
    items = kb.load()
    print("知识库 %d 条\n" % len(items))
    all_rows = []
    for p in papers:
        if not os.path.exists(p):
            print("找不到考卷：%s" % p)
            continue
        all_rows += run_paper(p, items)

    if not all_rows:
        return 1
    bad = [r for r in all_rows if not r["main_ok"] or r["missing"]]
    print("=" * 70)
    print("合计 %d 题，有问题的 %d 题" % (len(all_rows), len(bad)))
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
