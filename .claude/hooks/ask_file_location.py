"""Honshitsuプロジェクトルート直下への新規ファイル作成を検知し、格納先の確認をClaudeに促すPreToolUse hook。"""

import json
import os
import sys

PROJECT_ROOT = "C:/Project/Honshitsu"
DOC_EXTS = {".md", ".csv", ".xlsx", ".xls", ".txt"}
PROGRAM_EXTS = {".py", ".sh"}
ROOT_STANDARD_FILES = {"README.md", "LICENSE", "CHANGELOG.md", ".gitignore"}


def main() -> None:
    data = json.load(sys.stdin)
    file_path = data.get("tool_input", {}).get("file_path", "")
    if not file_path:
        return

    normalized = file_path.replace("\\", "/")
    parent_dir = os.path.dirname(normalized)
    if parent_dir != PROJECT_ROOT:
        return

    base = os.path.basename(normalized)
    if base in ROOT_STANDARD_FILES:
        return

    ext = os.path.splitext(base)[1].lower()

    if ext in DOC_EXTS:
        suggestion = "tmp/"
    elif ext in PROGRAM_EXTS:
        suggestion = "scripts/"
    else:
        return

    reason = (
        f"'{base}' をプロジェクトルート直下に作成しようとしています。"
        f"このプロジェクトではmd/csv/xlsx/xls/txtはtmp/、py/shはscripts/に格納する運用です"
        f"(該当拡張子の推奨格納先: {suggestion})。"
        "AskUserQuestionツールで保存先をユーザーに確認してから、選ばれた場所に書き直してください。"
    )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )


if __name__ == "__main__":
    main()
