# Copilot重複記事の301リダイレクト（任意・推奨）

ソフト転送（記事内リダイレクト＋統合）は適用済みです。検索エンジン向けに正式な301を入れる場合は、エックスサーバーの `.htaccess` に以下を追加してください。

```apache
# Growfolio: Copilot Chat duplicate consolidation (2026-07-12)
Redirect 301 /vscode-github-copilot-features-2026/ https://growfolio-note.com/vscode-1116-github-copilot-chat-builtin-2026/
Redirect 301 /vscode-1116-github-copilot-chat-builtin-changes/ https://growfolio-note.com/vscode-1116-github-copilot-chat-builtin-2026/
```

設定場所の目安: サーバーパネル → ホームページ → `.htaccess` 編集（または `public_html` 配下）。
