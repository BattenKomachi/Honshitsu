"""ファクトチェック博多弁ツール(CLI版)"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import anthropic
import trafilatura
from dotenv import load_dotenv

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "outputs" / "factcheck"

load_dotenv(SCRIPT_DIR / ".env")

SYSTEM_PROMPT = """あなたはファクトチェックの専門家です。ユーザーから渡された文章について、Web検索ツールを使ってネット上の情報を調べ、事実関係を検証してください。

出力ルール:
- 判定(事実/デマ/不明など)は下さないこと。「実際はこうだった」という事実の提示に徹すること。
- 検証結果を30文字以内の博多弁でまとめること(例: 「そぎゃん話、実際はこうやったばい」のような言い回し)。
- 根拠にした情報源のURLをすべて列挙すること。
- 出力は必ず次のJSON形式のみで返すこと。他の文章は一切含めないこと。

{"summary": "30文字以内の博多弁要約", "sources": ["url1", "url2"]}
"""


def fetch_article(url: str) -> str:
    downloaded = trafilatura.fetch_url(url)
    if downloaded is None:
        raise RuntimeError(f"記事を取得できませんでした: {url}")
    text = trafilatura.extract(downloaded)
    if not text:
        raise RuntimeError(f"記事本文を抽出できませんでした: {url}")
    return text


def check_facts(text: str) -> dict:
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=[{"type": "web_search_20260209", "name": "web_search"}],
        messages=[{"role": "user", "content": text}],
    )

    text_blocks = [block.text for block in response.content if block.type == "text"]
    if not text_blocks:
        raise RuntimeError("Claudeから本文テキストの応答がありませんでした")

    combined = "\n".join(text_blocks)
    start = combined.find("{")
    end = combined.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise RuntimeError(f"Claudeの応答からJSONを取り出せませんでした:\n{combined}")

    return json.loads(combined[start : end + 1])


def format_for_x(result: dict) -> str:
    summary = result.get("summary", "")
    sources = result.get("sources", [])

    lines = [summary, ""]
    lines.append("出典:")
    lines.extend(sources)
    return "\n".join(lines)


def save_output(text: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = datetime.now().strftime("%Y%m%d_%H%M%S") + ".txt"
    path = OUTPUT_DIR / filename
    path.write_text(text, encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="ファクトチェック博多弁ツール")
    parser.add_argument("text", nargs="?", help="検証したい文章")
    parser.add_argument("--url", help="検証したいニュース記事などのURL")
    args = parser.parse_args()

    if not args.text and not args.url:
        parser.error("検証したい文章か --url のどちらかを指定してください")

    input_text = fetch_article(args.url) if args.url else args.text

    result = check_facts(input_text)
    output_text = format_for_x(result)

    print(output_text)

    saved_path = save_output(output_text)
    print(f"\n[保存先] {saved_path}")


if __name__ == "__main__":
    main()
