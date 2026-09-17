"""ファクトチェック博多弁ツール(CLI版)"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import anthropic
import trafilatura
from dotenv import load_dotenv

if sys.stdout is not None and sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "outputs" / "factcheck"
HAKATA_DICT_PATH = SCRIPT_DIR / "hakata_dict.csv"

load_dotenv(SCRIPT_DIR / ".env")

DEFAULT_SUMMARY_LENGTH = 30


def _load_hakata_dict() -> list[tuple[str, str]]:
    """hakata_dict.csv(変換前,変換後)を読み込む。ファイルはユーザーがExcel等で編集できる。"""
    if not HAKATA_DICT_PATH.exists():
        return []
    pairs = []
    with HAKATA_DICT_PATH.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if len(row) >= 2 and row[0].strip():
                pairs.append((row[0].strip(), row[1].strip()))
    return pairs


def apply_hakata_dict(text: str) -> str:
    """対比表(hakata_dict.csv)に沿って、より自然な博多弁の言い回しに変換する"""
    for before, after in _load_hakata_dict():
        text = text.replace(before, after)
    return text


def _build_system_prompt(summary_length: int) -> str:
    return f"""あなたはファクトチェックの専門家です。ユーザーから渡された文章について、Web検索ツールを使ってネット上の情報を調べ、事実関係を検証してください。

出力ルール:
- 判定(事実/デマ/不明など)は下さないこと。「実際はこうだった」という事実の提示に徹すること。
- 検証結果を{summary_length}文字以内の博多弁でまとめること(例: 「そぎゃん話、実際はこうやったばい」のような言い回し)。
- 根拠にした情報源のURLをすべて列挙すること。
- 出力は必ず次のJSON形式のみで返すこと。他の文章は一切含めないこと。

{{"summary": "{summary_length}文字以内の博多弁要約", "sources": ["url1", "url2"]}}
"""


def fetch_article(url: str) -> str:
    downloaded = trafilatura.fetch_url(url)
    if downloaded is None:
        raise RuntimeError(f"記事を取得できませんでした: {url}")
    text = trafilatura.extract(downloaded)
    if not text:
        raise RuntimeError(f"記事本文を抽出できませんでした: {url}")
    return text


def check_facts(text: str, summary_length: int = DEFAULT_SUMMARY_LENGTH) -> dict:
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=4096,
        system=_build_system_prompt(summary_length),
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

    result = json.loads(combined[start : end + 1])
    if "summary" in result:
        result["summary"] = apply_hakata_dict(result["summary"])
    return result


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
    parser.add_argument(
        "--summary-length",
        type=int,
        default=DEFAULT_SUMMARY_LENGTH,
        help=f"まとめる文字数(デフォルト: {DEFAULT_SUMMARY_LENGTH})",
    )
    args = parser.parse_args()

    if not args.text and not args.url:
        parser.error("検証したい文章か --url のどちらかを指定してください")

    input_text = fetch_article(args.url) if args.url else args.text

    result = check_facts(input_text, summary_length=args.summary_length)
    output_text = format_for_x(result)

    print(output_text)

    saved_path = save_output(output_text)
    print(f"\n[保存先] {saved_path}")


if __name__ == "__main__":
    main()
