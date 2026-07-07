"""Xトレンド収集ツール(CLI版)

現時点ではX公式APIの有料プランを使わず、以下2つの無料モードで着手する。
- --mode search : Claudeのweb検索機能で、各カテゴリの話題を自動収集(無料・自動・参考値)
- --mode manual : ユーザーが気になった投稿のURL/テキストを貼り付け、AIがカテゴリ分類+要約(無料・確実)

将来X APIを有料契約した場合は collect_via_x_api() を実装するだけで済むよう、
「カテゴリ名を渡すと投稿(トピック)のリストを返す」という共通の形にしている。
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from factcheck import fetch_article

if sys.stdout is not None and sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stdin is not None and sys.stdin.encoding != "utf-8":
    sys.stdin.reconfigure(encoding="utf-8")

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "outputs" / "trends"

load_dotenv(SCRIPT_DIR / ".env")

CATEGORY_LIST = ["政治", "経済", "芸能", "スポーツ", "音楽"]

SEARCH_SYSTEM_PROMPT = """あなたはSNSトレンド調査の専門家です。指定されたカテゴリについて、
今ネット上で話題になっている出来事を、Web検索ツールを使って調べてください。

出力ルール:
- そのカテゴリで話題になっている出来事を3件、新しい順に挙げること
- 各項目は「一言要約(30文字以内)」と「出典URL」をセットにすること
- 出典URLは必ず個別記事の実際のURLにすること。検索結果一覧ページや検索クエリを含むURL(例: "search?p=...")、カテゴリ一覧ページ(例: "/categories/...")は絶対に使わないこと
- 出力は必ず次のJSON形式のみで返すこと。他の文章は一切含めないこと。

{"topics": [{"summary": "一言要約", "url": "出典URL"}, ...]}
"""

CLASSIFY_SYSTEM_PROMPT = """あなたはSNS投稿の分類の専門家です。渡された投稿(URLの記事本文、またはテキスト)を読み、
政治・経済・芸能・スポーツ・音楽のうち最も当てはまるカテゴリを1つ選び、一言要約を付けてください。

出力ルール:
- カテゴリは 政治・経済・芸能・スポーツ・音楽 のいずれか1つのみ
- 要約は30文字以内
- 出力は必ず次のJSON形式のみで返すこと。他の文章は一切含めないこと。

{"category": "カテゴリ名", "summary": "一言要約"}
"""


def _extract_json(text_blocks: list) -> dict:
    combined = "\n".join(text_blocks)
    start = combined.find("{")
    end = combined.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise RuntimeError(f"Claudeの応答からJSONを取り出せませんでした:\n{combined}")
    return json.loads(combined[start : end + 1])


def collect_via_search(category: str) -> list[dict]:
    """Web検索で話題を収集する(自動・無料)"""
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=4096,
        system=SEARCH_SYSTEM_PROMPT,
        tools=[{"type": "web_search_20260209", "name": "web_search"}],
        messages=[{"role": "user", "content": f"カテゴリ: {category}"}],
    )
    text_blocks = [block.text for block in response.content if block.type == "text"]
    if not text_blocks:
        raise RuntimeError("Claudeから本文テキストの応答がありませんでした")
    result = _extract_json(text_blocks)
    return result.get("topics", [])


def classify_and_summarize(item: str) -> dict:
    """貼り付けられたURL/テキストをカテゴリ分類+要約する(手動モード用)"""
    if item.startswith("http://") or item.startswith("https://"):
        content = fetch_article(item)
        source = item
    else:
        content = item
        source = None

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=1024,
        system=CLASSIFY_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )
    text_blocks = [block.text for block in response.content if block.type == "text"]
    if not text_blocks:
        raise RuntimeError("Claudeから本文テキストの応答がありませんでした")
    result = _extract_json(text_blocks)
    if source:
        result["url"] = source
    return result


def collect_via_x_api(category: str) -> list[dict]:
    """将来のX API有料連携用のプレースホルダー。ここに実装を追加すれば有料化できる。"""
    raise NotImplementedError(
        "X APIとの連携は未実装です。有料プラン契約後にこの関数を実装してください。"
    )


def collect_manual() -> dict[str, list[dict]]:
    """標準入力からURL/テキストを1件ずつ受け取り、カテゴリ分類する"""
    print("気になった投稿のURL、またはテキストを1行ずつ入力してください。")
    print("入力し終わったら、何も入力せずEnterを押してください。\n")

    results: dict[str, list[dict]] = {c: [] for c in CATEGORY_LIST}
    while True:
        item = input("> ").strip()
        if not item:
            break
        try:
            classified = classify_and_summarize(item)
        except Exception as e:
            print(f"  [エラー] 分類できませんでした: {e}")
            continue
        category = classified.get("category")
        if category not in results:
            print(f"  [警告] 未知のカテゴリ '{category}' は無視します")
            continue
        results[category].append(classified)
        print(f"  → {category}: {classified.get('summary')}")

    return results


def format_report(category_results: dict[str, list[dict]]) -> str:
    lines = []
    for category in CATEGORY_LIST:
        lines.append(f"【{category}】")
        topics = category_results.get(category, [])
        if not topics:
            lines.append("  該当なし")
        for topic in topics:
            summary = topic.get("summary", "")
            url = topic.get("url", "")
            lines.append(f"  ・{summary}")
            if url:
                lines.append(f"    {url}")
        lines.append("")
    return "\n".join(lines).rstrip()


def save_output(text: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = datetime.now().strftime("%Y%m%d_%H%M%S") + ".txt"
    path = OUTPUT_DIR / filename
    path.write_text(text, encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Xトレンド収集ツール")
    parser.add_argument(
        "--mode",
        choices=["search", "manual"],
        required=True,
        help="search: Web検索で自動収集 / manual: 気になった投稿を貼り付けて分類",
    )
    args = parser.parse_args()

    if args.mode == "search":
        category_results: dict[str, list[dict]] = {}
        for category in CATEGORY_LIST:
            print(f"[{category}] を調査中...")
            category_results[category] = collect_via_search(category)
    else:
        category_results = collect_manual()

    report = format_report(category_results)
    print("\n" + report)

    saved_path = save_output(report)
    print(f"\n[保存先] {saved_path}")


if __name__ == "__main__":
    main()
