"""
Just Shapes & Beats  —  Save Editor
=====================================
Merged from:
  • saltsalads' bp-patcher  (byte-level insight)
  • discord C# snippet      (confirmed XOR layer exists)
  • Our own JSaB-Editor.py  (full decode/encode pipeline)

IMPORTANT — Steam Cloud:
  The game will overwrite your save on launch if Steam Cloud sync is active.
  Disable it before using this tool:
    Steam → Library → Just Shapes and Beats → right-click → Properties
    → General → uncheck "Keep game saves in the Steam Cloud for …"
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, font as tkfont


KNOWN_HEADERS = [
    bytes([0xD8, 0xD8, 0x02]),
    bytes([0xEA, 0xBF, 0x02]),
]
_active_header = KNOWN_HEADERS[0]

_VOWELS = set('aeiouAEIOU')

def _should_shift(ch):
    if ch in _VOWELS or not ch.isalpha():
        return False
    lower = ch.lower()
    base  = ord('a')
    m2 = chr((ord(lower) - base - 2) % 26 + base)
    p2 = chr((ord(lower) - base + 2) % 26 + base)
    return m2 not in _VOWELS and p2 not in _VOWELS

def _shift(ch, d):
    if not _should_shift(ch):
        return ch
    base = ord('A') if ch.isupper() else ord('a')
    return chr((ord(ch) - base + d) % 26 + base)

def _map_obj(obj, d):
    if isinstance(obj, dict):
        return {''.join(_shift(c, d) for c in k): _map_obj(v, d)
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [_map_obj(i, d) for i in obj]
    if isinstance(obj, str):
        return ''.join(_shift(c, d) for c in obj)
    return obj

def _decode_body(body_utf8):
    shifted = ''.join(chr(ord(c) - 0x7F) for c in body_utf8)
    result, in_string, i = [], False, 0
    while i < len(shifted):
        c = shifted[i]
        if c == '$':
            result.append('"');  in_string = not in_string
        elif in_string:
            result.append(c)
        else:
            if c == '<':
                result.append(':')
            elif c == '.':
                result.append(',')
            elif c == ':':
                nxt          = shifted[i + 1] if i + 1 < len(shifted) else ''
                prev_is_digit = bool(result) and result[-1].isdigit()
                if prev_is_digit and (nxt == '.' or nxt in ('}', ']', '$', ':')):
                    pass  # trailing colon after float digits (game artifact) — skip
                elif not prev_is_digit and (nxt == '.' or nxt in ('}', ']', '$')):
                    result.append('0');  result.append('.0')
                elif prev_is_digit:
                    result.append('.')
                else:
                    result.append('0.')
            else:
                result.append(c)
        i += 1
    s = ''.join(result)
    s = re.sub(r'\bhanse\b', 'false', s)
    s = re.sub(r'\bvtue\b',  'true',  s)
    return s

def _encode_body(json_str):
    json_str = json_str.replace('false', 'hanse').replace('true', 'vtue')
    result, in_string, i = [], False, 0
    while i < len(json_str):
        c = json_str[i]
        if c == '"':
            result.append('$');  in_string = not in_string
        elif in_string:
            result.append(c)
        else:
            if c == ':':
                result.append('<')
            elif c == ',':
                result.append('.')
            elif c == '.':
                leading_zero = (result and result[-1] == '0'
                                and (len(result) < 2 or not result[-2].isdigit()))
                if leading_zero:
                    result.pop()
                result.append(':')
                if (i + 1 < len(json_str) and json_str[i + 1] == '0'
                        and i + 2 < len(json_str)
                        and json_str[i + 2] in (',', '}', ']')):
                    i += 1   # skip trailing zero of 0.0, keep separator
            else:
                result.append(c)
        i += 1
    obf = ''.join(result)
    return ''.join(chr(ord(c) + 0x7F) for c in obf)

def load_save(path):
    """Read a save file → returns (header_bytes, decoded_dict)."""
    global _active_header
    with open(path, 'rb') as f:
        raw = f.read()
    if len(raw) < 3 or raw[2] != 0x02:
        raise ValueError(f"Not a valid save file (header: {raw[:3].hex()})")
    _active_header = raw[:3]
    obj = _map_obj(json.loads(_decode_body(raw[3:].decode('utf-8'))), -2)
    return obj

def save_to_file(obj, path):
    """Encode decoded_dict and write to path."""
    compact = json.dumps(_map_obj(obj, +2), separators=(',', ':'),
                         ensure_ascii=False)
    with open(path, 'wb') as f:
        f.write(_active_header)
        f.write(_encode_body(compact).encode('utf-8'))

def decode_to_json(src_path, dst_path):
    obj = load_save(src_path)
    with open(dst_path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

def encode_from_json(src_path, dst_path):
    with open(src_path, 'r', encoding='utf-8') as f:
        obj = json.load(f)
    save_to_file(obj, dst_path)


# ─────────────────────────────────────────────────────────────────────────────
#  Field definitions  (what to show in the Quick Edit panel)
# ─────────────────────────────────────────────────────────────────────────────

QUICK_FIELDS = [
    # (label, json_path_tuple, type)
    ("Beat Points (bp)",            ("metaPlayerProfile", "bp"),                          "int"),
    ("Challenges Completed",        ("metaPlayerProfile", "numChallengeCompleted"),        "int"),
    ("Friends Rescued",             ("metaPlayerProfile", "numChallengeFriendsRescued"),   "int"),
    ("Ribbons Awarded",             ("metaPlayerProfile", "numRibbonAwarded"),             "int"),
    ("Challenge Dash score",        ("metaPlayerProfile", "numChallengeDash"),             "float"),
    ("Levels Played",               ("metaStats",         "numLevelPlayed"),               "int"),
    ("Player Deaths",               ("metaStats",         "numPlayerDeath"),               "int"),
    ("Rewinds Used",                ("metaStats",         "numRewind"),                    "int"),
    ("Levels Cleared (normal)",     ("metaStats",         "numLevel1Cleared"),             "int"),
    ("Levels Cleared (hard)",       ("metaStats",         "numLevel3Cleared"),             "int"),
    ("Levels Cleared (expert)",     ("metaStats",         "numLevel4Cleared"),             "int"),
    ("Story Completed",             ("metaStoryProgress", "hasCompletedStoryMode"),        "bool"),
    ("Lost Chapter Completed",      ("metaStoryProgress", "hasCompletedLostChapter"),      "bool"),
]


# ─────────────────────────────────────────────────────────────────────────────
#  Theme
# ─────────────────────────────────────────────────────────────────────────────

BG         = "#0d1117"
BG2        = "#111820"
BG3        = "#0a1520"
ACCENT     = "#ff2d6b"
ACCENT_HO  = "#ff6096"
ACCENT2    = "#00b8d4"
ACCENT2_HO = "#33d4eb"
FG         = "#e8f4f8"
FG_DIM     = "#5a8a9f"
FG_HINT    = "#1e3a4a"
ENTRY_BG   = "#080d12"
BTN_FG     = "#ffffff"
SUCCESS    = "#00e5ff"
ERR        = "#ff2d6b"
WARN       = "#ffb700"

FONT       = ("Segoe UI", 10)
FONT_SM    = ("Segoe UI", 8)
FONT_BOLD  = ("Segoe UI Semibold", 10)
FONT_TITLE = ("Segoe UI Semibold", 13)
FONT_MONO  = ("Consolas", 10)

STEAM_HINT = r"C:\Program Files (x86)\Steam\userdata\{SteamID}\531510\remote"


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def styled_btn(parent, text, command, bg=ACCENT, width=None):
    kw = dict(text=text, command=command, bg=bg, fg=BTN_FG,
              font=FONT_BOLD, relief="flat", bd=0,
              padx=12, pady=6, cursor="hand2",
              activebackground=ACCENT_HO, activeforeground=BTN_FG)
    if width:
        kw["width"] = width
    b = tk.Button(parent, **kw)
    hover = ACCENT_HO if bg == ACCENT else (ACCENT2_HO if bg == ACCENT2 else "#555")
    b.bind("<Enter>", lambda e: b.config(bg=hover))
    b.bind("<Leave>", lambda e: b.config(bg=bg))
    return b

def sep(parent, pady=(16, 14)):
    tk.Frame(parent, height=1, bg=FG_HINT).pack(fill="x", pady=pady)

def section_lbl(parent, text):
    tk.Label(parent, text=text, bg=BG, fg=FG,
             font=FONT_BOLD).pack(anchor="w")

def status_lbl(parent):
    lbl = tk.Label(parent, text="", bg=BG, fg=FG_DIM, font=FONT_SM)
    lbl.pack(side="left", padx=12)
    return lbl

def set_status(lbl, text, color=FG_DIM):
    lbl.config(text=text, fg=color)

def get_nested(d, path):
    for key in path:
        d = d[key]
    return d

def set_nested(d, path, value):
    for key in path[:-1]:
        d = d[key]
    d[path[-1]] = value


# ─────────────────────────────────────────────────────────────────────────────
#  Main window
# ─────────────────────────────────────────────────────────────────────────────

class JSaBEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Just Shapes & Beats  —  Save Editor")
        self.configure(bg=BG)
        self.resizable(False, False)

        self._save_obj  = None   # decoded save data currently loaded
        self._src_path  = None   # path of the loaded save file
        self._tmp_json  = None   # path of temp JSON for notepad editing

        self._field_vars = {}    # label -> (tk.StringVar or tk.BooleanVar, type_str)
        self._digit_caps = {}    # label -> digit count of original value

        self._build()
        self._center()

    # ── layout ───────────────────────────────────────────────────────────────

    def _build(self):
        # ── Title bar ─────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=BG2, pady=8)
        hdr.pack(fill="x")
        tk.Label(hdr, text="🎵  JSaB Save Editor", bg=BG2, fg=FG,
                 font=FONT_TITLE).pack(side="left", padx=14)
        lnk = tk.Label(hdr, text="by tomandesMSH", bg=BG2, fg=ACCENT,
                        font=FONT_BOLD, cursor="hand2")
        lnk.pack(side="right", padx=14)
        lnk.bind("<Button-1>",
                 lambda e: __import__("webbrowser").open("https://github.com/tomandesmsh"))
        lnk.bind("<Enter>", lambda e: lnk.config(fg=ACCENT_HO))
        lnk.bind("<Leave>", lambda e: lnk.config(fg=ACCENT))

        # ── Steam Cloud warning ────────────────────────────────────────────────
        warn = tk.Frame(self, bg="#2a1500", pady=4)
        warn.pack(fill="x")
        tk.Label(warn,
                 text="If editing does not work try disabling Steam Cloud for JSaB it could overwrite saves on launch.",
                 bg="#2a1500", fg=WARN, font=FONT_SM).pack(padx=14, anchor="w")

        # ── Main body: LEFT + RIGHT columns ───────────────────────────────────
        body = tk.Frame(self, bg=BG, padx=14, pady=12)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=0, minsize=230)
        body.columnconfigure(1, weight=1)

        # ╔══ LEFT PANEL ══╗
        left = tk.Frame(body, bg=BG2, padx=12, pady=10,
                        highlightthickness=1, highlightbackground=FG_HINT)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        tk.Label(left, text="① Save File", bg=BG2, fg=FG,
                 font=FONT_BOLD).pack(anchor="w")
        tk.Label(left, text=r"…\userdata\{ID}\531510\remote",
                 bg=BG2, fg=FG_DIM, font=FONT_SM).pack(anchor="w", pady=(1, 6))

        self.src_var = tk.StringVar()
        tk.Entry(left, textvariable=self.src_var, bg=ENTRY_BG, fg=FG,
                 insertbackground=FG, relief="flat", font=FONT_MONO,
                 highlightthickness=1, highlightbackground=FG_HINT,
                 highlightcolor=ACCENT, width=26).pack(fill="x", ipady=5)

        brw_load = tk.Frame(left, bg=BG2)
        brw_load.pack(fill="x", pady=(5, 0))
        styled_btn(brw_load, "Browse…", self._browse_src, bg="#263040", width=8).pack(side="left")
        styled_btn(brw_load, "⬇ Load", self._do_load, bg=ACCENT, width=8).pack(side="right")

        self.load_status = tk.Label(left, text="", bg=BG2, fg=FG_DIM,
                                     font=FONT_SM, wraplength=200, justify="left")
        self.load_status.pack(anchor="w", pady=(5, 0))

        # divider
        tk.Frame(left, height=1, bg=FG_HINT).pack(fill="x", pady=10)

        # Output folder
        tk.Label(left, text="② Output Folder", bg=BG2, fg=FG,
                 font=FONT_BOLD).pack(anchor="w")
        tk.Label(left, text="Defaults to same folder as save",
                 bg=BG2, fg=FG_DIM, font=FONT_SM).pack(anchor="w", pady=(1, 6))

        self.dst_var = tk.StringVar()
        tk.Entry(left, textvariable=self.dst_var, bg=ENTRY_BG, fg=FG,
                 insertbackground=FG, relief="flat", font=FONT_MONO,
                 highlightthickness=1, highlightbackground=FG_HINT,
                 highlightcolor=ACCENT, width=26).pack(fill="x", ipady=5)

        styled_btn(left, "Browse…", self._browse_dst, bg="#263040").pack(anchor="w", pady=(5, 0))

        # divider
        tk.Frame(left, height=1, bg=FG_HINT).pack(fill="x", pady=10)

        # Advanced section (collapsible)
        adv_toggle = tk.Label(left, text="▶ Advanced (JSON edit)", bg=BG2,
                               fg=FG_DIM, font=FONT_SM, cursor="hand2")
        adv_toggle.pack(anchor="w")

        self._adv_frame = tk.Frame(left, bg=BG2)
        self._adv_visible = False

        def toggle_adv():
            if self._adv_visible:
                self._adv_frame.pack_forget()
                adv_toggle.config(text="▶ Advanced (JSON edit)")
                self._adv_visible = False
            else:
                self._adv_frame.pack(fill="x", pady=(5, 0))
                adv_toggle.config(text="▼ Advanced (JSON edit)")
                self._adv_visible = True

        adv_toggle.bind("<Button-1>", lambda e: toggle_adv())
        adv_toggle.bind("<Enter>", lambda e: adv_toggle.config(fg=FG))
        adv_toggle.bind("<Leave>", lambda e: adv_toggle.config(fg=FG_DIM))

        # Advanced panel contents (hidden by default)
        tk.Label(self._adv_frame, text="Decoded JSON path:", bg=BG2,
                 fg=FG_DIM, font=FONT_SM).pack(anchor="w", pady=(4, 2))
        self.json_var = tk.StringVar()
        jrow = tk.Frame(self._adv_frame, bg=BG2)
        jrow.pack(fill="x")
        tk.Entry(jrow, textvariable=self.json_var, bg=ENTRY_BG, fg=FG,
                 insertbackground=FG, relief="flat", font=FONT_MONO,
                 highlightthickness=1, highlightbackground=FG_HINT,
                 highlightcolor=ACCENT, width=18).pack(side="left", fill="x",
                                                        expand=True, ipady=4)
        styled_btn(jrow, "…", self._browse_json, bg="#263040", width=2).pack(side="left", padx=(4,0))

        np_row = tk.Frame(self._adv_frame, bg=BG2)
        np_row.pack(fill="x", pady=(5, 0))
        styled_btn(np_row, "Open Notepad", self._do_open_notepad,
                   bg="#333a55").pack(side="left")
        self.notepad_status = tk.Label(np_row, text="", bg=BG2, fg=FG_DIM,
                                        font=FONT_SM)
        self.notepad_status.pack(side="left", padx=6)

        enc_row = tk.Frame(self._adv_frame, bg=BG2)
        enc_row.pack(fill="x", pady=(5, 0))
        styled_btn(enc_row, "Encode & Save", self._do_encode_json,
                   bg="#1a6e8a").pack(side="left")
        self.encode_status = tk.Label(enc_row, text="", bg=BG2, fg=FG_DIM,
                                       font=FONT_SM)
        self.encode_status.pack(side="left", padx=6)

        # ╔══ RIGHT PANEL ══╗
        right = tk.Frame(body, bg=BG2, padx=12, pady=10,
                         highlightthickness=1, highlightbackground=FG_HINT)
        right.grid(row=0, column=1, sticky="nsew")

        tk.Label(right, text="③ Quick Edit", bg=BG2, fg=FG,
                 font=FONT_BOLD).pack(anchor="w")
        tk.Label(right, text="Load a save first, then edit and hit Save",
                 bg=BG2, fg=FG_DIM, font=FONT_SM).pack(anchor="w", pady=(1, 8))

        self._qf_frame = tk.Frame(right, bg=BG2)
        self._qf_frame.pack(fill="x")
        self._build_quick_fields(self._qf_frame, enabled=False)

        tk.Frame(right, height=1, bg=FG_HINT).pack(fill="x", pady=8)

        save_row = tk.Frame(right, bg=BG2)
        save_row.pack(fill="x")
        styled_btn(save_row, "💾  Save Changes", self._do_save_quick,
                   bg=ACCENT2).pack(side="left")
        self.save_status = tk.Label(save_row, text="", bg=BG2, fg=FG_DIM,
                                     font=FONT_SM)
        self.save_status.pack(side="left", padx=10)

    def _build_quick_fields(self, parent, enabled=True):
        """Build (or rebuild) the quick-edit grid."""
        for w in parent.winfo_children():
            w.destroy()
        self._field_vars.clear()

        state  = "normal" if enabled else "disabled"
        fg_lbl = FG if enabled else FG_DIM
        dis_bg = "#0a0f14"
        dis_fg = "#2a4a5a"

        cols = 2
        for idx, (label, path, typ) in enumerate(QUICK_FIELDS):
            r = idx // cols
            c = idx % cols

            cell = tk.Frame(parent, bg=BG2)
            cell.grid(row=r, column=c, sticky="ew",
                      padx=(0, 12 if c == 0 else 0), pady=3)
            parent.columnconfigure(c, weight=1)

            tk.Label(cell, text=label, bg=BG2, fg=fg_lbl,
                     font=FONT_SM, anchor="w").pack(anchor="w")

            if typ == "bool":
                var = tk.BooleanVar()
                tk.Checkbutton(cell, variable=var, bg=BG2,
                               fg=FG, selectcolor=ENTRY_BG,
                               activebackground=BG2,
                               state=state, relief="flat").pack(anchor="w")
            else:
                var = tk.StringVar()
                tk.Entry(cell, textvariable=var,
                         bg=ENTRY_BG, fg=FG, insertbackground=FG,
                         relief="flat", font=FONT_MONO,
                         highlightthickness=1, highlightbackground=FG_HINT,
                         highlightcolor=ACCENT, state=state,
                         disabledbackground=dis_bg,
                         disabledforeground=dis_fg).pack(fill="x", ipady=3)

            self._field_vars[label] = (var, typ, path)

            if typ in ("int", "float") and enabled:
                cap = self._digit_caps.get(label)
                if cap:
                    max_val = "9" * cap
                    hint_text = f"max editable: {'9' * cap}  (depends on original digit count)"
                else:
                    hint_text = "load a save to see max"
                tk.Label(cell, text=hint_text, bg=BG2, fg=FG_HINT,
                         font=FONT_SM, anchor="w").pack(anchor="w")

        if not enabled:
            tk.Label(parent, text="← load a save to enable editing",
                     bg=BG2, fg=FG_HINT, font=FONT_SM).grid(
                         row=len(QUICK_FIELDS) // cols + 1, column=0,
                         columnspan=cols, sticky="w", pady=(4, 0))

    def _populate_quick_fields(self):
        """Fill quick-edit fields from _save_obj."""
        for label, (var, typ, path) in self._field_vars.items():
            try:
                val = get_nested(self._save_obj, path)
                if typ == "bool":
                    var.set(bool(val))
                else:
                    var.set(str(val))
                    if typ in ("int", "float"):
                        digits = len(str(int(float(str(val)))).lstrip('-')) or 1
                        self._digit_caps[label] = digits
            except (KeyError, TypeError):
                var.set("" if typ != "bool" else False)

    # ── file dialogs ─────────────────────────────────────────────────────────

    def _browse_src(self):
        p = filedialog.askopenfilename(
            title="Select save file",
            initialdir=r"C:\Program Files (x86)\Steam\userdata",
            filetypes=[("Save file", "JSBSave_SaveData"), ("All files", "*.*")])
        if p:
            self.src_var.set(p)

    def _browse_json(self):
        p = filedialog.askopenfilename(
            title="Select decoded JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if p:
            self.json_var.set(p)

    def _browse_dst(self):
        d = filedialog.askdirectory(title="Output folder")
        if d:
            self.dst_var.set(d)

    # ── actions ──────────────────────────────────────────────────────────────

    def _do_load(self):
        src = self.src_var.get().strip()
        if not src:
            messagebox.showwarning("No file", "Please select a save file first.")
            return
        if not os.path.isfile(src):
            messagebox.showerror("Not found", f"File not found:\n{src}")
            return
        try:
            self._save_obj = load_save(src)
            self._src_path = src
        except Exception as exc:
            set_status(self.load_status, f"✗  {exc}", ERR)
            return

        # Auto-fill output folder to same dir as source
        self.dst_var.set(os.path.dirname(src))

        # Write backup next to the source file
        bak_path = src + ".bak"
        try:
            import shutil
            shutil.copy2(src, bak_path)
            bak_note = f"  (backup → {os.path.basename(bak_path)})"
        except Exception as bak_err:
            bak_note = f"  (backup failed: {bak_err})"

        # Pre-compute digit caps from save data BEFORE building fields,
        # so the hint labels have values ready when widgets are created.
        self._digit_caps.clear()
        for label, path, typ in QUICK_FIELDS:
            if typ in ("int", "float"):
                try:
                    val = get_nested(self._save_obj, path)
                    digits = len(str(int(float(str(val)))).lstrip('-')) or 1
                    self._digit_caps[label] = digits
                except (KeyError, TypeError):
                    pass

        self._build_quick_fields(self._qf_frame, enabled=True)
        self._populate_quick_fields()

        set_status(self.load_status, f"✓  Loaded successfully{bak_note}", SUCCESS)

    def _do_save_quick(self):
        if self._save_obj is None:
            messagebox.showwarning("Not loaded", "Load a save file first.")
            return

        errors = []
        for label, (var, typ, path) in self._field_vars.items():
            raw = var.get()
            try:
                if typ == "int":
                    set_nested(self._save_obj, path, int(raw))
                elif typ == "float":
                    set_nested(self._save_obj, path, float(raw))
                elif typ == "bool":
                    set_nested(self._save_obj, path, bool(raw))
            except (ValueError, KeyError) as e:
                errors.append(f"  {label}: {e}")

        if errors:
            messagebox.showerror("Invalid values", "Fix these fields:\n" + "\n".join(errors))
            return

        dst = self.dst_var.get().strip()
        if not dst:
            # Default: overwrite source
            dst = os.path.dirname(self._src_path)
        if not os.path.isdir(dst):
            messagebox.showerror("Bad folder", f"Folder not found:\n{dst}")
            return

        out = os.path.join(dst, "JSBSave_SaveData")
        try:
            save_to_file(self._save_obj, out)
        except Exception as exc:
            set_status(self.save_status, f"✗  {exc}", ERR)
            return

        set_status(self.save_status, f"✓  Saved → {out}", SUCCESS)
        messagebox.showinfo("Saved", f"Save file written to:\n{out}")

    def _do_open_notepad(self):
        if self._save_obj is None:
            # Try to decode from whatever is in the src path
            src = self.src_var.get().strip()
            if not src or not os.path.isfile(src):
                messagebox.showwarning("No file", "Load a save file first (Step ①).")
                return
            try:
                self._save_obj = load_save(src)
                self._src_path = src
            except Exception as exc:
                set_status(self.notepad_status, f"✗  {exc}", ERR)
                return

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json",
                                          prefix="jsab_decoded_")
        tmp.close()
        self._tmp_json = tmp.name

        with open(self._tmp_json, 'w', encoding='utf-8') as f:
            json.dump(self._save_obj, f, indent=2, ensure_ascii=False)

        self.json_var.set(self._tmp_json)

        try:
            subprocess.Popen(["notepad.exe", self._tmp_json])
        except FileNotFoundError:
            subprocess.Popen(["xdg-open", self._tmp_json])

        set_status(self.notepad_status,
                   "✓  Opened — save in Notepad (Ctrl+S), then use Encode below.", SUCCESS)

    def _do_encode_json(self):
        json_path  = self.json_var.get().strip()
        dst_folder = self.dst_var.get().strip()

        if not json_path:
            messagebox.showwarning("No JSON", "Open/browse a decoded JSON file first.")
            return
        if not os.path.isfile(json_path):
            messagebox.showerror("Not found", f"JSON file not found:\n{json_path}")
            return
        if not dst_folder:
            messagebox.showwarning("No output folder", "Select an output folder (Step ④).")
            return
        if not os.path.isdir(dst_folder):
            messagebox.showerror("Bad folder", f"Folder not found:\n{dst_folder}")
            return

        out = os.path.join(dst_folder, "JSBSave_SaveData")
        try:
            encode_from_json(json_path, out)
        except Exception as exc:
            set_status(self.encode_status, f"✗  {exc}", ERR)
            return

        # Verify by decoding and showing bp
        try:
            check = load_save(out)
            bp = check.get("metaPlayerProfile", {}).get("bp", "?")
            set_status(self.encode_status, f"✓  Written — bp={bp}", SUCCESS)
        except Exception:
            set_status(self.encode_status, f"✓  Written to {out}", SUCCESS)

        messagebox.showinfo("Done", f"Encoded save written to:\n{out}")

    # ── utils ─────────────────────────────────────────────────────────────────

    def _center(self):
        self.update_idletasks()
        w, h   = self.winfo_width(),        self.winfo_height()
        sw, sh = self.winfo_screenwidth(),  self.winfo_screenheight()
        self.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = JSaBEditor()
    app.mainloop()
