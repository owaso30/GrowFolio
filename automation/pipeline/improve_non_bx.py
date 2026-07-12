"""Improve non-BitradeX SEO: Copilot dedupe, home hub, tax cluster."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from seo.ssp_meta import SSP_META_DESCRIPTION, SSP_META_TITLE
from wordpress.client import WordPressClient

CANONICAL_ID = 312
CANONICAL_URL = "https://growfolio-note.com/vscode-1116-github-copilot-chat-builtin-2026/"
DUPLICATE_IDS = [397, 400]

CANONICAL_TITLE = (
    "VS Code 1.116でGitHub Copilot Chatが標準同梱へ｜変更点・使い方・今後の展望"
)
CANONICAL_DESC = (
    "VS Code 1.116でGitHub Copilot Chat拡張が標準同梱になった変更点を解説。"
    "何が変わり何が変わらないか、開発現場への影響、今後の展望まで1本に整理。"
)

MOVED_CONTENT = f"""<!-- wp:paragraph -->
<p><strong>この記事の内容は、以下の決定版へ統合しました。</strong></p>
<!-- /wp:paragraph -->
<!-- wp:paragraph -->
<p>VS Code 1.116の GitHub Copilot Chat 標準同梱に関する解説は、重複を避けるため1本にまとめています。</p>
<!-- /wp:paragraph -->
<!-- wp:paragraph -->
<p>→ <a href="{CANONICAL_URL}">VS Code 1.116でGitHub Copilot Chatが標準同梱へ｜変更点・使い方・今後の展望</a></p>
<!-- /wp:paragraph -->
<!-- wp:html -->
<meta http-equiv="refresh" content="0;url={CANONICAL_URL}">
<!-- /wp:html -->
"""

HUB_SLUG = "growfolio-start-here"
HUB_TITLE = "グロウフォリオのおすすめ記事｜評判・出金・税金・AI開発の読み方"
HUB_DESC = (
    "グロウフォリオの読み方ガイド。"
    "BitradeXの評判・出金できない時の対処・税金、AI開発ツール比較など、目的別のおすすめ記事をまとめています。"
)
HUB_CONTENT = """<!-- wp:paragraph -->
<p>グロウフォリオは、<strong>AI開発 × 仮想通貨・資産運用</strong>の実践ノートです。目的別に、まず読むべき記事をまとめました。</p>
<!-- /wp:paragraph -->

<!-- wp:heading -->
<h2 class="wp-block-heading">BitradeXを調べている方</h2>
<!-- /wp:heading -->
<!-- wp:list -->
<ul class="wp-block-list">
<li><a href="/bitradex-review/">BitradeXの評判は？怪しい？6,200ドル実運用の正直レビュー</a></li>
<li><a href="/bitradex-withdraw-bitget/">BitradeXで出金できないときの対処法</a></li>
<li><a href="/bitradex-risk/">BitradeXの危険性・リスクを正直に解説</a></li>
<li><a href="/bitradex-start-smartphone/">BitradeXの始め方（画像付き）</a></li>
<li><a href="/bitradex-guide/">BitradeX完全ガイド</a></li>
</ul>
<!-- /wp:list -->

<!-- wp:heading -->
<h2 class="wp-block-heading">税金・資産形成</h2>
<!-- /wp:heading -->
<!-- wp:list -->
<ul class="wp-block-list">
<li><a href="/crypto-tax-timing-bunri-kazei-2026/">仮想通貨の税金「申告分離課税」移行で何が変わる？</a></li>
<li><a href="/bitradex-tax/">BitradeXの利益にかかる税金と確定申告</a></li>
</ul>
<!-- /wp:list -->

<!-- wp:heading -->
<h2 class="wp-block-heading">AI・開発ツール</h2>
<!-- /wp:heading -->
<!-- wp:list -->
<ul class="wp-block-list">
<li><a href="/cursor-vscode-difference-2026/">CursorとVSCodeの違い2026年版</a></li>
<li><a href="/vscode-1116-github-copilot-chat-builtin-2026/">VS Code 1.116でCopilot Chatが標準同梱へ</a></li>
<li><a href="/github-copilot-plan-comparison-2026/">GitHub Copilot 機能比較2026年版</a></li>
</ul>
<!-- /wp:list -->

<!-- wp:paragraph -->
<p>※投資・仮想通貨運用はリスクを伴います。最終判断はご自身の責任でお願いします。</p>
<!-- /wp:paragraph -->
"""

TAX_ID = 438
BITRADEX_TAX_ID = 244


def dedupe_copilot(client: WordPressClient) -> None:
    client.update_post(
        CANONICAL_ID,
        {
            "title": CANONICAL_TITLE,
            "meta": {
                SSP_META_TITLE: CANONICAL_TITLE,
                SSP_META_DESCRIPTION: CANONICAL_DESC,
            },
        },
    )
    print(f"canonical updated: {CANONICAL_ID}")

    for pid in DUPLICATE_IDS:
        post = client.get_post(pid, context="edit")
        old_title = post["title"]["raw"] if isinstance(post["title"], dict) else post["title"]
        client.update_post(
            pid,
            {
                "title": f"【移動しました】{str(old_title)[:55]}",
                "content": MOVED_CONTENT,
                "meta": {
                    SSP_META_TITLE: f"【移動】{CANONICAL_TITLE}"[:60],
                    SSP_META_DESCRIPTION: (
                        "この記事は決定版へ統合しました。"
                        f"最新の解説は {CANONICAL_URL} をご覧ください。"
                    ),
                },
            },
        )
        print(f"duplicate stubbed: {pid}")


def ensure_hub(client: WordPressClient) -> int:
    posts = client.list_posts(status="publish", per_page=100)
    for p in posts:
        if p.get("slug") == HUB_SLUG:
            hub_id = int(p["id"])
            client.update_post(
                hub_id,
                {
                    "title": HUB_TITLE,
                    "content": HUB_CONTENT,
                    "sticky": True,
                    "meta": {
                        SSP_META_TITLE: HUB_TITLE,
                        SSP_META_DESCRIPTION: HUB_DESC,
                    },
                },
            )
            print(f"hub updated sticky: {hub_id}")
            return hub_id

    # create under IT or first available - use 投資入門 / create without category preference
    cats = client.get_categories()
    cat_id = None
    for cat in cats:
        if cat.get("name") == "投資入門":
            cat_id = int(cat["id"])
            break
    if cat_id is None and cats:
        cat_id = int(cats[0]["id"])

    created = client.create_post(
        title=HUB_TITLE,
        content=HUB_CONTENT,
        slug=HUB_SLUG,
        category_id=cat_id or 1,
        status="publish",
        featured_media=None,
        meta_title=HUB_TITLE,
        meta_description=HUB_DESC,
    )
    hub_id = int(created["id"])
    client.update_post(hub_id, {"sticky": True})
    print(f"hub created sticky: {hub_id}")
    return hub_id


def improve_tax_cluster(client: WordPressClient) -> None:
    tax = client.get_post(TAX_ID, context="edit")
    raw = tax["content"]["raw"] if isinstance(tax["content"], dict) else tax["content"]
    aside_end = "</aside><!-- /wp:quote -->"
    marker = "<!-- TAX_CLUSTER_LINKS -->"
    if marker not in raw:
        block = f"""
<!-- wp:quote -->
<blockquote class="wp-block-quote"><!-- wp:paragraph -->
<p>{marker}<strong>関連記事（税金クラスター）</strong><br>
・<a href="/bitradex-tax/">BitradeXの利益にかかる税金と確定申告</a><br>
・計算・申告の実務ツールを検討するなら
<a href="https://px.a8.net/svt/ejp?a8mat=4B684I+EAEJG2+4DGW+5YJRM" rel="nofollow sponsored noopener" target="_blank">クリプタクト</a>
も選択肢です（PR）。</p>
<!-- /wp:paragraph --></blockquote>
<!-- /wp:quote -->
"""
        if aside_end in raw:
            i = raw.find(aside_end) + len(aside_end)
            raw = raw[:i] + "\n" + block + raw[i:]
        else:
            raw = block + raw

    tax_title = "仮想通貨の税金はいつ・どう変わる？申告分離課税と2026年のポイント"
    tax_desc = (
        "仮想通貨（暗号資産）の税金タイミングと申告分離課税への移行論点を整理。"
        "いつ課税されるか、BitradeXなど海外サービス利用時の注意、確定申告の考え方まで。"
        "※税務は専門家へ。"
    )
    client.update_post(
        TAX_ID,
        {
            "title": tax_title,
            "content": raw,
            "meta": {
                SSP_META_TITLE: tax_title,
                SSP_META_DESCRIPTION: tax_desc,
            },
        },
    )
    print(f"tax general updated: {TAX_ID}")

    bx = client.get_post(BITRADEX_TAX_ID, context="edit")
    bx_raw = bx["content"]["raw"] if isinstance(bx["content"], dict) else bx["content"]
    marker2 = "<!-- TAX_CLUSTER_TO_GENERAL -->"
    if marker2 not in bx_raw:
        link_p = f"""
<!-- wp:paragraph -->
<p>{marker2}仮想通貨全体の課税タイミング・申告分離課税の論点は、
<a href="/crypto-tax-timing-bunri-kazei-2026/">仮想通貨の税金はいつ・どう変わる？</a>
もあわせてご覧ください。</p>
<!-- /wp:paragraph -->
"""
        # insert before related articles or at end before last disclaimer
        key = "関連記事"
        idx = bx_raw.rfind(key)
        if idx > 0:
            # find start of that heading block
            h2 = bx_raw.rfind("<!-- wp:heading -->", 0, idx)
            if h2 > 0:
                bx_raw = bx_raw[:h2] + link_p + bx_raw[h2:]
            else:
                bx_raw = bx_raw + link_p
        else:
            bx_raw = bx_raw + link_p
        client.update_post(BITRADEX_TAX_ID, {"content": bx_raw})
        print(f"bitradex-tax linked: {BITRADEX_TAX_ID}")
    else:
        print("bitradex-tax already linked")


def main() -> None:
    client = WordPressClient()
    print("=== 1) Copilot dedupe ===")
    dedupe_copilot(client)
    print("=== 2) Homepage hub (sticky) ===")
    ensure_hub(client)
    print("=== 3) Tax cluster ===")
    improve_tax_cluster(client)
    print("DONE")


if __name__ == "__main__":
    main()
