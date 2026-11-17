"""myDB desktop app: control window, search popup and settings (Tkinter)."""
from __future__ import annotations

import argparse
import os
import queue
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from mydb import __version__
from mydb.config import config_path, load_config, save_config
from mydb.data import (CsvDatabase, PART_NUMBER_ALIASES, PRICE_ALIASES, detect_column,
                       format_all, format_part_number, format_price)
from mydb import system
from mydb.hotkey import parse_hotkey, pretty_hotkey

AUTO = "(auto-detect)"


# ------------------------------------------------------------ search popup
class SearchPopup(tk.Toplevel):
    """Three steps in one window: pick DB -> search -> choose what to copy."""

    def __init__(self, app: "App"):
        super().__init__(app.root)
        self.app = app
        self.withdraw()
        self.title("myDB search")
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.minsize(640, 360)
        self.db: CsvDatabase | None = None
        self.visible_rows: list[int] = []
        self.selected_row: dict | None = None
        self._debounce = None
        self.prev_app = None

        self.pick_frame = self._build_pick()
        self.search_frame = self._build_search()
        self.action_frame = self._build_action()
        self.bind("<Escape>", self._on_escape)

    # ---- building
    def _build_pick(self) -> ttk.Frame:
        f = ttk.Frame(self, padding=16)
        ttk.Label(f, text="Which database?", style="Title.TLabel").pack(anchor="w")
        ttk.Label(f, text="Press the number, or use arrows + Enter.  Esc closes.",
                  style="Hint.TLabel").pack(anchor="w", pady=(0, 8))
        self.db_list = tk.Listbox(f, font=self.app.font_big, activestyle="none", height=8,
                                  borderwidth=1, relief="solid", highlightthickness=0)
        self.db_list.pack(fill="both", expand=True)
        self.db_list.bind("<Return>", lambda e: self._pick_selected())
        self.db_list.bind("<Double-Button-1>", lambda e: self._pick_selected())
        for n in range(1, 10):
            self.db_list.bind(str(n), lambda e, i=n - 1: self._pick_index(i))
        return f

    def _build_search(self) -> ttk.Frame:
        f = ttk.Frame(self, padding=12)
        top = ttk.Frame(f)
        top.pack(fill="x")
        self.search_title = ttk.Label(top, text="", style="Title.TLabel")
        self.search_title.pack(side="left")
        ttk.Label(top, text="Type to filter · ↑↓ move · Enter select · Esc back",
                  style="Hint.TLabel").pack(side="right")
        self.query = tk.StringVar()
        self.entry = ttk.Entry(f, textvariable=self.query, font=self.app.font_big)
        self.entry.pack(fill="x", pady=8)
        self.query.trace_add("write", lambda *a: self._schedule_filter())
        self.entry.bind("<Down>", lambda e: self._move(1))
        self.entry.bind("<Up>", lambda e: self._move(-1))
        self.entry.bind("<Next>", lambda e: self._move(10))
        self.entry.bind("<Prior>", lambda e: self._move(-10))
        self.entry.bind("<Return>", lambda e: self._choose_row())

        body = ttk.Frame(f)
        body.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(body, show="headings", selectmode="browse")
        ys = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        xs = ttk.Scrollbar(body, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        self.tree.bind("<Double-Button-1>", lambda e: self._choose_row())
        self.tree.bind("<Return>", lambda e: self._choose_row())

        self.count_label = ttk.Label(f, text="", style="Hint.TLabel")
        self.count_label.pack(anchor="w", pady=(6, 0))
        return f

    def _build_action(self) -> ttk.Frame:
        f = ttk.Frame(self, padding=16)
        ttk.Label(f, text="What do you want to copy?", style="Title.TLabel").pack(anchor="w")
        self.action_summary = ttk.Label(f, text="", style="Hint.TLabel", justify="left")
        self.action_summary.pack(anchor="w", pady=(4, 12))
        for key, label, kind in (("1", "Part Number", "pn"), ("2", "Price", "price"), ("3", "All info", "all")):
            b = ttk.Button(f, text=f"[{key}]  {label}", style="Big.TButton",
                           command=lambda k=kind: self._do_action(k))
            b.pack(fill="x", pady=4)  # keys 1/2/3 are bound in _show()
        ttk.Label(f, text="Shortcuts: 1/P · 2/R · 3/A · Esc back", style="Hint.TLabel").pack(anchor="w", pady=(10, 0))
        return f

    # ---- steps
    def open(self) -> None:
        self.prev_app = system.remember_frontmost()
        dbs = self.app.cfg.get("databases", [])
        if not dbs:
            messagebox.showinfo("myDB", "No databases configured yet. Add your CSV files in Settings.")
            self.app.open_settings()
            return
        self.db_list.delete(0, "end")
        for i, d in enumerate(dbs, 1):
            self.db_list.insert("end", f"  {i}.  {d['name']}   —  {os.path.basename(d['path'])}")
        last = min(self.app.last_db_index, len(dbs) - 1)
        self.db_list.selection_set(last)
        self.db_list.activate(last)
        self._show(self.pick_frame)
        self._present()
        self.db_list.focus_set()

    def _present(self) -> None:
        w, h = 980, 560
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 3
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.deiconify()
        self.update_idletasks()
        system.bring_to_front(self)

    def _show(self, frame: ttk.Frame) -> None:
        for fr in (self.pick_frame, self.search_frame, self.action_frame):
            fr.pack_forget()
        frame.pack(fill="both", expand=True)
        self.current = frame
        for k in "123praPRA":
            self.unbind(k)
        if frame is self.action_frame:
            for keys, kind in (("1pP", "pn"), ("2rR", "price"), ("3aA", "all")):
                for k in keys:
                    self.bind(k, lambda e, kd=kind: self._do_action(kd))

    def _pick_index(self, i: int) -> None:
        if i < self.db_list.size():
            self.db_list.selection_clear(0, "end")
            self.db_list.selection_set(i)
            self._pick_selected()

    def _pick_selected(self) -> None:
        sel = self.db_list.curselection()
        if not sel:
            return
        i = sel[0]
        try:
            self.db = self.app.get_database(i)
        except Exception as exc:  # file missing, unreadable...
            messagebox.showerror("myDB", f"Could not open the database:\n\n{exc}", parent=self)
            return
        self.app.last_db_index = i
        self.search_title.configure(text=f"{self.db.name}  ·  {len(self.db.rows):,} rows")
        cols = self.db.headers
        self.tree.configure(columns=cols)
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=150 if c in (self.db.pn_col, self.db.price_col) else 180,
                             stretch=len(cols) <= 6)
        self.query.set("")
        self._show(self.search_frame)
        self._filter()
        self.entry.focus_set()

    def _schedule_filter(self) -> None:
        if self._debounce:
            self.after_cancel(self._debounce)
        self._debounce = self.after(120, self._filter)

    def _filter(self) -> None:
        self._debounce = None
        if not self.db:
            return
        limit = int(self.app.cfg.get("max_results", 500))
        idxs, total = self.db.search(self.query.get(), limit)
        self.tree.delete(*self.tree.get_children())
        self.visible_rows = idxs
        for n, i in enumerate(idxs):
            r = self.db.rows[i]
            self.tree.insert("", "end", iid=str(n), values=[r.get(h, "") for h in self.db.headers])
        if idxs:
            self.tree.selection_set("0")
            self.tree.see("0")
        shown = f"Showing {len(idxs):,} of {total:,} matches" if total > len(idxs) else f"{total:,} matches"
        self.count_label.configure(text=shown)

    def _move(self, delta: int) -> str:
        items = self.tree.get_children()
        if not items:
            return "break"
        sel = self.tree.selection()
        cur = int(sel[0]) if sel else -1
        nxt = max(0, min(len(items) - 1, cur + delta))
        self.tree.selection_set(str(nxt))
        self.tree.see(str(nxt))
        return "break"

    def _choose_row(self) -> str:
        sel = self.tree.selection()
        if not sel:
            return "break"
        self.selected_row = self.db.rows[self.visible_rows[int(sel[0])]]
        pn = format_part_number(self.db, self.selected_row) or "(no part-number column detected)"
        price = format_price(self.db, self.selected_row) or "(no price column detected)"
        self.action_summary.configure(text=f"Part Number:  {pn}\nPrice:  {price}")
        self._show(self.action_frame)
        self.focus_set()
        return "break"

    def _do_action(self, kind: str) -> None:
        db, row = self.db, self.selected_row
        if not (db and row):
            return
        if kind == "pn":
            text, what = format_part_number(db, row), "Part Number"
        elif kind == "price":
            text, what = format_price(db, row), "Price"
        else:
            text, what = format_all(db, row, self.app.cfg.get("all_info_format", "lines")), "All info"
        if not text:
            messagebox.showwarning(
                "myDB", f"No {what} column was detected in '{db.name}'.\n"
                        "Choose it in Settings → Edit database.", parent=self)
            return
        self.app.copy_to_clipboard(text)
        self.close()
        self.app.set_status(f"Copied {what}: {text.splitlines()[0][:60]}")
        if self.app.cfg.get("auto_paste"):
            self.app.paste_into(self.prev_app)

    def _on_escape(self, _e=None) -> None:
        if self.current is self.action_frame:
            self._show(self.search_frame)
            self.entry.focus_set()
        elif self.current is self.search_frame and len(self.app.cfg.get("databases", [])) > 1:
            self._show(self.pick_frame)
            self.db_list.focus_set()
        else:
            self.close()

    def close(self) -> None:
        self.withdraw()
        system.restore_frontmost(self.prev_app)


# ------------------------------------------------------------ settings
class DbDialog(tk.Toplevel):
    def __init__(self, parent, entry: dict | None = None):
        super().__init__(parent)
        self.title("Database")
        self.transient(parent)
        self.resizable(False, False)
        self.result = None
        e = entry or {"name": "", "path": "", "part_number_column": "", "price_column": ""}
        f = ttk.Frame(self, padding=14)
        f.pack(fill="both", expand=True)
        self.name = tk.StringVar(value=e["name"])
        self.path = tk.StringVar(value=e["path"])
        self.pn = tk.StringVar(value=e.get("part_number_column") or AUTO)
        self.price = tk.StringVar(value=e.get("price_column") or AUTO)

        ttk.Label(f, text="Name").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(f, textvariable=self.name, width=50).grid(row=0, column=1, columnspan=2, sticky="ew")
        ttk.Label(f, text="CSV file").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(f, textvariable=self.path, width=50).grid(row=1, column=1, sticky="ew")
        ttk.Button(f, text="Browse…", command=self.browse).grid(row=1, column=2, padx=(6, 0))
        ttk.Label(f, text="Part Number column").grid(row=2, column=0, sticky="w", pady=4)
        self.pn_box = ttk.Combobox(f, textvariable=self.pn, state="readonly", width=47)
        self.pn_box.grid(row=2, column=1, columnspan=2, sticky="ew")
        ttk.Label(f, text="Price column").grid(row=3, column=0, sticky="w", pady=4)
        self.price_box = ttk.Combobox(f, textvariable=self.price, state="readonly", width=47)
        self.price_box.grid(row=3, column=1, columnspan=2, sticky="ew")
        self.info = ttk.Label(f, text="", style="Hint.TLabel")
        self.info.grid(row=4, column=0, columnspan=3, sticky="w", pady=(6, 0))
        btns = ttk.Frame(f)
        btns.grid(row=5, column=0, columnspan=3, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(btns, text="OK", command=self.ok).pack(side="right", padx=6)
        self.load_headers()
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()

    def browse(self) -> None:
        p = filedialog.askopenfilename(parent=self, title="Choose CSV file",
                                       filetypes=[("CSV files", "*.csv *.txt *.tsv"), ("All files", "*.*")])
        if p:
            self.path.set(p)
            if not self.name.get():
                self.name.set(os.path.splitext(os.path.basename(p))[0])
            self.load_headers()

    def load_headers(self) -> None:
        p = self.path.get()
        headers = []
        if p and os.path.exists(p):
            try:
                db = CsvDatabase("tmp", p)
                db.load()
                headers = db.headers
                pn = detect_column(headers, PART_NUMBER_ALIASES) or "none"
                pr = detect_column(headers, PRICE_ALIASES) or "none"
                self.info.configure(text=f"{len(db.rows):,} rows · auto-detected → Part Number: {pn} · Price: {pr}")
            except Exception as exc:
                self.info.configure(text=f"Could not read file: {exc}")
        self.pn_box.configure(values=[AUTO] + headers)
        self.price_box.configure(values=[AUTO] + headers)

    def ok(self) -> None:
        if not self.path.get():
            messagebox.showwarning("myDB", "Please choose a CSV file.", parent=self)
            return
        self.result = {
            "name": self.name.get().strip() or os.path.basename(self.path.get()),
            "path": self.path.get(),
            "part_number_column": "" if self.pn.get() == AUTO else self.pn.get(),
            "price_column": "" if self.price.get() == AUTO else self.price.get(),
        }
        self.destroy()


class SettingsWindow(tk.Toplevel):
    def __init__(self, app: "App"):
        super().__init__(app.root)
        self.app = app
        self.title("myDB settings")
        self.minsize(760, 420)
        self.dbs = [dict(d) for d in app.cfg.get("databases", [])]
        f = ttk.Frame(self, padding=14)
        f.pack(fill="both", expand=True)

        ttk.Label(f, text="Databases (CSV files)", style="Title.TLabel").pack(anchor="w")
        ttk.Label(f, text="Removing a database only removes it from this list — the CSV file itself is never touched.",
                  style="Hint.TLabel").pack(anchor="w", pady=(0, 6))
        mid = ttk.Frame(f)
        mid.pack(fill="both", expand=True)
        cols = ("name", "path", "pn", "price")
        self.tree = ttk.Treeview(mid, columns=cols, show="headings", height=7, selectmode="browse")
        for c, t, w in zip(cols, ("Name", "File", "Part Number col.", "Price col."), (160, 330, 120, 110)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w)
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<Double-Button-1>", lambda e: self.edit())
        side = ttk.Frame(mid, padding=(8, 0, 0, 0))
        side.pack(side="left", fill="y")
        for text, cmd in (("Add…", self.add), ("Edit…", self.edit), ("Remove", self.remove),
                          ("Move up", lambda: self.move(-1)), ("Move down", lambda: self.move(1))):
            ttk.Button(side, text=text, command=cmd, width=12).pack(pady=2)

        opts = ttk.LabelFrame(f, text="Options", padding=10)
        opts.pack(fill="x", pady=(12, 0))
        self.hotkey = tk.StringVar(value=app.cfg.get("hotkey", "<ctrl>+<shift>+s"))
        self.auto_paste = tk.BooleanVar(value=bool(app.cfg.get("auto_paste")))
        self.fmt = tk.StringVar(value=app.cfg.get("all_info_format", "lines"))
        ttk.Label(opts, text="Hotkey").grid(row=0, column=0, sticky="w")
        ttk.Entry(opts, textvariable=self.hotkey, width=24).grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(opts, text="e.g. <ctrl>+<shift>+s, <ctrl>+<alt>+f", style="Hint.TLabel").grid(row=0, column=2, sticky="w")
        ttk.Checkbutton(opts, text="Auto-paste into the window I was working in (otherwise just copy to clipboard)",
                        variable=self.auto_paste).grid(row=1, column=0, columnspan=3, sticky="w", pady=4)
        ttk.Label(opts, text="\"All info\" format").grid(row=2, column=0, sticky="w")
        ttk.Combobox(opts, textvariable=self.fmt, values=("lines", "tsv", "json"), state="readonly",
                     width=10).grid(row=2, column=1, sticky="w", padx=6)
        ttk.Label(opts, text="lines = 'Header: value' · tsv = pastes as an Excel row · json",
                  style="Hint.TLabel").grid(row=2, column=2, sticky="w")

        btns = ttk.Frame(f)
        btns.pack(fill="x", pady=(12, 0))
        ttk.Label(btns, text=f"Settings file: {config_path()}", style="Hint.TLabel").pack(side="left")
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(btns, text="Save", command=self.save).pack(side="right", padx=6)
        self.refresh()

    def refresh(self, select: int | None = None) -> None:
        self.tree.delete(*self.tree.get_children())
        for i, d in enumerate(self.dbs):
            self.tree.insert("", "end", iid=str(i), values=(
                d["name"], d["path"], d.get("part_number_column") or AUTO, d.get("price_column") or AUTO))
        if select is not None and self.dbs:
            self.tree.selection_set(str(select))

    def _sel(self) -> int | None:
        s = self.tree.selection()
        return int(s[0]) if s else None

    def add(self) -> None:
        dlg = DbDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            self.dbs.append(dlg.result)
            self.refresh(len(self.dbs) - 1)

    def edit(self) -> None:
        i = self._sel()
        if i is None:
            return
        dlg = DbDialog(self, self.dbs[i])
        self.wait_window(dlg)
        if dlg.result:
            self.dbs[i] = dlg.result
            self.refresh(i)

    def remove(self) -> None:
        i = self._sel()
        if i is None:
            return
        if messagebox.askyesno("myDB", f"Remove '{self.dbs[i]['name']}' from the list?\n"
                                       "(The CSV file on disk is NOT deleted.)", parent=self):
            del self.dbs[i]
            self.refresh()

    def move(self, delta: int) -> None:
        i = self._sel()
        if i is None or not 0 <= i + delta < len(self.dbs):
            return
        self.dbs[i], self.dbs[i + delta] = self.dbs[i + delta], self.dbs[i]
        self.refresh(i + delta)

    def save(self) -> None:
        try:
            parse_hotkey(self.hotkey.get())
        except ValueError as exc:
            messagebox.showerror("myDB", str(exc), parent=self)
            return
        cfg = dict(self.app.cfg)
        cfg.update(databases=self.dbs, hotkey=self.hotkey.get().strip(),
                   auto_paste=self.auto_paste.get(), all_info_format=self.fmt.get())
        save_config(cfg)
        self.app.apply_config(cfg)
        self.destroy()


# ------------------------------------------------------------ main app
class App:
    def __init__(self, start_minimized: bool = False):
        system.setup_process()
        self.root = tk.Tk()
        self.root.title("myDB")
        self.font_big = {"win32": ("Segoe UI", 13), "darwin": ("Helvetica Neue", 15)}.get(sys.platform, ("DejaVu Sans", 12))
        self._style()
        self.cfg = load_config()
        self.cache: dict[tuple, CsvDatabase] = {}
        self.last_db_index = 0
        self.events: queue.Queue = queue.Queue()
        self.listener = None
        self.settings: SettingsWindow | None = None

        f = ttk.Frame(self.root, padding=16)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text=f"myDB  v{__version__}", style="Title.TLabel").pack(anchor="w")
        self.hotkey_label = ttk.Label(f, text="", wraplength=520, justify="left")
        self.hotkey_label.pack(anchor="w", pady=(4, 10))
        row = ttk.Frame(f)
        row.pack(fill="x")
        ttk.Button(row, text="Search now", command=self.open_search).pack(side="left")
        ttk.Button(row, text="Settings", command=self.open_settings).pack(side="left", padx=6)
        ttk.Button(row, text="Quit", command=self.quit).pack(side="right")
        self.status = ttk.Label(f, text="Ready.", style="Hint.TLabel")
        self.status.pack(anchor="w", pady=(10, 0))
        self.root.protocol("WM_DELETE_WINDOW", self.root.iconify)  # close = minimise; use Quit to exit
        self.popup = SearchPopup(self)
        if sys.platform == "darwin":  # ⌘Q and clicking the Dock icon
            self.root.createcommand("tk::mac::Quit", self.quit)
            self.root.createcommand("tk::mac::ReopenApplication", self.root.deiconify)
        self.apply_config(self.cfg)
        self.root.after(50, self._poll)
        if start_minimized:
            self.root.iconify()

    def _style(self) -> None:
        s = ttk.Style(self.root)
        if sys.platform == "darwin":
            pass  # keep the native Aqua theme (follows macOS light/dark mode)
        elif sys.platform == "win32" and "vista" in s.theme_names():
            s.theme_use("vista")
        elif "clam" in s.theme_names():
            s.theme_use("clam")
        s.configure("Title.TLabel", font=(self.font_big[0], 14, "bold"))
        s.configure("Hint.TLabel", font=(self.font_big[0], 11))
        if sys.platform != "darwin":  # on macOS let Aqua pick a colour that works in dark mode
            s.configure("Hint.TLabel", foreground="#666666")
        s.configure("Big.TButton", font=self.font_big, padding=8)
        s.configure("Treeview", rowheight=26)

    # ---- config / hotkey
    def apply_config(self, cfg: dict) -> None:
        self.cfg = cfg
        if self.listener:
            self.listener.stop()
            self.listener = None
        spec = cfg.get("hotkey", "<ctrl>+<shift>+s")
        try:
            self.listener = system.make_hotkey(spec, lambda: self.events.put("search"))
            self.listener.start()
            msg = f"Press {pretty_hotkey(spec)} anywhere to search."
            if system.accessibility_trusted(prompt=True) is False:
                msg += ("\n⚠ macOS has not granted Accessibility permission yet: open System Settings → "
                        "Privacy & Security → Accessibility, enable myDB (or your Terminal), then restart myDB.")
            self.hotkey_label.configure(text=msg)
        except Exception as exc:  # missing dependency, no display server, etc.
            self.listener = None
            self.hotkey_label.configure(text=f"Global hotkey unavailable ({exc}). Use 'Search now'.")

    def _poll(self) -> None:
        try:
            while True:
                if self.events.get_nowait() == "search":
                    self.open_search()
        except queue.Empty:
            pass
        self.root.after(50, self._poll)

    # ---- actions
    def get_database(self, index: int) -> CsvDatabase:
        d = self.cfg["databases"][index]
        key = (d["path"], d.get("part_number_column", ""), d.get("price_column", ""), d["name"])
        db = self.cache.get(key)
        if db is None:
            db = CsvDatabase(d["name"], d["path"], d.get("part_number_column") or None,
                             d.get("price_column") or None, d.get("delimiter") or None)
            self.cache[key] = db
        db.load()  # cheap if the file has not changed
        return db

    def open_search(self) -> None:
        if self.popup.winfo_viewable():
            self.popup._present()
            return
        self.popup.open()

    def open_settings(self) -> None:
        if self.settings and self.settings.winfo_exists():
            self.settings.lift()
            return
        self.settings = SettingsWindow(self)

    def copy_to_clipboard(self, text: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()

    def paste_into(self, prev_app) -> None:
        def do_paste():
            try:
                system.send_paste()
            except Exception as exc:
                self.set_status(f"Copied, but auto-paste failed: {exc}")
        system.restore_frontmost(prev_app)
        self.root.after(250, do_paste)

    def set_status(self, text: str) -> None:
        self.status.configure(text=text)

    def quit(self) -> None:
        if self.listener:
            self.listener.stop()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    ap = argparse.ArgumentParser(description="myDB quick CSV search")
    ap.add_argument("--minimized", action="store_true", help="start minimised (for auto-start)")
    ap.add_argument("--search", action="store_true", help="open the search popup immediately")
    args = ap.parse_args()
    app = App(start_minimized=args.minimized)
    if args.search:
        app.root.after(300, app.open_search)
    app.run()


if __name__ == "__main__":
    main()
