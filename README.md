# Honshitsu

博多弁キャラでSNS（X/旧Twitter）を運用するための、個人用サポートツール。

ニュースの事実確認（ファクトチェック）と、SNSで話題になっているトピック集めをAI（Claude）にやらせて、その結果を博多弁でまとめて投稿しやすくするデスクトップアプリです。

## 主な機能

- **ファクトチェックタブ**：文章やニュース記事のURLを入力すると、ClaudeのWeb検索機能で調べて「実際はこうだった」を博多弁で要約
- **Xトレンド収集タブ**：政治・経済・芸能・スポーツ・音楽の話題を自動収集、または気になった投稿を貼り付けて分類・要約

## ディレクトリ構成

```
Honshitsu/
├── scripts/
│   └── sns-tools/        ← SNSツール本体一式（このフォルダ単位で自己完結）
│       ├── SNSツールを起動.bat
│       ├── gui.py
│       ├── factcheck.py
│       ├── trend_watch.py
│       ├── hakata_dict.csv
│       ├── requirements.txt
│       ├── .env            ← APIキー(共有しないこと)
│       ├── venv/
│       └── outputs/
├── tmp/                    ← ドキュメント・データ置き場
│   └── プロジェクト概要.md ← より詳しい経緯・仕組みの説明
├── logs/
└── _trash/
```

## 起動方法

`scripts\sns-tools\SNSツールを起動.bat` をダブルクリックするだけ。

## 使っている技術

- Python + tkinter
- Anthropic Claude API（Web検索機能つき）
- trafilatura（記事本文抽出）

## 注意点

`scripts/sns-tools/.env` に本物のAnthropic APIキーが平文で保存されています。Gitの管理対象からは除外されていますが、他の人に渡したりクラウドにアップロードしたりしないよう注意してください。

より詳しい背景・作業の流れは [tmp/プロジェクト概要.md](tmp/プロジェクト概要.md) を参照してください。
