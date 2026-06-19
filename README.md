# candyhouse-changelog-notifier

CANDY HOUSE（セサミスマートロックなど）の公式チェンジログの更新を監視し、新しいアップデートがあれば自動的にXへ通知するスクリプトです。

GitHub Actions を利用して、定期的に自動実行（監視）させています。

## 🛠 主な機能

- CANDY HOUSE の `changelog.html` を定期的にチェック
- 前回のチェック時からの更新（SHAの変更）を検知
- 最新の変更内容を取得し、Xに自動ポスト
- 実行状態（最後に確認したSHA）を `last_sha.txt` に保存して管理

## 📂 構成ファイル

- `post_to_x.py`: チェンジログの監視、差分抽出、およびXへの投稿を行うメインのPythonスクリプト
- `last_sha.txt`: 最後に確認したチェンジログのコミットSHAを記録するファイル
- `requirements.txt`: 依存ライブラリ（`requests`, `tweepy`）
- `.github/workflows/`: 定期実行を行うための GitHub Actions ワークフロー設定

## 🔗 参考リンク
- [CANDY HOUSE - changelog.html（ファイル本体）](https://github.com/CANDY-HOUSE/.github/blob/main/changelog.html)
- [CANDY HOUSE - changelog.html（コミット履歴）](https://github.com/CANDY-HOUSE/.github/commits/main/changelog.html)
- [CANDY HOUSE Website - Change Log と To Do](https://jp.candyhouse.co/pages/changelog)
