"""Small contract scanner backed by retrieve.scan_contract."""

import argparse
import json

from retrieve import DEFAULT_GLOSSARY, scan_contract


def check_contract(text: str):
    return scan_contract(text)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text", nargs="?", help="要扫描的合同文本")
    parser.add_argument("--file", help="从 UTF-8 文本文件读取合同")
    parser.add_argument("--terms", default=str(DEFAULT_GLOSSARY), help="中英法律术语对照表 XLSX 路径")
    args = parser.parse_args()
    if bool(args.text) == bool(args.file):
        parser.error("请提供合同文本，或使用 --file 指定文件，不能同时使用")
    text = open(args.file, encoding="utf-8").read() if args.file else args.text
    print(json.dumps(scan_contract(text, args.terms), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()