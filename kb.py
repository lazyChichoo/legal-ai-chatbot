# -*- coding: utf-8 -*-
"""
知识库装载 + 检索层。

职责只有两件：
1. 把 kb_raw.txt（法学组交付的 20 条）解析成程序能用的结构；
2. 拿到一个用户问题，挑出该喂给 AI 的几条，组装成 llm.ask() 要的
   provisions 格式：[{"source": ..., "text": ...}, ...]

一条铁规矩（关系到 citation_guard 会不会误杀）：
    provisions 里的 "source" 必须原样放【法律依据】那一行，
    绝对不许写成"知识库第9条"这种。
    因为 citation_guard 只从 source 里提取允许出现的法条编号；
    source 写成"第9条"，会导致 CISG 40/44/50 全被判成编造出处。
"""

import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
KB_PATH = os.path.join(_HERE, "kb_raw.txt")

# 一条知识里认哪些字段
_FIELDS = ["编号", "标题", "场景标签", "风险等级", "典型问法",
           "回答", "法律依据", "合同审查点", "关键词", "风险提示"]

_FIELD_PAT = re.compile(r"^【(" + "|".join(_FIELDS) + r")】[ \t]*(.*)$")
_SPLIT_PAT = re.compile(r"^[─—\-]{10,}\s*$")


def _parse_block(block):
    """把一段文字解析成一条知识。认不出编号的返回 None。"""
    item = {f: "" for f in _FIELDS}
    cur = None
    for line in block.splitlines():
        m = _FIELD_PAT.match(line)
        if m:
            cur = m.group(1)
            # 同名字段重复出现（法学组第9条有过两行【标题】），保留先出现的那个
            if item[cur]:
                cur = None
                continue
            item[cur] = m.group(2).strip()
        elif cur:
            item[cur] += ("\n" + line.rstrip())

    if not item["编号"]:
        return None

    n = re.search(r"\d+", item["编号"])
    item["no"] = int(n.group()) if n else 0
    item["关键词表"] = [w.strip() for w in re.split(r"[,，、]", item["关键词"]) if w.strip()]
    for f in _FIELDS:
        item[f] = item[f].strip()
    return item


def load(path=None):
    """读取知识库，返回列表，按编号排序。"""
    with open(path or KB_PATH, "r", encoding="utf-8") as f:
        raw = f.read()

    blocks, cur = [], []
    for line in raw.splitlines():
        if _SPLIT_PAT.match(line):
            blocks.append("\n".join(cur))
            cur = []
        else:
            cur.append(line)
    blocks.append("\n".join(cur))

    items = [x for x in (_parse_block(b) for b in blocks) if x]
    items.sort(key=lambda x: x["no"])
    return items


# ---------- 必带条文 ----------
# 某类问题不管检索排名如何，这几条必须塞进去。
# 理由：case_guard 会强制 AI 说出特定法条编号，如果知识库检索没把
# 载有那些编号的条目带上，citation_guard 会判它编造出处，回答被打回，
# 最后吐兜底话术。两道防线必须对齐。
PINNED = {
    # 拒付 / 瑕疵 / 拒收 —— case_guard 的 REJECT_DIRECTIVE 要求引用 CISG 40、44、50
    "reject": [9, 13],
    # 停运 —— case_guard 的 TRANSIT_DIRECTIVE 涉及 CISG 71、UCC 2-705
    "transit": [3, 20],
}


def _score(item, question):
    """土办法打分：关键词、标题、典型问法命中就加分。够用，且看得懂。"""
    q = question.lower()
    s = 0
    for w in item["关键词表"]:
        if len(w) >= 2 and w.lower() in q:
            s += 3
    for ch in re.findall(r"[一-鿿]{2,}", item["标题"]):
        if ch in question:
            s += 2
    for ch in re.findall(r"[一-鿿]{3,}", item["典型问法"]):
        if ch in question:
            s += 1
    return s


def to_provision(item):
    """一条知识 -> llm.ask() 要的格式。source 必须是【法律依据】原文。"""
    body = item["回答"]
    if item["风险提示"]:
        body += "\n【风险提示】" + item["风险提示"]
    return {
        "source": item["法律依据"],
        "text": "（知识库第%d条·%s）%s" % (item["no"], item["标题"], body),
        "no": item["no"],
    }


def retrieve(question, items=None, top_k=3, pin=None):
    """
    question : 用户问题
    pin      : PINNED 的键组成的列表，如 ["reject"]；由 case_guard 的判定结果决定
    返回 provisions 列表
    """
    items = items if items is not None else load()
    by_no = {x["no"]: x for x in items}

    chosen = []
    seen = set()

    for key in (pin or []):
        for no in PINNED.get(key, []):
            if no in by_no and no not in seen:
                seen.add(no)
                chosen.append(by_no[no])

    ranked = sorted(items, key=lambda x: (-_score(x, question), x["no"]))
    for x in ranked:
        if len(chosen) >= max(top_k, len(seen)):
            break
        if x["no"] in seen:
            continue
        if _score(x, question) <= 0:
            break
        seen.add(x["no"])
        chosen.append(x)

    return [to_provision(x) for x in chosen]


VERSION = "v1"
