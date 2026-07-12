# グロウフォリオ 自動投稿パイプライン

WordPress（SWELL）× GitHub Actions による SEO 記事の自動生成・公開ツールです。

---

## 運用方針


| 項目          | 設定                                                    |
| ----------- | ----------------------------------------------------- |
| 公開スパン       | **火・金 09:00 JST**（週2本）                                |
| 1記事あたり      | 4,000〜6,000字 + **アイキャッチAI画像（本文0〜1枚）** + 直近IT/金融ニュース反映 |
| **AI**      | 記事: **Claude Sonnet 4.6** / 画像: **Flux（fal.ai）**      |
| **自動投稿の対象** | **ブログコンセプト全般**（BitradeX・AI副業・投資入門・税金など）               |
| 記事構成        | **事実セクション**と**考察セクション**を明確に分離（【事実】/【考察】）              |
| 収益          | **AdSense + BitradeX AF + 一般AF**（Amazon / A8）         |
| テーマ選定       | **事前の柱なし** — ニュース・サジェストからトレンドKWを自動収集                  |


公開前に Google News RSS（任意で SerpAPI）でトレンドを収集し、タイムリーな内容にしたうえで深い考察を加えます。

### 記事数の目安（参考）


| マイルストーン   | 累計記事数          | 主な目的                     |
| --------- | -------------- | ------------------------ |
| AdSense申請 | 13〜20本         | **今すぐ申請可能圏内**            |
| 初成約（AF）   | 15〜25本         | BitradeXロングテール + 自動記事のAF |
| 月1万PV級    | 40〜50本（6ヶ月目標）  | トピック拡張                   |
| 本格収益      | 70〜90本（12ヶ月目標） | 新規 + リライト                |


---



## 自動化の仕組み

```
週次: keyword-research.yml  →  KWキュー更新
週次: fetch-analytics.yml   →  GSC + GA4 スナップショット
毎月: sync-posts.yml        →  公開済み記事マスタ同期
火金: publish-scheduled.yml →  記事1本 生成・公開
```


| ワークフロー                                                                | スケジュール            | 処理                           |
| --------------------------------------------------------------------- | ----------------- | ---------------------------- |
| `[sync-posts.yml](../.github/workflows/sync-posts.yml)`               | 毎月1日 03:00 JST    | 公開済み記事を `published.json` に同期 |
| `[keyword-research.yml](../.github/workflows/keyword-research.yml)`   | 毎週日曜 03:00 JST    | トレンドニュース＋サジェスト → KWキュー更新     |
| `[fetch-analytics.yml](../.github/workflows/fetch-analytics.yml)`     | 毎週月曜 03:00 JST    | Search Console + GA4 → `data/analytics/` |
| `[publish-scheduled.yml](../.github/workflows/publish-scheduled.yml)` | **火・金 09:00 JST** | 記事1本を生成・公開                   |


---



## 初回セットアップ



### Step 1. WordPress 側（5〜10分）

- [x] 管理画面 → **ユーザー → プロフィール → アプリケーションパスワード** を発行
- [x] REST API が CloudSecure WP Security 等でブロックされていないことを確認 → **[付録A](#付録a-rest-api-の確認cloudsecure-wp-security)**
- [x] SEO SIMPLE PACK の meta を REST で書き込めるよう、**子テーマ** `functions.php` にコードを追加 → **[付録B](#付録b-子テーマ-functionsphp-への追記seo-simple-pack)**

```php
add_action('init', function () {
    register_post_meta('post', 'ssp_meta_title', [
        'show_in_rest' => true,
        'single'       => true,
        'type'         => 'string',
    ]);
    register_post_meta('post', 'ssp_meta_description', [
        'show_in_rest' => true,
        'single'       => true,
        'type'         => 'string',
    ]);
});
```



### Step 2. GitHub にコードを push

`Blog` リポジトリを GitHub にアップロードする（未作成なら新規リポジトリを作成して push）。

### Step 3. 環境変数・Secrets を登録

**ローカル**: `cp .env.example .env` して編集  
**GitHub**: リポジトリ → **Settings → Secrets and variables → Actions → New repository secret**


| 変数 / Secret              | 必須  | 説明                                                                               |
| ------------------------ | --- | -------------------------------------------------------------------------------- |
| `WP_URL`                 | Yes | `https://growfolio-note.com`                                                     |
| `WP_USER`                | Yes | WordPress ユーザー名                                                                  |
| `WP_APP_PASSWORD`        | Yes | アプリケーションパスワード                                                                    |
| `ANTHROPIC_API_KEY`      | Yes | 記事生成（Claude Sonnet 4.6）— [console.anthropic.com](https://console.anthropic.com/) |
| `FAL_KEY`                | Yes | 画像生成（Flux）— [fal.ai/dashboard/keys](https://fal.ai/dashboard/keys)（課金設定が必要）      |
| `BITRADEX_AFFILIATE_URL` | 推奨  | BitradeX 招待リンク（自動記事CTA）                                                          |
| `AMAZON_AFFILIATE_TAG`   | 推奨  | Amazonアソシエイト（自動記事CTA）                                                            |
| `SERPAPI_KEY`            | 任意  | ニュース・SERP分析の精度向上                                                                 |
| `GA4_PROPERTY_ID`        | 計測時 | GA4 プロパティ ID（数字のみ）                                                              |
| `GSC_SITE_URL`           | 計測時 | Search Console プロパティ URL（例: `https://growfolio-note.com/`）                       |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | 計測時 | サービスアカウント鍵JSONの**全文**（GitHub Secret 向け）                                      |


### Step 3b. 自動計測（GSC + GA4）の初回セットアップ

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成（または既存を使用）
2. API を有効化:
   - **Google Search Console API**
   - **Google Analytics Data API**
3. **サービスアカウント**を作成 → 鍵（JSON）を発行
4. 権限付与:
   - **Search Console** → 設定 → ユーザー → サービスアカウントのメールを **閲覧者** 以上で追加
   - **GA4** → 管理 → プロパティアクセス管理 → 同メールを **閲覧者** 以上で追加
5. GitHub Secrets に登録:
   - `GA4_PROPERTY_ID` … GA4「プロパティ設定」の数字 ID
   - `GSC_SITE_URL` … `https://growfolio-note.com/`（ドメインプロパティなら `sc-domain:growfolio-note.com`）
   - `GOOGLE_SERVICE_ACCOUNT_JSON` … 鍵JSONの中身をそのまま貼り付け
6. Actions → **Fetch Analytics (GSC + GA4)** → Run workflow

出力先:

| ファイル | 内容 |
| --- | --- |
| `data/analytics/latest.json` | 直近スナップショット（クエリ・ページ・チャネル・日次など） |
| `data/analytics/summary.md` | 人間向け週次サマリー（リライト候補つき） |
| `data/analytics/trend.json` | 週次KPIの履歴（最大52点） |

ローカル実行例:

```bash
cd automation
pip install -r requirements.txt
python -m pipeline fetch-analytics --dry-run
python -m pipeline fetch-analytics
python -m pipeline fetch-analytics --days 7
```


### Step 4. GitHub Actions を手動実行（初回のみ）

Actions タブ → 各ワークフロー → **Run workflow** で、**次の順番**に実行する。


| 順番  | ワークフロー                        | 設定               | 目的                           |
| --- | ----------------------------- | ---------------- | ---------------------------- |
| 1   | **Sync WordPress Posts**      | デフォルト            | 公開済み記事を `published.json` に同期 |
| 2   | **Keyword Research**          | デフォルト            | `keyword_queue.json` を更新     |
| 3   | **Publish Scheduled Article** | `dry_run: true`  | 生成内容の確認（公開しない）               |
| 4   | **Publish Scheduled Article** | `dry_run: false` | テスト公開（1本）                    |


Step 4 まで成功すれば、**火・金の自動公開が本番稼働**します。

### ローカルで試す場合（任意）

GitHub より先に手元で動作確認したい場合:

```bash
cd automation
cp .env.example .env
# .env に WP_URL / WP_USER / WP_APP_PASSWORD / ANTHROPIC_API_KEY / FAL_KEY 等を記入
pip install -r requirements.txt

python -m pipeline sync-posts
python -m pipeline research --max-keywords 10
python -m pipeline fetch-analytics --dry-run
python -m pipeline fetch-analytics
python -m pipeline publish --count 1 --dry-run
python -m pipeline publish --count 1          # 本番公開（dry-run 確認後）
```

---



## 記事の品質方針（自動生成）


| 要素       | 内容                                                     |
| -------- | ------------------------------------------------------ |
| トレンド     | 公開直前に IT・金融ニュースを収集（`content/trends.py`）                |
| 事実       | H2「いま起きていること（事実）」— 出典付き・捏造なし                           |
| 考察       | H2「筆者の考察・見解」— 【考察】と明記、不確実性を記載                          |
| BitradeX | 記事内容が関連する場合、AIが `bitradex` CTA を選択                     |
| 一般AF     | Amazon / A8 / BitradeX 等（AIが `affiliates.yaml` から自動選択） |


設定: `[config/content_policy.yaml](config/content_policy.yaml)` / `[config/prompts/article_system.txt](config/prompts/article_system.txt)` / `[config/affiliates.yaml](config/affiliates.yaml)`

---



## トレンドKW・ブルーオーシャン

- **監視クエリ**: `content_policy.yaml` の `trend_research.news_queries` — 見出しからロングテールKWに展開
- **ブルーオーシャン**: 同ファイルの `blue_ocean` — 短いヘッド語・競合が強いKWを除外し、3語以上の意図語付きロングテールを優先
- **トピックフィルタ**: `auto_publish.topic_keywords`
- **アフィリエイト**: `[config/affiliates.yaml](config/affiliates.yaml)` + `[config/a8_programs.yaml](config/a8_programs.yaml)`

`SERPAPI_KEY` を設定すると、上位10件のドメイン構成で競合強度を判定し、related searches / PAA から追加ロングテールも収集します。

---



## モデル設定

記事・画像のモデル名は `[config/models.yaml](config/models.yaml)` で変更できます（環境変数 `CLAUDE_MODEL` / `FLUX_*_MODEL` でも上書き可）。


| 用途         | デフォルト               | 備考                                                                        |
| ---------- | ------------------- | ------------------------------------------------------------------------- |
| 記事         | `claude-sonnet-4-6` | Anthropic                                                                 |
| 画像         | `fal-ai/flux/dev`   | アイキャッチ 1792×1024、本文 1024×1024、最大1枚                                        |
| Flux 2 Pro | `fal-ai/flux-2-pro` | `config/models.yaml` の `featured_model` / `body_model` を変更 |


月8本の目安コスト: **約 $1〜1.5（150〜225円）**（Flux 2 Pro 使用時はやや増）

---



## A8 案件の追加

`[config/a8_programs.yaml](config/a8_programs.yaml)` に **url と keywords（1〜3個）** だけ書きます。

```yaml
programs:
  - url: "https://px.a8.net/svt/ejp?a8mat=..."
    keywords: [NISA, 投資]
```

記事生成時、LLM がカタログから記事に合う id を選びます。`url` が空の案件は CTA がスキップされます。

## BitradeX / Amazon

`[config/affiliates.yaml](config/affiliates.yaml)` で定義。URL / タグは `.env` と GitHub Secrets に設定。

---



## 並行してやること


| タイミング   | アクション                                         |
| ------- | --------------------------------------------- |
| **今**   | **Google AdSense 申請**（13本 + 固定ページが揃っていれば申請可能） |
| 初回自動公開後 | Google Search Console でインデックス・エラーを確認          |
| 20本前後   | AdSense 未申請ならこのタイミングで申請                       |
| 週1回程度   | 自動公開記事を目視チェック（免責・誇大表現・事実関係）                   |
| 50本超以降  | 新規8本/月 + **既存記事リライト2〜3本/月** を検討               |


---



## 避けるべき運用


| NG              | 理由                                |
| --------------- | --------------------------------- |
| 1日に複数本の一括公開     | AdSense 審査・クロール品質に不利              |
| 品質チェックなしの毎日量産   | 金融YMYL × Helpful Content で評価低下リスク |
| 既存13本と被るKWの重複記事 | カニバリゼーション                         |


---



## トラブル時


| 症状                     | 確認ポイント                                 |
| ---------------------- | -------------------------------------- |
| REST API 401/403       | アプリパスワード・ユーザー権限・セキュリティプラグイン            |
| メタ description が反映されない | `functions.php` の `register_post_meta` |
| 画像が表示されない              | `FAL_KEY`・fal.ai 残高・メディアアップロード権限       |
| 重複記事が生成される             | `sync-posts` 実行後に `research` を再実行      |


---



## 付録A. REST API の確認（CloudSecure WP Security）

自動投稿は WordPress REST API（`/wp-json/wp/v2/`）経由で記事を投稿します。CloudSecure で REST API が無効化されていると、GitHub Actions から一切投稿できません。

### A-1. パーマリンク設定の確認（前提）

REST API が正しく動くには、パーマリンクが **「基本」以外** である必要があります（CloudSecure 公式マニュアルでも明記）。

1. WordPress 管理画面 → **設定 → パーマリンク**
2. **「投稿名」** が選ばれているか確認（growfolio-note.com は設定済みのはず）
3. 変更した場合は **「変更を保存」** をクリック



### A-2. CloudSecure の「REST API 無効化」を確認

1. 管理画面 → **設定 → CloudSecure WP Security**（または左メニューの CloudSecure）
2. 設定一覧から **「REST API 無効化」** を開く（[公式マニュアル](https://wpplugin.cloudsecure.ne.jp/cloudsecure_wp_security/disable_restapi.php)）
3. **デフォルトは「無効（OFF）」** ＝ REST API は使える状態


| 画面の状態                  | 意味            | 自動投稿   |
| ---------------------- | ------------- | ------ |
| REST API 無効化 = **OFF** | REST API 利用可  | OK     |
| REST API 無効化 = **ON**  | REST API ブロック | **NG** |


**ON になっていた場合**

- 自動投稿を使うなら **OFF に戻す**（推奨）
- どうしても ON のままにする場合は、CloudSecure の「除外プラグイン」に何か追加する必要がありますが、**外部からの REST 投稿（GitHub Actions）は基本的に通りません**。自動投稿には OFF が必須です。



### A-3. エックスサーバー「REST API アクセス制限」の確認（該当する場合）

エックスサーバーのサーバーパネルに **「REST API アクセス制限」** がある場合、国外 IP からの REST アクセスがブロックされることがあります。

- GitHub Actions の実行サーバーは **海外（米国等）** のため、制限 ON だと失敗する可能性あり
- サーバーパネル → 対象ドメイン → **REST API アクセス制限** → **OFF** または例外設定を検討

参考: [エックスサーバー CloudSecure 解説](https://www.xserver.ne.jp/bizhp/cloudsecure-wp-security/)

### A-4. ブラウザで REST API の疎通テスト

ログイン不要の公開エンドポイントで、まず JSON が返るか確認します。

**テスト1: サイト情報**

```
https://growfolio-note.com/wp-json/
```

**成功の目安**: `{"name":"グロウフォリオ",...}` のような JSON が表示される（真っ白なエラーページや 403 ではない）

**テスト2: 投稿一覧（公開記事）**

```
https://growfolio-note.com/wp-json/wp/v2/posts?per_page=1
```

**成功の目安**: 記事データの JSON 配列が返る


| 結果             | 原因の目安                                 |
| -------------- | ------------------------------------- |
| JSON が返る       | REST API 自体は有効                        |
| 403 Forbidden  | CloudSecure の REST API 無効化、WAF、サーバー制限 |
| 404 Not Found  | パーマリンクが「基本」、または URL 誤り                |
| 真っ白 / HTML エラー | プラグイン競合、PHP エラー                       |




### A-5. アプリケーションパスワードで認証テスト（本番と同じ条件）

Step 1 で発行したアプリケーションパスワードを使い、**投稿権限があるか** を確認します。

PowerShell（Windows）の例:

```powershell
$user = "あなたのWPユーザー名"
$pass = "xxxx xxxx xxxx xxxx xxxx xxxx"   # アプリケーションパスワード（スペース含むまま）
$pair = "${user}:${pass}"
$bytes = [System.Text.Encoding]::ASCII.GetBytes($pair)
$base64 = [System.Convert]::ToBase64String($bytes)
$headers = @{ Authorization = "Basic $base64" }
Invoke-RestMethod -Uri "https://growfolio-note.com/wp-json/wp/v2/users/me" -Headers $headers
```

**成功の目安**: 自分のユーザー名・ID などが JSON で返る


| HTTP ステータス       | 原因の目安                     |
| ---------------- | ------------------------- |
| 200 OK           | 認証成功。自動投稿の前提はクリア          |
| 401 Unauthorized | ユーザー名 or パスワード誤り          |
| 403 Forbidden    | 権限不足、または REST API / IP 制限 |


---



## 付録B. 子テーマ functions.php への追記（SEO SIMPLE PACK）

自動投稿スクリプトは、記事公開時に SEO SIMPLE PACK 用のメタ情報も REST API 経由で送ります。


| 送る項目        | WordPress 内部キー          |
| ----------- | ----------------------- |
| SEO タイトル    | `ssp_meta_title`       |
| メタディスクリプション | `ssp_meta_description` |


WordPress はデフォルトではカスタム meta を REST で受け取れないため、**子テーマの** `functions.php` **で「REST に公開する」と登録**する必要があります。

### B-1. 子テーマが有効か確認

1. **外観 → テーマ**
2. **「SWELL CHILD」**（子テーマ）が **有効** になっているか確認
3. 親テーマ「SWELL」が有効なら、**SWELL CHILD に切り替え**（親を直接編集しない）



### B-2. functions.php を開く（方法は2通り）



#### 方法A: WordPress 管理画面（手軽）

1. **外観 → テーマファイルエディター**
2. 右上の **「テーマを選択」** で **SWELL CHILD** を選ぶ
3. 右側のファイル一覧から `functions.php` をクリック

> 初めて開くと「直接編集は危険」と警告が出る場合があります。**子テーマの functions.php だけ**を編集する前提で「理解した」を押して進んでください。



#### 方法B: エックスサーバーのファイルマネージャー（確実）

1. エックスサーバー サーバーパネル → **ファイル管理**
2. ドメインの `public_html`（または WordPress 設置フォルダ）へ移動
3. 次のパスを開く:

```
wp-content/themes/swell_child/functions.php
```

> フォルダ名は `swell-child` 等の場合あり。`themes` 内で **CHILD** と付くフォルダを探す。



### B-3. 追記するコード

`functions.php` の **いちばん下**（既存コードの後、`?>` がある場合はその **前**）に、次をそのまま貼り付けます。

```php
/**
 * SEO SIMPLE PACK の meta を REST API から書き込み可能にする
 * （グロウフォリオ自動投稿パイプライン用）
 */
add_action('init', function () {
    register_post_meta('post', 'ssp_meta_title', [
        'show_in_rest' => true,
        'single'       => true,
        'type'         => 'string',
        'auth_callback' => function () {
            return current_user_can('edit_posts');
        },
    ]);
    register_post_meta('post', 'ssp_meta_description', [
        'show_in_rest' => true,
        'single'       => true,
        'type'         => 'string',
        'auth_callback' => function () {
            return current_user_can('edit_posts');
        },
    ]);
});
```

**注意**

- 既に同じ `register_post_meta` が書いてある場合は **二重に貼らない**
- 貼り付け後、**「ファイルを更新」** または **「更新ファイル」** をクリックして保存



### B-4. 追記後の動作確認

1. 管理画面で **適当な下書き記事** を1つ開く
2. SEO SIMPLE PACK の欄で **メタディスクリプション** を手動で入力して更新（比較用）
3. ブラウザで（ログイン中なら Cookie 認証、または付録A-5 と同様の Basic 認証で）:

```
https://growfolio-note.com/wp-json/wp/v2/posts/記事ID?context=edit
```

`meta` オブジェクト内に `ssp_meta_title` / `ssp_meta_description` が見えれば OK です。

**簡易確認**: 自動投稿のテスト公開後、該当記事の編集画面 → SEO SIMPLE PACK 欄に **タイトル・メタが入っているか** 目視確認するだけでも十分です。

### B-5. うまくいかないとき


| 症状                | 対処                                      |
| ----------------- | --------------------------------------- |
| 記事は公開されるがメタが空     | `functions.php` の保存忘れ、子テーマ未使用、キー名の typo |
| サイト全体が真っ白（500エラー） | `functions.php` の PHP 文法エラー。FTP で直前版に戻す |
| REST で meta が見えない | キャッシュプラグインを一時無効化して再確認                   |


メタが空でも **記事本文・タイトル・スラッグの公開は可能** です。SEO 最適化のため、本番稼働前に B-4 の確認を推奨します。

---



## 関連ドキュメント


| ファイル                                                                                 | 内容              |
| ------------------------------------------------------------------------------------ | --------------- |
| [`../カテゴリ・著者ページ_SEO設定.md`](../カテゴリ・著者ページ_SEO設定.md) | カテゴリ・著者・固定ページのSEOメタ |
| `[../BitradeX/BitradeX_アフィリエイト完全ロードマップ.md](../BitradeX/BitradeX_アフィリエイト完全ロードマップ.md)` | 収益KPI・KW戦略      |
| `[../BitradeX/WordPress初期セットアップ手順書.md](../BitradeX/WordPress初期セットアップ手順書.md)`         | SWELL・プラグイン初期設定 |
| `[config/](config/)`                                                                 | YAML 設定一式       |


---

*最終更新: 2026年6月*