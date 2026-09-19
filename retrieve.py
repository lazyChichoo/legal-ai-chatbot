"""Retrieve statute text and expose contract keyword scanning."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from ingest import _read_text_source, embed_text, tokenize

DISCLAIMER = "固定免责声明：本系统提供的法律信息仅供参考，不构成正式法律意见，不可替代执业律师服务。风险等级仅为初步提示，不代表确定性法律判断。涉及重大法律事项，请咨询执业律师。因使用本系统信息产生的损失，开发团队不承担法律责任。"

SCENARIO_KEYWORDS = {
    "实体救济": ("赔偿", "返还", "解除", "履行", "救济"),
    "合同审查": ("合同", "条款", "违约", "付款", "验收", "质量", "交付"),
    "程序应急": ("拒收", "起诉", "仲裁", "保全", "期限", "证据", "通知"),
}
CONTRACT_KEYWORDS = tuple(sorted({word for words in SCENARIO_KEYWORDS.values() for word in words}, key=len, reverse=True))
DEFAULT_GLOSSARY = Path("中英法律术语对照表.xlsx")


def clean_text(text: str) -> str:
    text = re.sub(r"[─━═]{3,}", "", text or "")
    text = re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", text)
    return text.strip()


def load_glossary(path: str | Path = DEFAULT_GLOSSARY) -> list[dict[str, str]]:
    """Read the first worksheet of an XLSX glossary without extra dependencies."""
    glossary_path = Path(path)
    if not glossary_path.is_file():
        return []
    with zipfile.ZipFile(glossary_path) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
            shared = ["".join(node.text or "" for node in item.iter(f"{namespace}t")) for item in root.iter(f"{namespace}si")]
        sheet = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    rows = []
    for row in sheet.iter(f"{namespace}row"):
        values = []
        for cell in row.iter(f"{namespace}c"):
            value = cell.find(f"{namespace}v")
            item = "" if value is None else value.text or ""
            if cell.get("t") == "s" and item:
                item = shared[int(item)]
            values.append(item.strip())
        rows.append(values)
    if not rows:
        return []
    headers = rows[0]
    return [dict(zip(headers, row)) for row in rows[1:] if row and row[0]]


def scan_contract(text: str, glossary_path: str | Path = DEFAULT_GLOSSARY) -> list[dict[str, Any]]:
    """Return fixed keywords and matching legal terms from the glossary."""
    matches = []
    for keyword in CONTRACT_KEYWORDS:
        for found in re.finditer(re.escape(keyword), text or ""):
            matches.append({"keyword": keyword, "start": found.start(), "end": found.end(), "category": next(category for category, words in SCENARIO_KEYWORDS.items() if keyword in words)})
    for term in load_glossary(glossary_path):
        for field in ("中文术语", "英文术语"):
            for keyword in filter(None, re.split(r"\s+/\s+", term.get(field, ""))):
                for found in re.finditer(re.escape(keyword), text or "", re.IGNORECASE):
                    matches.append({"keyword": keyword, "start": found.start(), "end": found.end(), "category": "法律术语", "english": term.get("英文术语", ""), "description": term.get("简要说明", "")})
    return sorted(matches, key=lambda item: (item["start"], -len(item["keyword"])))


def _tag_hits(query: str, category: str) -> int:
    return sum(1 for keyword in SCENARIO_KEYWORDS[category] if keyword in query)


def retrieve(query: str, db_path: str = "./legal_knowledge_db", collection_name: str = "legal_knowledge", top_k: int = 5, tag_weight: float = 0.25) -> list[dict[str, Any]]:
    if not query.strip():
        raise ValueError("query 不能为空")
    if not 3 <= top_k <= 5:
        raise ValueError("top_k 必须在 3 到 5 之间")
    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError("请先安装依赖：python -m pip install -r requirements.txt") from exc
    collection = chromadb.PersistentClient(path=db_path).get_collection(collection_name)
    if collection.count() == 0:
        return []
    candidate_count = min(max(top_k * 4, 20), collection.count())
    result = collection.query(query_embeddings=[embed_text(query)], n_results=candidate_count, include=["documents", "metadatas", "distances"])
    query_tokens = set(tokenize(query))
    ranked = []
    for document, metadata, distance in zip(result["documents"][0], result["metadatas"][0], result["distances"][0]):
        doc_tokens = set(tokenize(document))
        overlap = len(query_tokens & doc_tokens)
        tag_score = _tag_hits(query, metadata["category"])
        score = overlap * 10 + tag_weight * tag_score - float(distance)
        ranked.append((score, overlap, {
            "text": document,
            "source": metadata["source"],
            "title": metadata["title"],
            "category": metadata["category"],
            "article": clean_text(metadata.get("article", "")),
            "risk_level": metadata.get("risk_level", ""),
            "scenario": metadata["scenario"],
            "answer": clean_text(metadata.get("answer", document)),
            "legal_basis": clean_text(metadata.get("legal_basis", "")),
            "review_points": clean_text(metadata.get("review_points", "")),
            "risk_warning": clean_text(metadata.get("risk_warning", "")),
            "score": round(score, 4),
        }))
    strong_tokens = {token for token in query_tokens if len(token) >= 2}
    if strong_tokens and any(overlap for _, overlap, _ in ranked):
        ranked = [item for item in ranked if item[1] > 0]
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [item[2] for item in ranked[:top_k]]


def retrieve_cases(query: str, db_path: str = "./legal_knowledge_db", collection_name: str = "legal_cases", top_k: int = 3, tag_weight: float = 0.25, provision_nos: list[int] | None = None, provision_scores: dict[int, float] | None = None) -> list[dict[str, Any]]:
    """Retrieve case-law entries from a separate collection without disturbing the main legal knowledge base."""
    if not query.strip():
        raise ValueError("query 不能为空")
    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError("请先安装依赖：python -m pip install -r requirements.txt") from exc
    try:
        collection = chromadb.PersistentClient(path=db_path).get_collection(collection_name)
    except Exception:
        return []
    if collection.count() == 0:
        return []
    # 案例文档可能被切成多个片段；扫描整个 collection 后按案例 id 去重，
    # 否则相似度最高的多个片段会挤掉其他真实案例。
    candidate_count = collection.count()
    result = collection.query(query_embeddings=[embed_text(query)], n_results=candidate_count, include=["documents", "metadatas", "distances"])
    ranked = []
    seen_cases = set()
    query_tokens = set(tokenize(query))
    for document, metadata, distance in zip(result["documents"][0], result["metadatas"][0], result["distances"][0]):
        linked_raw = metadata.get("linked_provisions", "[]")
        try:
            linked = {int(item) for item in (json.loads(linked_raw) if isinstance(linked_raw, str) else linked_raw)}
        except (TypeError, ValueError, json.JSONDecodeError):
            linked = set()
        if provision_nos and not linked.intersection(provision_nos):
            continue
        matched_provisions = sorted(linked.intersection(provision_nos or linked))
        provision_match_score = max(
            (provision_scores or {}).get(number, 0.0) for number in matched_provisions
        ) if matched_provisions else 0.0
        case_key = metadata.get("id") or (metadata.get("source", collection_name), metadata.get("title", "案例"))
        if case_key in seen_cases:
            continue
        seen_cases.add(case_key)
        doc_tokens = set(tokenize(document))
        overlap = len(query_tokens & doc_tokens)
        score = overlap * 12 - float(distance)
        ranked.append((score, overlap, {
            "text": document,
            "source": metadata.get("source", collection_name),
            "title": metadata.get("title", "案例"),
            "category": metadata.get("category", "合同审查"),
            "article": clean_text(metadata.get("article", document)),
            "answer": clean_text(metadata.get("answer", document)),
            "legal_basis": clean_text(metadata.get("legal_basis", "")),
            "risk_level": metadata.get("risk_level", "参考案例"),
            "linked_provisions": sorted(linked),
            "matched_provisions": matched_provisions,
            "provision_match_score": round(provision_match_score, 4),
            "score": round(score, 4),
        }))
    ranked.sort(key=lambda item: (item[2]["provision_match_score"], item[0]), reverse=True)
    return [item[2] for item in ranked[:top_k]]


def evaluate_retrieval(cases: list[dict[str, Any]], db_path: str = "./legal_knowledge_db", collection_name: str = "legal_knowledge", top_k: int = 5, tag_weight: float = 0.25) -> float:
    """Return hit accuracy for cases like {"query": ..., "sources": [...]}."""
    if not cases:
        return 0.0
    hits = 0
    for case in cases:
        expected = set(case.get("sources", []))
        actual = {item["source"] for item in retrieve(case["query"], db_path, collection_name, top_k, tag_weight)}
        hits += bool(expected & actual)
    return hits / len(cases)


def load_exam_cases(path: str | Path) -> list[dict[str, Any]]:
    """Read exam questions and their expected legal references from Word/text."""
    text = _read_text_source(Path(path))
    pattern = re.compile(r"第\s*(\d+)\s*题\s*(.*?)(?=第\s*\d+\s*题|附：|$)", re.S)
    cases = []
    for match in pattern.finditer(text):
        block = match.group(2).strip()
        reference = re.search(r"标准答案应引用：(.+?)(?:\n|风险等级：|$)", block)
        if not reference:
            continue
        query = block[:reference.start()].strip()
        expected = [item.strip() for item in re.split(r"[；;]", reference.group(1)) if item.strip()]
        cases.append({"number": int(match.group(1)), "query": query, "references": expected})
    return cases


def _reference_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _reference_matches(reference: str, basis: str) -> bool:
    if re.search(r"\bucc\b", reference, re.IGNORECASE):
        section = re.search(r"\d+-\d+(?:\(\d+\))?", reference)
        if section:
            return bool(re.search(rf"(?<!\d){re.escape(section.group())}(?!\d)", basis))
    if re.search(r"\bcisg\b", reference, re.IGNORECASE):
        article = re.search(r"art\.?\s*(\d+(?:\(\d+\))?)", reference, re.IGNORECASE)
        if article:
            return bool(re.search(rf"art\.?\s*{re.escape(article.group(1))}(?!\d)", basis, re.IGNORECASE))
    return _reference_key(reference) in _reference_key(basis)


def evaluate_exam(path: str | Path, db_path: str = "./legal_knowledge_db", collection_name: str = "legal_knowledge", top_k: int = 5, tag_weight: float = 0.25) -> dict[str, Any]:
    cases = load_exam_cases(path)
    results = []
    for case in cases:
        retrieved = retrieve(case["query"], db_path, collection_name, top_k, tag_weight)
        top_basis = retrieved[0]["legal_basis"] if retrieved else ""
        matched = [reference for reference in case["references"] if _reference_matches(reference, top_basis)]
        coverage = len(matched) / len(case["references"]) if case["references"] else 0.0
        results.append({"number": case["number"], "hit": bool(matched), "coverage": coverage, "matched": matched, "expected": case["references"], "top_title": retrieved[0]["title"] if retrieved else ""})
    hit_count = sum(item["hit"] for item in results)
    return {"total": len(results), "hits": hit_count, "accuracy": hit_count / len(results) if results else 0.0, "results": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?")
    parser.add_argument("--evaluate", metavar="EXAM", help="评测考卷 Word/text 文件")
    parser.add_argument("--db", default="./legal_knowledge_db")
    parser.add_argument("--collection", default="legal_knowledge")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--tag-weight", type=float, default=0.25)
    args = parser.parse_args()
    if bool(args.query) == bool(args.evaluate):
        parser.error("请提供一个问题，或使用 --evaluate 指定考卷文件")
    if args.evaluate:
        report = evaluate_exam(args.evaluate, args.db, args.collection, args.top_k, args.tag_weight)
        print(f"考卷：{args.evaluate}")
        print(f"总题数：{report['total']}，命中：{report['hits']}，命中率：{report['accuracy']:.1%}")
        for item in report["results"]:
            status = "命中" if item["hit"] else "未命中"
            print(f"第{item['number']}题：{status}；首条知识点：{item['top_title'] or '无'}")
        return
    results = retrieve(args.query, args.db, args.collection, args.top_k, args.tag_weight)
    print(f"\n免责声明：{DISCLAIMER}")
    if not results:
        print("未找到相关知识点。")
        return
    for index, item in enumerate(results, 1):
        print(f"\n===== 相关知识点 {index} =====")
        print(f"标题：{item['title']}")
        print(f"分类：{item['category']}")
        print(f"\n回答：\n{item['answer']}")
        if item["article"] and item["article"] != item["answer"]:
            print(f"\n对应条文：\n{item['article']}")
        print(f"\n法律依据：\n{item['legal_basis'] or '暂无'}")
        print(f"\n合同审查点：\n{item['review_points'] or '暂无'}")
        print(f"\n风险提示：\n{item['risk_warning'] or '暂无'}")
        print(f"\n相关度：{item['score']}")


if __name__ == "__main__":
    main()