"""SNSツール 専用アプリ画面(ファクトチェック + Xトレンド収集)

ダブルクリックで起動できる、入力欄・実行ボタン・結果表示欄を持つ
シンプルなデスクトップアプリ。tkinter(Python標準ライブラリ)のみを使用。
"""

import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"


def _log_startup_error(exc: BaseException) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / "gui_error.log"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"\n[{datetime.now().isoformat()}]\n")
        traceback.print_exception(type(exc), exc, exc.__traceback__, file=f)


try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext

    import factcheck
    import trend_watch
except Exception as e:
    _log_startup_error(e)
    sys.exit(1)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SNSツール")
        self.geometry("700x600")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.factcheck_tab = FactCheckTab(notebook)
        self.trend_tab = TrendWatchTab(notebook)

        notebook.add(self.factcheck_tab, text="ファクトチェック")
        notebook.add(self.trend_tab, text="Xトレンド収集")


class FactCheckTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        ttk.Label(
            self,
            text="調べたい文章、またはニュース記事のURLを入力してください",
        ).pack(anchor="w", padx=10, pady=(10, 0))

        self.input_box = tk.Text(self, height=5)
        self.input_box.pack(fill="x", padx=10, pady=5)

        length_frame = ttk.Frame(self)
        length_frame.pack(fill="x", padx=10, pady=(0, 5))
        ttk.Label(length_frame, text="まとめる文字数:").pack(side="left")
        self.summary_length_var = tk.StringVar(value=str(factcheck.DEFAULT_SUMMARY_LENGTH))
        ttk.Spinbox(
            length_frame, from_=1, to=200, width=5, textvariable=self.summary_length_var
        ).pack(side="left", padx=(5, 0))

        self.run_button = ttk.Button(
            self, text="チェック開始", command=self.on_run
        )
        self.run_button.pack(padx=10, pady=5, anchor="w")

        self.status_label = ttk.Label(self, text="")
        self.status_label.pack(anchor="w", padx=10)

        ttk.Label(self, text="結果:").pack(anchor="w", padx=10, pady=(10, 0))
        self.result_box = scrolledtext.ScrolledText(self, height=15, state="disabled")
        self.result_box.pack(fill="both", expand=True, padx=10, pady=5)

        self.copy_button = ttk.Button(
            self, text="結果をコピー", command=self.on_copy
        )
        self.copy_button.pack(padx=10, pady=(0, 10), anchor="w")

    def set_result(self, text: str) -> None:
        self.result_box.config(state="normal")
        self.result_box.delete("1.0", "end")
        self.result_box.insert("1.0", text)
        self.result_box.config(state="disabled")

    def on_run(self) -> None:
        raw_input = self.input_box.get("1.0", "end").strip()
        if not raw_input:
            self.status_label.config(text="文章かURLを入力してください")
            return

        try:
            summary_length = int(self.summary_length_var.get())
            if summary_length <= 0:
                raise ValueError
        except ValueError:
            self.status_label.config(text="まとめる文字数には1以上の整数を入力してください")
            return

        self.run_button.config(state="disabled")
        self.status_label.config(text="チェック中です。少々お待ちください...")
        self.set_result("")

        thread = threading.Thread(
            target=self._worker, args=(raw_input, summary_length), daemon=True
        )
        thread.start()

    def _worker(self, raw_input: str, summary_length: int) -> None:
        try:
            if raw_input.startswith("http://") or raw_input.startswith("https://"):
                text = factcheck.fetch_article(raw_input)
            else:
                text = raw_input

            result = factcheck.check_facts(text, summary_length=summary_length)
            output_text = factcheck.format_for_x(result)
            saved_path = factcheck.save_output(output_text)
            display_text = f"{output_text}\n\n[保存先] {saved_path}"
            self.after(0, self._on_done, display_text)
        except Exception as e:
            self.after(0, self._on_done, f"[エラー] {e}")

    def _on_done(self, display_text: str) -> None:
        self.set_result(display_text)
        self.status_label.config(text="完了しました")
        self.run_button.config(state="normal")

    def on_copy(self) -> None:
        text = self.result_box.get("1.0", "end").strip()
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        self.status_label.config(text="コピーしました")


class TrendWatchTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        self.mode = tk.StringVar(value="search")

        mode_frame = ttk.Frame(self)
        mode_frame.pack(fill="x", padx=10, pady=(10, 0))
        ttk.Radiobutton(
            mode_frame,
            text="自動収集(政治・経済・芸能・スポーツ・音楽を自動で調べる。数分かかります)",
            variable=self.mode,
            value="search",
            command=self.on_mode_change,
        ).pack(anchor="w")
        ttk.Radiobutton(
            mode_frame,
            text="手動入力(気になった投稿のURL/テキストを1行に1件ずつ貼り付ける)",
            variable=self.mode,
            value="manual",
            command=self.on_mode_change,
        ).pack(anchor="w")

        self.input_label = ttk.Label(self, text="")
        self.input_label.pack(anchor="w", padx=10, pady=(10, 0))

        self.input_box = tk.Text(self, height=6)
        self.input_box.pack(fill="x", padx=10, pady=5)

        length_frame = ttk.Frame(self)
        length_frame.pack(fill="x", padx=10, pady=(0, 5))
        ttk.Label(length_frame, text="まとめる文字数:").pack(side="left")
        self.summary_length_var = tk.StringVar(value=str(trend_watch.DEFAULT_SUMMARY_LENGTH))
        ttk.Spinbox(
            length_frame, from_=1, to=200, width=5, textvariable=self.summary_length_var
        ).pack(side="left", padx=(5, 0))

        self.run_button = ttk.Button(
            self, text="実行", command=self.on_run
        )
        self.run_button.pack(padx=10, pady=5, anchor="w")

        self.status_label = ttk.Label(self, text="")
        self.status_label.pack(anchor="w", padx=10)

        ttk.Label(self, text="結果:").pack(anchor="w", padx=10, pady=(10, 0))
        self.result_box = scrolledtext.ScrolledText(self, height=15, state="disabled")
        self.result_box.pack(fill="both", expand=True, padx=10, pady=5)

        self.copy_button = ttk.Button(
            self, text="結果をコピー", command=self.on_copy
        )
        self.copy_button.pack(padx=10, pady=(0, 10), anchor="w")

        self.on_mode_change()

    def on_mode_change(self) -> None:
        if self.mode.get() == "search":
            self.input_box.config(state="disabled")
            self.input_label.config(text="(手動入力モードではありません。そのまま「実行」を押してください)")
        else:
            self.input_box.config(state="normal")
            self.input_label.config(text="URL、またはテキストを1行に1件ずつ入力してください")

    def set_result(self, text: str) -> None:
        self.result_box.config(state="normal")
        self.result_box.delete("1.0", "end")
        self.result_box.insert("1.0", text)
        self.result_box.config(state="disabled")

    def on_run(self) -> None:
        mode = self.mode.get()
        items = []
        if mode == "manual":
            raw = self.input_box.get("1.0", "end")
            items = [line.strip() for line in raw.splitlines() if line.strip()]
            if not items:
                self.status_label.config(text="投稿のURLかテキストを入力してください")
                return

        try:
            summary_length = int(self.summary_length_var.get())
            if summary_length <= 0:
                raise ValueError
        except ValueError:
            self.status_label.config(text="まとめる文字数には1以上の整数を入力してください")
            return

        self.run_button.config(state="disabled")
        self.status_label.config(text="収集中です。少々お待ちください...")
        self.set_result("")

        thread = threading.Thread(
            target=self._worker, args=(mode, items, summary_length), daemon=True
        )
        thread.start()

    def _worker(self, mode: str, items: list, summary_length: int) -> None:
        try:
            if mode == "search":
                category_results = {}
                for category in trend_watch.CATEGORY_LIST:
                    self.after(0, self.status_label.config, {"text": f"[{category}] を調査中..."})
                    category_results[category] = trend_watch.collect_via_search(
                        category, summary_length=summary_length
                    )
            else:
                category_results = {c: [] for c in trend_watch.CATEGORY_LIST}
                for item in items:
                    classified = trend_watch.classify_and_summarize(
                        item, summary_length=summary_length
                    )
                    category = classified.get("category")
                    if category in category_results:
                        category_results[category].append(classified)

            report = trend_watch.format_report(category_results)
            saved_path = trend_watch.save_output(report)
            display_text = f"{report}\n\n[保存先] {saved_path}"
            self.after(0, self._on_done, display_text)
        except Exception as e:
            self.after(0, self._on_done, f"[エラー] {e}")

    def _on_done(self, display_text: str) -> None:
        self.set_result(display_text)
        self.status_label.config(text="完了しました")
        self.run_button.config(state="normal")

    def on_copy(self) -> None:
        text = self.result_box.get("1.0", "end").strip()
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        self.status_label.config(text="コピーしました")


if __name__ == "__main__":
    try:
        App().mainloop()
    except Exception as e:
        _log_startup_error(e)
        sys.exit(1)
