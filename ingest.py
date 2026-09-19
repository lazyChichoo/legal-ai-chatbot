"""Load 20 legal materials, split them by article and scenario, and index them in Chroma."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import zipfile
from dataclasses import asdict, dataclass
from xml.etree import ElementTree
from pathlib import Path
from typing import Any

EMBEDDING_DIMENSION = 256
CATEGORIES = ("实体救济", "合同审查", "程序应急")
TOKEN_RE = re.compile(r"[\u4e00-\u9fff]+|[A-Za-z0-9_]+")


@dataclass
class Material:
    id: str
    title: str
    article: str
    scenario: str
    category: str
    source: str
    keywords: list[str]
    risk_level: str = ""
    typical_question: str = ""
    answer: str = ""
    legal_basis: str = ""
    review_points: str = ""
    risk_warning: str = ""
    linked_provisions: list[int] = None


def tokenize(text: str) -> list[str]:
    tokens = []
    for token in TOKEN_RE.findall(text or ""):
        if re.fullmatch(r"[\u4e00-\u9fff]+", token):
            tokens.extend(token[index:index + 2] for index in range(len(token) - 1))
        else:
            tokens.append(token.lower())
    return tokens


def embed_text(text: str) -> list[float]:
    """Create a deterministic, dependency-free embedding for Chroma candidate search."""
    vector = [0.0] * EMBEDDING_DIMENSION
    tokens = tokenize(text)
    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSION
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[index] += sign
    norm = sum(value * value for value in vector) ** 0.5 or 1.0
    return [value / norm for value in vector]


def _value(record: dict[str, Any], *names: str, default: str = "") -> str:
    for name in names:
        if record.get(name) not in (None, ""):
            return str(record[name]).strip()
    return default


def _material(record: dict[str, Any], index: int, source: str) -> Material:
    category = _value(record, "category", "label", "标签", default="合同审查")
    if category not in CATEGORIES:
        raise ValueError(f"第 {index} 条资料的 category 必须是：{'、'.join(CATEGORIES)}")
    raw_keywords = record.get("keywords", record.get("关键词", []))
    keywords = [str(item).strip() for item in raw_keywords] if isinstance(raw_keywords, list) else tokenize(str(raw_keywords))
    answer = _value(record, "answer", "回答")
    article = _value(record, "article", "statute", "条文", "content", "原文", default=answer)
    scenario = _value(record, "scenario", "scene", "场景", "typical_question", "典型问法")
    if not article or not scenario:
        raise ValueError(f"第 {index} 条资料必须同时包含 article/statute 和 scenario")
    title = _value(record, "title", "name", "标题", default=f"资料 {index}")
    material_id = _value(record, "id", default=f"material-{index:03d}")
    return Material(
        material_id,
        title,
        article,
        scenario,
        category,
        _value(record, "source", default=source),
        keywords,
        _value(record, "risk_level", "风险等级"),
        _value(record, "typical_question", "典型问法"),
        answer,
        _value(record, "legal_basis", "法律依据"),
        _value(record, "review_points", "合同审查点"),
        _value(record, "risk_warning", "风险提示"),
        [int(item) for item in record.get("linked_provisions", [])],
    )


def parse_template_text(text: str) -> list[dict[str, Any]]:
    """Parse records written with fields such as ``【标题】...``."""
    records: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_field = ""
    field_map = {
        "编号": "id", "标题": "title", "场景标签": "category", "风险等级": "risk_level",
        "典型问法": "typical_question", "回答": "answer", "法律依据": "legal_basis",
        "合同审查点": "review_points", "关键词": "keywords", "风险提示": "risk_warning",
    }
    for line in text.splitlines():
        match = re.match(r"^【([^】]+)】\s*(.*)$", line.strip())
        if match:
            label, value = match.groups()
            if label == "编号":
                if current:
                    records.append(current)
                current = {}
            if current is None:
                continue
            current_field = field_map.get(label, "")
            if current_field:
                current[current_field] = value.strip()
            continue
        if current is not None and current_field and line.strip():
            current[current_field] = f"{current.get(current_field, '')}\n{line.strip()}".strip()
    if current:
        records.append(current)
    for record in records:
        record["category"] = record.get("category", "").split("/")[0].strip()
        record["keywords"] = [item.strip() for item in re.split(r"[,，、]", record.get("keywords", "")) if item.strip()]
    return records


def parse_case_library_text(text: str, source: str | Path | None = None) -> list[dict[str, Any]]:
    """Parse a plain docx/txt case library into the same record schema as legal knowledge.

    This is a fallback for case libraries that are raw legal text, not a strict
    【编号】... template. It keeps the main knowledge base unchanged while letting
    the project ingest a case file into a separate collection later.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return []

    blocks = []
    current_title = ""
    current_lines: list[str] = []
    case_pattern = re.compile(r"^案例\s*(\d+)\s+(.+)$")
    for line in cleaned.splitlines():
        candidate = line.strip()
        match = case_pattern.match(candidate)
        if match:
            if current_lines:
                blocks.append((current_title, "\n".join(current_lines).strip()))
            current_title = f"案例{match.group(1)} {match.group(2).strip()}"
            current_lines = [candidate]
        elif current_lines:
            current_lines.append(candidate)
    if current_lines:
        blocks.append((current_title, "\n".join(current_lines).strip()))
    if not blocks:
        blocks = [(next((line.strip() for line in cleaned.splitlines() if line.strip()), "案例库条目"), cleaned)]

    stem = Path(str(source or "case")).stem or "case"
    records = []
    for index, (title, article) in enumerate(blocks, 1):
        title = title[:120].rstrip("。；,，）)")
        linked = []
        linked_match = re.search(r"【对应知识库】([^\n]+)", article)
        if linked_match:
            linked = [int(item) for item in re.findall(r"\d+", linked_match.group(1))]
        records.append({
            "id": f"case-{stem}-{index:03d}",
            "title": title,
            "article": article,
            "scenario": "合同审查",
            "category": "合同审查",
            "keywords": [token.strip() for token in re.split(r"[,，、;；\s]+", title) if token.strip()][:8],
            "risk_level": "参考案例",
            "typical_question": title,
            "answer": article,
            "legal_basis": "",
            "review_points": article,
            "risk_warning": "参考案例，不构成正式法律意见。",
            "linked_provisions": linked,
        })
    return records


def _read_text_source(path: Path) -> str:
    """Read plain text or Word documents saved with a misleading .txt suffix."""
    with path.open("rb") as handle:
        signature = handle.read(4)
    if signature == b"PK\x03\x04":
        with zipfile.ZipFile(path) as archive:
            document = archive.read("word/document.xml")
        root = ElementTree.fromstring(document)
        paragraphs = []
        namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        for paragraph in root.iter(f"{namespace}p"):
            value = "".join(node.text or "" for node in paragraph.iter(f"{namespace}t"))
            if value.strip():
                paragraphs.append(value.strip())
        return "\n".join(paragraphs)
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "utf-16"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"无法识别文件编码：{path}")


def load_materials(source: str | Path, expected: int | None = None, allow_fewer: bool = False) -> list[Material]:
    """Read JSON, JSONL, CSV, DOCX, or the Chinese bracket-field text template."""
    path = Path(source)
    source_is_file = path.is_file()
    files = [path] if source_is_file else sorted(path.glob("*.json")) + sorted(path.glob("*.jsonl")) + sorted(path.glob("*.csv")) + sorted(path.glob("*.docx")) + sorted(path.glob("*.word")) + sorted(path.glob("*.txt"))
    records: list[tuple[dict[str, Any], str]] = []
    for file in files:
        if file.suffix == ".txt":
            text = _read_text_source(file)
            parsed = parse_template_text(text)
            if not parsed:
                parsed = parse_case_library_text(text, file)
            records.extend((record, str(file)) for record in parsed)
        elif file.suffix == ".csv":
            with file.open(encoding="utf-8-sig", newline="") as handle:
                records.extend((dict(row), str(file)) for row in csv.DictReader(handle))
        elif file.suffix in (".docx", ".word"):
            text = _read_text_source(file)
            parsed = parse_template_text(text)
            if not parsed:
                parsed = parse_case_library_text(text, file)
            records.extend((record, str(file)) for record in parsed)
        else:
            with file.open(encoding="utf-8") as handle:
                data = json.load(handle) if file.suffix == ".json" else [json.loads(line) for line in handle if line.strip()]
            if isinstance(data, dict):
                data = data.get("materials", data.get("data", [data]))
            records.extend((record, str(file)) for record in data)
    if expected is not None and len(records) < expected and not allow_fewer:
        raise ValueError(f"需要 {expected} 条资料，实际读取 {len(records)} 条；用 --allow-fewer 可关闭此检查")
    if not records and source_is_file:
        raise ValueError(f"文件中未找到【编号】知识条目或案例内容：{path}")
    if not records:
        raise ValueError(f"未找到资料：{path}")
    return [_material(record, index, source_name) for index, (record, source_name) in enumerate(records[:expected], 1)]


def build_chunk_text(material: Material) -> str:
    sections = [
        f"标题：{material.title}",
        f"条文：{material.article}",
        f"场景：{material.scenario}",
    ]
    if material.typical_question:
        sections.append(f"典型问法：{material.typical_question}")
    if material.answer:
        sections.append(f"回答：{material.answer}")
    if material.legal_basis:
        sections.append(f"法律依据：{material.legal_basis}")
    if material.review_points:
        sections.append(f"合同审查点：{material.review_points}")
    if material.risk_warning:
        sections.append(f"风险提示：{material.risk_warning}")
    if material.keywords:
        sections.append(f"关键词：{'、'.join(material.keywords)}")
    return "\n".join(sections)


def split_material(material: Material, chunk_size: int = 800, overlap: int = 80) -> list[dict[str, Any]]:
    if chunk_size <= overlap:
        raise ValueError("chunk_size 必须大于 overlap")
    text = build_chunk_text(material)
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        metadata = {**asdict(material), "keywords": json.dumps(material.keywords, ensure_ascii=False), "linked_provisions": json.dumps(material.linked_provisions or [], ensure_ascii=False), "chunk_index": len(chunks)}
        chunks.append({"text": text[start:end], "metadata": metadata})
        if end == len(text):
            break
        start = end - overlap
    return chunks


def ingest(source: str | Path, db_path: str | Path = "./legal_knowledge_db", collection_name: str = "legal_knowledge", chunk_size: int = 800, overlap: int = 80, allow_fewer: bool = False, expected: int | None = None, reset: bool = False) -> int:
    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError("请先安装依赖：python -m pip install -r requirements.txt") from exc
    materials = load_materials(source, expected=expected, allow_fewer=allow_fewer)
    client = chromadb.PersistentClient(path=str(db_path))
    if reset:
        try:
            client.delete_collection(collection_name)
        except (ValueError, chromadb.errors.NotFoundError):
            pass
    collection = client.get_or_create_collection(collection_name)
    chunks = [chunk for material in materials for chunk in split_material(material, chunk_size, overlap)]
    if chunks:
        for source_name in {item["metadata"]["source"] for item in chunks}:
            collection.delete(where={"source": source_name})
        collection.upsert(ids=[f"{item['metadata']['id']}-{item['metadata']['chunk_index']}" for item in chunks], documents=[item["text"] for item in chunks], metadatas=[item["metadata"] for item in chunks], embeddings=[embed_text(item["text"]) for item in chunks])
    return len(chunks)


def export_json(source: str | Path, output: str | Path) -> int:
    """Convert a DOCX/TXT case library into the structured JSON source format."""
    materials = load_materials(source, allow_fewer=True)
    records = [asdict(material) for material in materials]
    Path(output).write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--db", default="./legal_knowledge_db")
    parser.add_argument("--collection", default="legal_knowledge")
    parser.add_argument("--chunk-size", type=int, default=800)
    parser.add_argument("--overlap", type=int, default=80)
    parser.add_argument("--allow-fewer", action="store_true")
    parser.add_argument("--expected", type=int, default=None, help="期望资料数量；不指定则读取全部")
    parser.add_argument("--reset", action="store_true", help="导入前清空整个集合，适合重建知识库")
    parser.add_argument("--export-json", default=None, help="同时将源文件转换为结构化 JSON")
    args = parser.parse_args()
    if args.export_json:
        print(f"已导出 {export_json(args.source, args.export_json)} 条 JSON 案例")
    print(f"已写入 {ingest(args.source, args.db, args.collection, args.chunk_size, args.overlap, args.allow_fewer, args.expected, args.reset)} 个切块")


if __name__ == "__main__":
    main()