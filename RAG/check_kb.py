# -*- coding: utf-8 -*-
"""
知识库自检：确认 kb_raw.txt 存对了。
跑法：python check_kb.py
"""
import sys

try:
    import kb
except Exception as e:
    print("[失败] kb.py 装不进来：%s" % e)
    sys.exit(1)

try:
    items = kb.load()
except Exception as e:
    print("[失败] 读不了 kb_raw.txt：%s" % e)
    print("       确认 kb_raw.txt 和 kb.py 在同一个文件夹，且存成了 UTF-8 编码。")
    sys.exit(1)

bad = 0
print("解析出条数：%d" % len(items))
if len(items) != 20:
    print("[失败] 应该是 20 条。少了说明分隔线或【编号】被吃掉了。")
    bad += 1

nos = [x["no"] for x in items]
missing_no = [n for n in range(1, 21) if n not in nos]
if missing_no:
    print("[失败] 缺这几条：%s" % missing_no)
    bad += 1

no_src = [x["no"] for x in items if not x["法律依据"]]
if no_src:
    print("[失败] 这几条没读到【法律依据】：%s" % no_src)
    print("       这一项必须有，否则 citation_guard 会把正确的出处判成编造。")
    bad += 1

# 拒付两个例外所需的条文，必须在第9条和第13条里找得到
try:
    import citation_guard as cg
    by = {x["no"]: x for x in items}
    need = {9: ["40", "44", "50"], 13: ["38", "39", "40"]}
    for no, arts in need.items():
        if no not in by:
            continue
        got = {n for (_law, n) in cg.extract_refs(by[no]["法律依据"])}
        lack = [a for a in arts if a not in got]
        if lack:
            print("[失败] 第%d条的【法律依据】里找不到 CISG 第%s条" % (no, "、".join(lack)))
            bad += 1
except Exception as e:
    print("[跳过] 条文号检查没跑成：%s" % e)

print()
print("知识库没问题" if bad == 0 else "有 %d 处不对，照上面的提示改" % bad)
sys.exit(1 if bad else 0)
