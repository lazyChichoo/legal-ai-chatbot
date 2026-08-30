"""Interactive command-line entry point for the legal knowledge assistant."""

from __future__ import annotations

import argparse

from retrieve import DISCLAIMER, retrieve


def print_result(index: int, item: dict[str, object]) -> None:
    print(f"\n===== 相关知识点 {index} =====")
    print(f"标题：{item['title']}")
    print(f"分类：{item['category']}")
    print(f"\n回答：\n{item['answer']}")
    print(f"\n法律依据：\n{item['legal_basis'] or '暂无'}")
    print(f"\n合同审查点：\n{item['review_points'] or '暂无'}")
    print(f"\n风险提示：\n{item['risk_warning'] or '暂无'}")
    print(f"\n相关度：{item['score']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="./legal_knowledge_db")
    parser.add_argument("--collection", default="legal_knowledge")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--tag-weight", type=float, default=0.25)
    args = parser.parse_args()

    print("法律知识库问答助手")
    print("请输入问题，输入 q、quit 或 exit 退出。")
    print(f"免责声明：{DISCLAIMER}")
    while True:
        try:
            query = input("\n问题：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已退出。")
            break
        if query.lower() in {"q", "quit", "exit", "退出"}:
            print("已退出。")
            break
        if not query:
            print("请输入具体问题。")
            continue
        try:
            results = retrieve(query, args.db, args.collection, args.top_k, args.tag_weight)
        except (RuntimeError, ValueError) as exc:
            print(f"错误：{exc}")
            continue
        if not results:
            print("未找到相关知识点。")
            continue
        for index, item in enumerate(results, 1):
            print_result(index, item)


if __name__ == "__main__":
    main()
