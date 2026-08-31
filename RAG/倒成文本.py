# -*- coding: utf-8 -*-
"""
倒成文本.py —— 把 Excel(.xlsx) / Word(.docx) / 文本(.txt) 的内容倒成纯文本

给谁用：需要把法学组发来的表格、文档内容贴给别人看，但不方便传文件的时候。
怎么用：  python 倒成文本.py "中英法律术语对照表.xlsx"
结果：    同目录下生成一个同名的 .txt，同时在屏幕上打印出来。

不装任何第三方库。xlsx 和 docx 本质都是 zip 压缩包，这里直接拆开读里面的 XML。
"""

import html
import os
import re
import sys
import zipfile

_TAG = re.compile(r"<[^>]+>")


def _unescape(s):
    # html.unescape 连 &amp; 这类实体和 &#24207; 这种数字编码一起处理。
    # openpyxl 存的中文就是数字编码，Excel 自己存的是原文，两种都得认。
    return html.unescape(s)


# ============================================================
# Word (.docx)
# ============================================================

_W_P = re.compile(r"<w:p[ >]")
_W_BR = re.compile(r"<w:(?:br|tab)\b[^>]*/?>")
_W_T = re.compile(r"<w:t[^>]*>.*?</w:t>", re.S)


def docx_to_text(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    lines = []
    for para in _W_P.split(xml):
        para = _W_BR.sub(" ", para)
        chunks = _W_T.findall(para)
        if not chunks:
            continue
        line = _unescape("".join(_TAG.sub("", c) for c in chunks)).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


# ============================================================
# Excel (.xlsx)
# ============================================================

_SI = re.compile(r"<si>(.*?)</si>", re.S)
_T = re.compile(r"<t[^>]*>(.*?)</t>", re.S)
_ROW = re.compile(r"<row[^>]*>(.*?)</row>", re.S)
_CELL = re.compile(r"<c\b([^>]*)>(.*?)</c>|<c\b([^>]*)/>", re.S)
_REF = re.compile(r'r="([A-Z]+)\d+"')
_TYPE = re.compile(r't="([^"]+)"')
_V = re.compile(r"<v>(.*?)</v>", re.S)
_IS = re.compile(r"<is>(.*?)</is>", re.S)
_SHEET_TAG = re.compile(r"<sheet\b[^>]*/?>")
_REL_TAG = re.compile(r"<Relationship\b[^>]*/?>")
_ATTR = re.compile(r'([\w:]+)="([^"]*)"')


def _attrs(tag):
    """把一个 XML 标签的属性拆成字典，不管属性写的先后顺序。"""
    return dict(_ATTR.findall(tag))


def _col_index(letters):
    """A -> 0, B -> 1, ... AA -> 26"""
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _shared_strings(z):
    try:
        xml = z.read("xl/sharedStrings.xml").decode("utf-8", "ignore")
    except KeyError:
        return []
    out = []
    for block in _SI.findall(xml):
        out.append(_unescape("".join(_T.findall(block))))
    return out


def _sheet_list(z):
    """返回 [(工作表名, zip里的路径), ...]，顺序跟 Excel 里的标签页一致。"""
    names = z.namelist()
    try:
        wb = z.read("xl/workbook.xml").decode("utf-8", "ignore")
        rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8", "ignore")
    except KeyError:
        paths = sorted(p for p in names if p.startswith("xl/worksheets/sheet"))
        return [(os.path.basename(p), p) for p in paths]
    rid2target = {}
    for tag in _REL_TAG.findall(rels):
        a = _attrs(tag)
        if a.get("Id") and a.get("Target"):
            rid2target[a["Id"]] = a["Target"]
    out = []
    for tag in _SHEET_TAG.findall(wb):
        a = _attrs(tag)
        name, rid = a.get("name"), a.get("r:id") or a.get("id")
        target = rid2target.get(rid, "")
        if not name or not target:
            continue
        # Target 可能写成 worksheets/sheet1.xml、/xl/worksheets/sheet1.xml 等好几种，统一成 zip 里的路径
        path = target.lstrip("/")
        if not path.startswith("xl/"):
            path = "xl/" + path
        if path in names:
            out.append((_unescape(name), path))
    if not out:   # 上面全没对上就退回按文件名排序，至少别空手而归
        paths = sorted(q for q in names if q.startswith("xl/worksheets/sheet"))
        out = [(os.path.basename(q), q) for q in paths]
    return out


def _cells_of_row(body, strings):
    """一行 -> [(列号, 文字), ...]"""
    got = []
    for attrs1, inner, attrs2 in _CELL.findall(body):
        attrs = attrs1 or attrs2
        ref = _REF.search(attrs)
        col = _col_index(ref.group(1)) if ref else len(got)
        typ = _TYPE.search(attrs)
        typ = typ.group(1) if typ else "n"
        if typ == "inlineStr":
            blk = _IS.search(inner)
            val = _unescape("".join(_T.findall(blk.group(1)))) if blk else ""
        else:
            v = _V.search(inner)
            val = _unescape(v.group(1)) if v else ""
            if typ == "s" and val.isdigit():
                idx = int(val)
                val = strings[idx] if idx < len(strings) else ""
        got.append((col, val.strip()))
    return got


def xlsx_to_text(path):
    with zipfile.ZipFile(path) as z:
        strings = _shared_strings(z)
        out = []
        for name, sheet_path in _sheet_list(z):
            xml = z.read(sheet_path).decode("utf-8", "ignore")
            rows = []
            for body in _ROW.findall(xml):
                cells = _cells_of_row(body, strings)
                if not cells:
                    continue
                width = max(c for c, _ in cells) + 1
                line = [""] * width
                for c, v in cells:
                    line[c] = v
                while line and line[-1] == "":
                    line.pop()
                if any(x for x in line):
                    rows.append(" | ".join(line))
            out.append("=== 工作表：%s（%d 行）===" % (name, len(rows)))
            out.extend(rows)
            out.append("")
        return "\n".join(out).rstrip() + "\n"


# ============================================================
# 纯文本
# ============================================================

def plain_to_text(path):
    raw = open(path, "rb").read()
    for enc in ("utf-8", "utf-8-sig", "gbk", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "ignore")


# ============================================================
# 入口
# ============================================================

def to_text(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".xlsx":
        return xlsx_to_text(path)
    if ext == ".docx":
        return docx_to_text(path)
    if ext in (".txt", ".md", ".csv", ".json", ""):
        return plain_to_text(path)
    if ext in (".doc", ".xls"):
        raise ValueError("旧版 %s 读不了。在 Office 里打开，另存为 %s 再试。"
                         % (ext, ".docx" if ext == ".doc" else ".xlsx"))
    raise ValueError("不认识的文件类型：%s（支持 .xlsx / .docx / .txt）" % ext)


def main(argv):
    if len(argv) < 2:
        print("用法： python 倒成文本.py \"文件名.xlsx\"")
        print("支持： .xlsx  .docx  .txt")
        return 1
    path = argv[1]
    if not os.path.exists(path):
        print("找不到这个文件：%s" % path)
        print("提示：文件名里有空格的话，两边要加英文双引号。")
        return 1
    try:
        text = to_text(path)
    except Exception as e:
        print("读不出来：%s" % e)
        return 1
    out = os.path.splitext(path)[0] + ".txt"
    if os.path.abspath(out) == os.path.abspath(path):
        out = os.path.splitext(path)[0] + "_倒出来的.txt"
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    print()
    print("-" * 50)
    print("共 %d 个字，已存到：%s" % (len(text), out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
