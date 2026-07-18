"""AdSense再審査向けのサイト品質改善を一括適用する。

実施内容:
1. 免責ページ拡充
2. 読み方ハブ拡充（sticky）
3. Copilot重複スタブを下書きへ
4. プロモ色の強いAF記事を下書きへ
5. 非BitradeXの実用記事を2本公開
6. ads.txt 設置手順を表示
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from seo.ssp_meta import SSP_META_DESCRIPTION, SSP_META_TITLE
from wordpress.client import WordPressClient

DISCLAIMER_ID = 11
HUB_ID = 446
DUPLICATE_IDS = [397, 400]
# AFやり方・招待コードは公開維持（下書きにしない）

DISCLAIMER_TITLE = "免責事項｜投資・仮想通貨・広告に関する注意事項"
DISCLAIMER_DESC = (
    "グロウフォリオの免責事項。"
    "投資・仮想通貨に関する注意、金融商品取引法上の位置づけ、"
    "アフィリエイト・広告（PR）表記、著作権、更新方針を掲載しています。"
)

DISCLAIMER_CONTENT = """<!-- wp:paragraph -->
<p>当ブログ「グロウフォリオ」（以下「当サイト」）をご利用いただく前に、以下の内容をご確認ください。本ページは、読者の皆さまと運営者の双方が安心して情報をやり取りできるよう、当サイトの立ち位置と限界を明示するものです。</p>
<!-- /wp:paragraph -->

<!-- wp:heading -->
<h2 class="wp-block-heading">投資・金融情報に関する免責</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>当サイトで提供する情報は、筆者個人の調査・体験・見解に基づくものであり、<strong>情報の正確性・完全性・有用性・最新性を保証するものではありません</strong>。</p>
<!-- /wp:paragraph -->

<!-- wp:list -->
<ul class="wp-block-list">
<li>当サイトは、特定の金融商品・暗号資産（仮想通貨）・投資サービス・口座開設を勧誘・推奨するものではありません。</li>
<li>暗号資産・株式・FX・投資信託等には価格変動リスクがあり、<strong>元本は保証されません</strong>。損失が生じる可能性があります。</li>
<li>掲載している残高・利率・手数料・仕様・画面は時点の記録であり、将来の成果を約束するものではありません。</li>
<li>当サイトの情報を用いて行う一切の行為・投資判断は、すべて利用者ご自身の責任において行ってください。</li>
<li>当サイトの情報によって生じたいかなる損害についても、運営者は一切の責任を負いません。</li>
</ul>
<!-- /wp:list -->

<!-- wp:heading -->
<h2 class="wp-block-heading">金融商品取引法等に関する表記</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>当サイト運営者は、金融庁・財務局等に登録された<strong>投資助言・代理業者ではありません</strong>。個別の銘柄選定、売買タイミング、投資金額の助言は行いません。具体的な投資判断が必要な場合は、税理士・弁護士・金融機関等の専門家にご相談ください。</p>
<!-- /wp:paragraph -->

<!-- wp:paragraph -->
<p>海外の暗号資産関連サービスについては、日本の金融庁に登録されていない場合があります。利用可否・規制・税制は各国・各時点で異なるため、<strong>必ずご自身で公式情報と関連法規を確認</strong>したうえで判断してください。</p>
<!-- /wp:paragraph -->

<!-- wp:heading -->
<h2 class="wp-block-heading">アフィリエイト・広告について（PR表記）</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>当サイトは、運営費の一部を賄うため、アフィリエイトプログラムおよび第三者配信の広告サービスを利用しています。記事内に広告（PR）を含む場合があり、商品・サービスのリンク経由で成果が発生した場合、運営者が報酬を受け取ることがあります。</p>
<!-- /wp:paragraph -->

<!-- wp:list -->
<ul class="wp-block-list">
<li>アフィリエイトを含む記事では、可能な範囲で冒頭または目立つ位置にPR表記を行います。</li>
<li>報酬の有無が、体験談・リスク記述・手順の正確さを意図的に歪めることがないよう努めています。</li>
<li>Google AdSense 等の広告配信を利用する場合があります。詳細は<a href="/privacy-policy/">プライバシーポリシー</a>をご覧ください。</li>
</ul>
<!-- /wp:list -->

<!-- wp:heading -->
<h2 class="wp-block-heading">コンテンツの性質と更新方針</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>当サイトは「つくって、増やす。」をコンセプトに、<strong>筆者が実際に試した記録</strong>を中心に発信しています。ツール比較・手順解説・運用メモなど、実務に役立つ一次情報を増やすことを優先しています。</p>
<!-- /wp:paragraph -->

<!-- wp:list -->
<ul class="wp-block-list">
<li>サービス仕様や税制は変更されるため、重要な手続きは必ず公式・行政の一次情報で再確認してください。</li>
<li>誤記・リンク切れのご指摘は<a href="/contact/">お問い合わせ</a>より受け付け、確認のうえ修正します。</li>
<li>本免責事項は、必要に応じて予告なく改定することがあります。重要な変更がある場合は本ページを更新します。</li>
</ul>
<!-- /wp:list -->

<!-- wp:heading -->
<h2 class="wp-block-heading">著作権について</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>当サイトに掲載された文章・画像・図表等の無断転載を禁止します。引用の際は、出典として当サイトの該当ページURLを明記してください。第三者の商標・サービス名は、各権利者に帰属します。</p>
<!-- /wp:paragraph -->

<!-- wp:heading -->
<h2 class="wp-block-heading">お問い合わせ</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>本免責や記事内容に関するご連絡は、<a href="/contact/">お問い合わせフォーム</a>よりお願いします。運営者情報は<a href="/profile/">運営者情報</a>をご覧ください。</p>
<!-- /wp:paragraph -->
"""

HUB_TITLE = "グロウフォリオの読み方ガイド｜目的別おすすめ記事まとめ"
HUB_DESC = (
    "グロウフォリオの読み方ガイド。"
    "AI開発・NISA・税金・ツール比較など目的別にまず読む記事を整理。"
    "仮想通貨関連はリスク記事から読むことを推奨します。"
)

HUB_CONTENT = """<!-- wp:paragraph -->
<p>グロウフォリオは、<strong>AI開発と資産運用を実際に手を動かしながら検証する</strong>個人ブログです。ネット上の二次情報の寄せ集めではなく、筆者が試した手順・失敗・所感を中心に書いています。コンセプトは「つくって、増やす。」——ツールを作り、自分の資金で試し、結果をそのまま残すことです。</p>
<!-- /wp:paragraph -->

<!-- wp:paragraph -->
<p>初めて訪れた方は、目的別に下のリンクから読んでください。投資・仮想通貨の話は必ずリスクと自己責任を前提にしています。稼ぎ話だけを先に読むと、判断を誤りやすいです。</p>
<!-- /wp:paragraph -->

<!-- wp:heading -->
<h2 class="wp-block-heading">このサイトで分かること / 分からないこと</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p><strong>分かること</strong>：ツールの使い方比較、実際の画面つき手順、運用記録、税金の一般的な整理、失敗しやすいポイント、続け方のチェックリスト。</p>
<!-- /wp:paragraph -->

<!-- wp:paragraph -->
<p><strong>分からないこと（扱いません）</strong>：「今すぐ買うべき銘柄」「いくら投資すべきか」「今日のシグナル」などの個別助言。運営者は投資助言業者ではないため、最終判断はご自身で行ってください。税務・法律の個別相談もお受けできません。</p>
<!-- /wp:paragraph -->

<!-- wp:heading -->
<h2 class="wp-block-heading">まず読むなら（サイトの入口）</h2>
<!-- /wp:heading -->

<!-- wp:list -->
<ul class="wp-block-list">
<li><a href="/profile/">運営者情報</a> — 誰が・何を・なぜ書いているか</li>
<li><a href="/disclaimer/">免責事項</a> — 投資情報の限界とPR表記</li>
<li><a href="/privacy-policy/">プライバシーポリシー</a> — Cookie・解析・広告の扱い</li>
<li><a href="/nisa-start-checklist-2026/">NISAの始め方チェックリスト（2026）</a> — 投資入門の実践メモ</li>
<li><a href="/cursor-copilot-work-split-2026/">CursorとCopilotの実務使い分け</a> — AI開発ツールの比較</li>
</ul>
<!-- /wp:list -->

<!-- wp:heading -->
<h2 class="wp-block-heading">AI・開発ツールを調べている方</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>エディタ比較と実務での役割分担を中心にまとめています。機能カタログより、「どの作業でどれを使うか」が分かる記事を優先してください。</p>
<!-- /wp:paragraph -->

<!-- wp:list -->
<ul class="wp-block-list">
<li><a href="/cursor-vscode-difference-2026/">CursorとVS Codeの違い（2026年版）</a></li>
<li><a href="/cursor-copilot-work-split-2026/">CursorとGitHub Copilotを実務で使い分ける</a></li>
<li><a href="/github-copilot-plan-comparison-2026/">GitHub Copilot 機能・プラン比較（2026）</a></li>
<li><a href="/vscode-1116-github-copilot-chat-builtin-2026/">VS Code 1.116でCopilot Chatが標準同梱へ</a></li>
</ul>
<!-- /wp:list -->

<!-- wp:heading -->
<h2 class="wp-block-heading">税金・資産形成を調べている方</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>制度の一般整理と、続け方のチェックリストです。個別の申告代行や節税スキームの提案はしません。不明点は税理士・税務署へ確認してください。</p>
<!-- /wp:paragraph -->

<!-- wp:list -->
<ul class="wp-block-list">
<li><a href="/nisa-start-checklist-2026/">NISAの始め方チェックリスト（2026）</a></li>
<li><a href="/crypto-tax-timing-bunri-kazei-2026/">仮想通貨の税金はいつ・どう変わる？申告分離課税のポイント</a></li>
<li><a href="/tax-robot-jiyukenkyu-viral-sns/">税金ロボット自由研究から学ぶ税負担の可視化</a></li>
</ul>
<!-- /wp:list -->

<!-- wp:heading -->
<h2 class="wp-block-heading">仮想通貨・BitradeXを調べている方</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>海外サービス・元本保証なし・価格変動リスクがあります。<strong>評判や運用経過の前にリスク解説を読む</strong>ことをおすすめします。記事にはアフィリエイトを含むものがあります（PR表記あり）。</p>
<!-- /wp:paragraph -->

<!-- wp:list -->
<ul class="wp-block-list">
<li><a href="/bitradex-risk/">BitradeXの危険性・リスクを正直に解説</a></li>
<li><a href="/bitradex-review/">BitradeXの評判・実運用レビュー</a></li>
<li><a href="/bitradex-withdraw-bitget/">出金できないときの対処法</a></li>
<li><a href="/bitradex-start-smartphone/">始め方（スマホ画像付き）</a></li>
<li><a href="/bitradex-guide/">BitradeX完全ガイド</a></li>
<li><a href="/bitradex-tax/">利益にかかる税金と確定申告</a></li>
</ul>
<!-- /wp:list -->

<!-- wp:heading -->
<h2 class="wp-block-heading">FX自動売買（開発メモ）</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>EA開発・検証の記録です。フォワード結果の一部共有であり、売買シグナル配信や運用代行ではありません。</p>
<!-- /wp:paragraph -->

<!-- wp:list -->
<ul class="wp-block-list">
<li><a href="/nanpin-ea-hatan-joken/">ナンピンEAが破綻する3つの条件</a></li>
<li><a href="/ladder-x-audnzd-stable/">LADDER-X 開発メモと検証結果</a></li>
</ul>
<!-- /wp:list -->

<!-- wp:heading -->
<h2 class="wp-block-heading">読み進めるときの注意</h2>
<!-- /wp:heading -->

<!-- wp:list -->
<ul class="wp-block-list">
<li>記事時点の仕様・残高・税制は変わることがあります。重要な手続きは公式・行政情報で再確認してください。</li>
<li>アフィリエイトリンクを含む記事にはPR表記があります。詳細は<a href="/disclaimer/">免責事項</a>へ。</li>
<li>Cookie・アクセス解析・広告の扱いは<a href="/privacy-policy/">プライバシーポリシー</a>へ。</li>
<li>誤記や改善提案は<a href="/contact/">お問い合わせ</a>からどうぞ。</li>
</ul>
<!-- /wp:list -->

<!-- wp:paragraph -->
<p>更新方針：ツール比較・手順・失敗談など、読者の判断材料になる一次情報を優先して増やします。宣伝だけの薄いページは公開しません。</p>
<!-- /wp:paragraph -->
"""

NISA_TITLE = "NISAの始め方チェックリスト（2026）｜口座開設前に決める5つとよくある失敗"
NISA_SLUG = "nisa-start-checklist-2026"
NISA_DESC = (
    "2026年版NISAの始め方チェックリスト。"
    "口座開設前に決めること、つみたて投資枠の考え方、よくある失敗、"
    "証券口座選びの視点を実践メモとして整理。"
)
NISA_CONTENT = """<!-- wp:paragraph -->
<p>NISAを「なんとなく始めたい」段階から、実際に口座を開いて積立を始めるまでに、筆者が詰まりやすかったポイントをチェックリストにまとめました。個別銘柄の推奨や「いくら買うべきか」の助言ではありません。手続きと意思決定の順番のメモです。</p>
<!-- /wp:paragraph -->

<!-- wp:paragraph -->
<p><strong>この記事で分かること</strong>：開設前に決める5項目、つみたて投資枠の使い方の考え方、よくある失敗、証券会社選びで見る観点。</p>
<!-- /wp:paragraph -->

<!-- wp:heading -->
<h2 class="wp-block-heading">口座開設前に決める5つ</h2>
<!-- /wp:heading -->

<!-- wp:heading {"level":3} -->
<h3 class="wp-block-heading">1. 目的（何のためのお金か）</h3>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>「増やす」だけでは判断がぶれます。例：5〜10年後の生活防衛の厚み、教育費の一部、老後の取り崩し原資。目的が決まると、取り崩し時期とリスク許容度の話が具体になります。</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":3} -->
<h3 class="wp-block-heading">2. 毎月いくらまでなら生活が崩れないか</h3>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>NISAは上限額まで使う義務はありません。先に生活費・緊急資金を分け、余裕のある額だけを積立に回す方が続きやすいです。筆者の感覚では「口座から消えても生活が揺がない額」が上限の目安です。</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":3} -->
<h3 class="wp-block-heading">3. つみたて投資枠と成長投資枠の使い分け</h3>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>まずはつみたて投資枠で長期分散の土台を作り、慣れてから成長投資枠を検討する、という順番が多くの初心者には分かりやすいです。枠の消化を急ぐ必要はありません。</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":3} -->
<h3 class="wp-block-heading">4. どこで口座を開くか（比較軸だけ先に決める）</h3>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>「人気だから」ではなく、アプリの見やすさ、投信の取扱本数、サポート、入出金のしやすさなど、自分が迷わない軸を1〜2個決めてから比較すると選びやすいです。</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":3} -->
<h3 class="wp-block-heading">5. 本人確認書類とマイナンバーの準備</h3>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>開設そのものより、書類不備で止まるケースが多いです。撮影切れ・光の反射・住所不一致は定番です。提出前にチェックリスト化しておくと再提出が減ります。</p>
<!-- /wp:paragraph -->

<!-- wp:heading -->
<h2 class="wp-block-heading">始め方の実務フロー（短縮版）</h2>
<!-- /wp:heading -->

<!-- wp:list {"ordered":true} -->
<ol class="wp-block-list">
<li>証券口座（NISA口座）を申し込む</li>
<li>本人確認・マイナンバー提出を完了する</li>
<li>銀行口座を連携し、少額で入金テストする</li>
<li>つみたて設定（銘柄・金額・日付）を入れる</li>
<li>最初の1〜3ヶ月は「設定が動いているか」だけ確認する</li>
</ol>
<!-- /wp:list -->

<!-- wp:paragraph -->
<p>価格を毎日見ると判断がブレやすいので、初期は「積立が実行されているか」の確認に寄せるのがおすすめです。</p>
<!-- /wp:paragraph -->

<!-- wp:heading -->
<h2 class="wp-block-heading">よくある失敗（筆者周辺で見たもの）</h2>
<!-- /wp:heading -->

<!-- wp:list -->
<ul class="wp-block-list">
<li><strong>上限まで埋めないと損、と思い込む</strong> — 無理な積立は途中解約や生活圧迫につながりやすい</li>
<li><strong>開設直後に値動きで一喜一憂する</strong> — 長期前提なら、短期の上下はノイズになりがち</li>
<li><strong>商品を増やしすぎる</strong> — 最初は少数の低コスト分散型に絞った方が管理しやすい</li>
<li><strong>旧NISA・新制度の用語混在で混乱する</strong> — 2024年以降の制度を前提に公式資料で確認する</li>
<li><strong>税金・損益通算の例外を見落とす</strong> — NISA口座内の扱いは課税口座と異なります。不明点は税務署や専門家へ</li>
</ul>
<!-- /wp:list -->

<!-- wp:heading -->
<h2 class="wp-block-heading">証券会社選びで見る観点（おすすめ社名の押し売りはしない）</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>特定の証券会社を推奨する記事ではありません。比較するときの観点だけ置きます。</p>
<!-- /wp:paragraph -->

<!-- wp:list -->
<ul class="wp-block-list">
<li>つみたて設定の変更しやすさ（金額・日付・休止）</li>
<li>目論見書・交付書面の確認導線が分かりやすいか</li>
<li>スマホとPCのどちらで主に操作するか</li>
<li>問い合わせ手段（チャット・電話・フォーム）と営業時間</li>
<li>他の口座（特定口座など）と家計管理を分けやすいか</li>
</ul>
<!-- /wp:list -->

<!-- wp:heading -->
<h2 class="wp-block-heading">仮想通貨記事との読み分け</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>当サイトには仮想通貨関連の実践記事もありますが、<strong>NISA（税制優遇のある長期投資）と海外暗号資産サービスは性質がまったく異なります</strong>。リスク許容度・規制・税制が違うため、同一の「投資」として雑に混ぜないでください。仮想通貨に触れる場合は、先に<a href="/bitradex-risk/">リスク解説</a>と<a href="/disclaimer/">免責事項</a>を読んでください。</p>
<!-- /wp:paragraph -->

<!-- wp:heading -->
<h2 class="wp-block-heading">まとめ</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>NISAは「開設すること」より「続けられる設計にすること」が本題です。目的・余裕資金・枠の使い方・書類・証券会社の比較軸を先に決めると、途中で止まりにくくなります。制度や手数料は変更されるため、申し込み直前は各社・金融庁等の一次情報で再確認してください。</p>
<!-- /wp:paragraph -->

<!-- wp:paragraph -->
<p>関連：<a href="/growfolio-start-here/">グロウフォリオの読み方ガイド</a> / <a href="/crypto-tax-timing-bunri-kazei-2026/">仮想通貨の税金の整理</a> / <a href="/contact/">お問い合わせ</a></p>
<!-- /wp:paragraph -->

<!-- wp:paragraph -->
<p>※本記事は一般的な情報提供であり、投資助言ではありません。NISA・税制の最終確認は公式情報および専門家にご相談ください。</p>
<!-- /wp:paragraph -->
"""

CURSOR_TITLE = "CursorとGitHub Copilotを実務で使い分ける｜役割分担の実践メモ（2026）"
CURSOR_SLUG = "cursor-copilot-work-split-2026"
CURSOR_DESC = (
    "CursorとGitHub Copilotの実務での使い分けメモ。"
    "補完・チャット・リファクタ・レビューそれぞれでどちらを使うか、"
    "重複課金を避ける判断基準まで整理。"
)
CURSOR_CONTENT = """<!-- wp:paragraph -->
<p>AIコーディング支援を入れると「全部Cursor」「全部Copilot」に寄りがちです。筆者の実務では、<strong>エディタ体験はCursor、既存VS Code資産とチーム標準はCopilot</strong>のように役割を分ける方が無駄が少なかったです。本記事は機能カタログではなく、作業シーン別の使い分けメモです。</p>
<!-- /wp:paragraph -->

<!-- wp:paragraph -->
<p>関連の基礎比較は<a href="/cursor-vscode-difference-2026/">CursorとVS Codeの違い</a>、<a href="/github-copilot-plan-comparison-2026/">Copilotプラン比較</a>も参照してください。</p>
<!-- /wp:paragraph -->

<!-- wp:heading -->
<h2 class="wp-block-heading">結論：シーンで役割を分ける</h2>
<!-- /wp:heading -->

<!-- wp:list -->
<ul class="wp-block-list">
<li><strong>新規機能の設計〜実装の往復</strong>：Cursor（チャット＋マルチファイル編集の一体感）</li>
<li><strong>既存リポジトリでの細かい補完</strong>：Copilot（VS Code標準フローに溶けやすい）</li>
<li><strong>チームで同じ拡張・ポリシーを揃えたい</strong>：Copilot寄り</li>
<li><strong>個人の実験・スクリプト・ブログ自動化</strong>：Cursor寄り</li>
</ul>
<!-- /wp:list -->

<!-- wp:heading -->
<h2 class="wp-block-heading">作業シーン別の使い分け</h2>
<!-- /wp:heading -->

<!-- wp:heading {"level":3} -->
<h3 class="wp-block-heading">1. 小さな補完（関数名・ボイラープレート）</h3>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>どちらでも足ります。すでにVS Codeが手に馴染んでいるならCopilotのインライン補完で十分なことが多いです。Cursorに乗り換える必然は薄いシーンです。</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":3} -->
<h3 class="wp-block-heading">2. 「この方針で3ファイル直して」系</h3>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>要件が文章で、変更範囲が複数ファイルにまたがるときはCursorの方が速いことが多いです。チャットと差分適用が一体なので、往復が減ります。</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":3} -->
<h3 class="wp-block-heading">3. レビュー・説明・ドキュメント化</h3>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>「何が危ないか」「テスト観点は何か」を先に出したいときは、どちらでも可。筆者は<strong>変更差分を貼って指摘させる</strong>用途ではCopilot Chat、<strong>リポジトリ文脈を踏まえて直す</strong>用途ではCursor、と分けています。</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":3} -->
<h3 class="wp-block-heading">4. チーム開発・CI前提</h3>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>組織で許可されたツール、ログ方針、シークレット扱いが決まっている場合は、個人の最速ツールより<strong>チーム標準</strong>を優先します。Copilotが標準なら無理にCursorへ統一しなくてよいです。</p>
<!-- /wp:paragraph -->

<!-- wp:heading -->
<h2 class="wp-block-heading">重複課金を避ける判断基準</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>両方をフルプランで契約するとコストがかさみます。次の順で見直すと決めやすいです。</p>
<!-- /wp:paragraph -->

<!-- wp:list {"ordered":true} -->
<ol class="wp-block-list">
<li>直近2週間の作業ログを思い出し、「チャットで直す時間」と「補完だけ」の比率をざっくり出す</li>
<li>チャット比率が高いならCursor主、補完中心ならCopilot主</li>
<li>主ツールのプランを先に最適化し、副ツールは無料枠や低プランに落とす</li>
<li>1ヶ月後に「副ツールを開いた日数」が少なければ解約候補</li>
</ol>
<!-- /wp:list -->

<!-- wp:heading -->
<h2 class="wp-block-heading">品質を落とさないための運用ルール</h2>
<!-- /wp:heading -->

<!-- wp:list -->
<ul class="wp-block-list">
<li>生成コードは<strong>必ず差分レビュー</strong>する（特に認証・課金・ファイル削除）</li>
<li>「動いた」だけで終わらせず、テストまたは再現手順を残す</li>
<li>秘密情報をチャットに貼らない（.env、鍵、本番URLのトークン）</li>
<li>同じ indents / lint 設定を両エディタで揃える（フォーマット戦争を防ぐ）</li>
</ul>
<!-- /wp:list -->

<!-- wp:heading -->
<h2 class="wp-block-heading">VS Code 1.116以降の位置づけ</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>Copilot Chatの標準同梱が進むと、「VS Code単体でもチャットできる」状態になります。詳細は<a href="/vscode-1116-github-copilot-chat-builtin-2026/">VS Code 1.116のCopilot Chat同梱解説</a>へ。これにより「チャットがあるからCursor必須」という理由は弱まり、<strong>マルチファイル編集体験と個人ワークフロー</strong>でCursorを選ぶ、という整理になりやすいです。</p>
<!-- /wp:paragraph -->

<!-- wp:heading -->
<h2 class="wp-block-heading">まとめ</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>道具は一つに無理に統一しなくて大丈夫です。補完・チーム標準はCopilot、設計〜複数ファイル実装はCursor、という分担が実務では扱いやすいことが多いです。料金と学習コストを見て、主ツールを一つ決めてから副ツールを足す方が失敗しにくいです。</p>
<!-- /wp:paragraph -->

<!-- wp:paragraph -->
<p>関連：<a href="/growfolio-start-here/">読み方ガイド</a> / <a href="/cursor-vscode-difference-2026/">CursorとVS Codeの違い</a> / <a href="/github-copilot-plan-comparison-2026/">Copilot比較</a></p>
<!-- /wp:paragraph -->
"""


def _update_page(client: WordPressClient, page_id: int, data: dict) -> None:
    client._post(f"pages/{page_id}", data)


def expand_disclaimer(client: WordPressClient) -> None:
    _update_page(
        client,
        DISCLAIMER_ID,
        {
            "title": "免責事項",
            "content": DISCLAIMER_CONTENT,
            "meta": {
                SSP_META_TITLE: DISCLAIMER_TITLE,
                SSP_META_DESCRIPTION: DISCLAIMER_DESC,
            },
        },
    )
    print(f"disclaimer expanded: {DISCLAIMER_ID}")


def expand_hub(client: WordPressClient) -> None:
    client.update_post(
        HUB_ID,
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
    print(f"hub expanded sticky: {HUB_ID}")


def draft_thin_inventory(client: WordPressClient) -> None:
    for pid in DUPLICATE_IDS:
        post = client.get_post(pid, context="edit")
        title = post["title"]["raw"] if isinstance(post["title"], dict) else post["title"]
        client.update_post(pid, {"status": "draft"})
        print(f"set draft: {pid} {title[:50]}")


def publish_non_bx(client: WordPressClient) -> None:
    cats = {c["name"]: int(c["id"]) for c in client.get_categories()}
    invest_id = cats.get("投資入門") or list(cats.values())[0]
    it_id = cats.get("ITキャリア") or invest_id

    existing = {p["slug"] for p in client.list_posts(status="publish,draft,private", per_page=100)}

    articles = [
        (NISA_SLUG, NISA_TITLE, NISA_CONTENT, invest_id, NISA_TITLE, NISA_DESC),
        (CURSOR_SLUG, CURSOR_TITLE, CURSOR_CONTENT, it_id, CURSOR_TITLE, CURSOR_DESC),
    ]
    for slug, title, content, cat_id, meta_title, meta_desc in articles:
        if slug in existing:
            # update if exists
            posts = client._get("posts", {"slug": slug, "status": "publish,draft,private", "context": "edit"})
            if posts:
                pid = int(posts[0]["id"])
                client.update_post(
                    pid,
                    {
                        "title": title,
                        "content": content,
                        "status": "publish",
                        "categories": [cat_id],
                        "meta": {
                            SSP_META_TITLE: meta_title,
                            SSP_META_DESCRIPTION: meta_desc,
                        },
                    },
                )
                print(f"updated publish: {pid} {slug}")
                continue
        created = client.create_post(
            title=title,
            content=content,
            slug=slug,
            category_id=cat_id,
            status="publish",
            featured_media=None,
            meta_title=meta_title,
            meta_description=meta_desc,
        )
        print(f"created publish: {created['id']} {slug}")


def main() -> None:
    client = WordPressClient()
    print("=== 1) disclaimer ===")
    expand_disclaimer(client)
    print("=== 2) hub ===")
    expand_hub(client)
    print("=== 3) draft thin/promo ===")
    draft_thin_inventory(client)
    print("=== 4) non-BX articles ===")
    publish_non_bx(client)
    print("DONE")
    print()
    print("手動必須: エックスサーバーの public_html に ads.txt を配置")
    print("  google.com, pub-6512765201608456, DIRECT, f08c47fec0942fa0")
    print("手動推奨: Copilot重複URLに301（BitradeX/Copilot重複_301設定メモ.md）")
    print("手動推奨: 再申請まで1〜2週間空ける（週次自動投稿は継続）")


if __name__ == "__main__":
    main()
