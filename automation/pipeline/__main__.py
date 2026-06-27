"""CLI entry: python -m pipeline [sync-posts|publish|research]"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# automation/ を PYTHONPATH 相当に
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> None:
    parser = argparse.ArgumentParser(description="Growfolio WordPress automation")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("sync-posts", help="公開済み記事をWordPressから同期")

    p_pub = sub.add_parser("publish", help="キューから記事を生成・公開")
    p_pub.add_argument("--count", type=int, default=1)
    p_pub.add_argument("--dry-run", action="store_true")

    p_res = sub.add_parser("research", help="キーワード調査してキュー更新")
    p_res.add_argument("--max-keywords", type=int, default=10)

    args = parser.parse_args()

    if args.command == "sync-posts":
        from pipeline.sync import sync_posts
        sync_posts()
    elif args.command == "publish":
        from pipeline.publish import publish_next
        publish_next(count=args.count, dry_run=args.dry_run)
    elif args.command == "research":
        from kw_research.research import run_research
        result = run_research(max_keywords=args.max_keywords)
        print(f"Queue size: {len(result.get('keywords', []))}")


if __name__ == "__main__":
    main()
