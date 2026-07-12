"""CLI entry: python -m pipeline [sync-posts|publish|research|fetch-analytics]"""
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

    p_analytics = sub.add_parser(
        "fetch-analytics",
        help="Search Console + GA4 を取得し data/analytics/ に保存",
    )
    p_analytics.add_argument(
        "--days",
        type=int,
        default=0,
        help="集計日数（未指定時は config/analytics.yaml の period_days）",
    )
    p_analytics.add_argument(
        "--dry-run",
        action="store_true",
        help="認証・API呼び出しなしで期間と設定だけ表示",
    )
    p_analytics.add_argument(
        "--no-seed-queue",
        dest="seed_queue",
        action="store_false",
        help="GSC opportunities のキュー投入をスキップ（既定は投入する）",
    )
    p_analytics.set_defaults(seed_queue=True)

    p_seed = sub.add_parser(
        "seed-from-analytics",
        help="analytics/latest.json の GSC opportunities を keyword_queue へ流す",
    )
    p_seed.add_argument("--max-items", type=int, default=10)

    p_badges = sub.add_parser("apply-badges", help="公開済み記事に【事実】【考察】バッジを一括適用")
    p_badges.add_argument("--dry-run", action="store_true")
    p_badges.add_argument("--slug", default="", help="特定スラッグのみ更新")

    p_emphasis = sub.add_parser("apply-emphasis", help="公開済み記事の強調ショートコードを装飾HTMLに一括適用")
    p_emphasis.add_argument("--dry-run", action="store_true")
    p_emphasis.add_argument("--slug", default="", help="特定スラッグのみ更新")

    p_aff = sub.add_parser("apply-affiliates", help="記事のアフィリエイトを intro/mid/end バナー形式へ更新")
    p_aff.add_argument("--dry-run", action="store_true")
    p_aff.add_argument("--slug", default="", help="特定スラッグのみ更新")
    p_aff.add_argument("--post-id", type=int, default=0, help="特定投稿IDのみ更新")
    p_aff.add_argument(
        "--bitradex-only",
        action="store_true",
        help="BitradeX系記事のみ更新（既存バナーを差し替え）",
    )
    p_aff.add_argument(
        "--all",
        action="store_true",
        help="全公開記事のアフィリエイト配置を更新（記事末は end 1件のみ）",
    )

    p_sources = sub.add_parser("apply-source-links", help="参考・関連情報の裸URLを文字リンク化")
    p_sources.add_argument("--dry-run", action="store_true")
    p_sources.add_argument("--slug", default="", help="特定スラッグのみ更新")
    p_sources.add_argument("--post-id", type=int, default=0, help="特定投稿IDのみ更新")

    p_feat = sub.add_parser(
        "apply-featured-images",
        help="公開済み記事のアイキャッチをロゴ＋テーマ写真のハイブリッドへ更新（BitradeX系は除外）",
    )
    p_feat.add_argument("--dry-run", action="store_true")
    p_feat.add_argument("--slug", default="", help="特定スラッグのみ更新")
    p_feat.add_argument("--post-id", type=int, default=0, help="特定投稿IDのみ更新")

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
    elif args.command == "fetch-analytics":
        from analytics.report import fetch_analytics
        fetch_analytics(
            days=args.days or None,
            dry_run=args.dry_run,
        )
        if not args.dry_run and args.seed_queue:
            from pipeline.seed_from_analytics import seed_from_analytics
            seed_from_analytics()
    elif args.command == "seed-from-analytics":
        from pipeline.seed_from_analytics import seed_from_analytics
        seed_from_analytics(max_items=args.max_items)
    elif args.command == "apply-badges":
        from pipeline.apply_badges import apply_badges_to_posts
        apply_badges_to_posts(dry_run=args.dry_run, slug=args.slug or None)
    elif args.command == "apply-emphasis":
        from pipeline.apply_emphasis import apply_emphasis_to_posts
        apply_emphasis_to_posts(dry_run=args.dry_run, slug=args.slug or None)
    elif args.command == "apply-affiliates":
        from pipeline.apply_affiliates import apply_affiliates_to_posts
        apply_affiliates_to_posts(
            dry_run=args.dry_run,
            slug=args.slug or None,
            post_id=args.post_id or None,
            bitradex_only=args.bitradex_only,
            all_posts=args.all,
        )
    elif args.command == "apply-source-links":
        from pipeline.apply_source_links import apply_source_links_to_posts
        apply_source_links_to_posts(
            dry_run=args.dry_run,
            slug=args.slug or None,
            post_id=args.post_id or None,
        )
    elif args.command == "apply-featured-images":
        from pipeline.apply_featured_images import apply_featured_images_to_posts
        apply_featured_images_to_posts(
            dry_run=args.dry_run,
            slug=args.slug or None,
            post_id=args.post_id or None,
        )


if __name__ == "__main__":
    main()
