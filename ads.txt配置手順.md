# ads.txt（エックスサーバー配置用）

AdSense 公式の publisher ID 行です。次を **サイトのドキュメントルート** に置いてください。

## 配置手順（エックスサーバー）

1. サーバーパネル → ファイルマネージャ（または FTP）
2. 対象ドメインの `public_html`（WordPress の `index.php` と同じ階層）を開く
3. このリポジトリの `ads.txt` をアップロード
4. ブラウザで確認: https://growfolio-note.com/ads.txt → **200** で1行表示

## 中身

```
google.com, pub-6512765201608456, DIRECT, f08c47fec0942fa0
```

> WordPress の「メディア」や固定ページでは `/ads.txt` にならない。必ずルート直下の静的ファイルとして置く。
