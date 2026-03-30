import json
import os
import re
import subprocess
import sys
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

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
        return {''.join(_shift(c, d) for c in k): _map_obj(v, d) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_map_obj(i, d) for i in obj]
    if isinstance(obj, str):
        return ''.join(_shift(c, d) for c in obj)
    return obj

def decode_body(body_utf8):
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
                if not prev_is_digit and (nxt == '.' or nxt in ('}', ']', '$')):
                    result.append('0'); result.append('.0')
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

def decode(input_path, output_path):
    global _active_header
    with open(input_path, 'rb') as f:
        raw = f.read()
    if len(raw) < 3 or raw[2] != 0x02:
        raise ValueError(f"Not a valid save file (bad header: {raw[:3].hex()})")
    _active_header = raw[:3]
    obj = _map_obj(json.loads(decode_body(raw[3:].decode('utf-8'))), -2)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

def encode_body(json_str):
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
                        and i + 2 < len(json_str) and json_str[i + 2] in (',', '}', ']')):
                    i += 1
            else:
                result.append(c)
        i += 1
    obf = ''.join(result)
    return ''.join(chr(ord(c) + 0x7F) for c in obf)

def encode(input_path, output_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        obj = json.load(f)
    compact = json.dumps(_map_obj(obj, +2), separators=(',', ':'), ensure_ascii=False)
    with open(output_path, 'wb') as f:
        f.write(_active_header)
        f.write(encode_body(compact).encode('utf-8'))


STEAM_HINT = r"C:\Program Files (x86)\Steam\userdata\{YOUR SteamID}\531510\remote"

BG        = "#0d1117"
BG2       = "#111820"
ACCENT    = "#ff2d6b"
ACCENT_HO = "#ff6096"
FG        = "#e8f4f8"
FG_DIM    = "#5a8a9f"
FG_HINT   = "#1e3a4a"
ENTRY_BG  = "#080d12"
BTN_FG    = "#ffffff"
SUCCESS   = "#00e5ff"
ERR       = "#ff2d6b"
RADIUS    = 6
FONT      = ("Segoe UI", 10)
FONT_SM   = ("Segoe UI", 8)
FONT_HEAD = ("Segoe UI Semibold", 10)
FONT_TITLE= ("Segoe UI Semibold", 13)

def styled_btn(parent, text, command, width=None, bg=ACCENT, fg=BTN_FG, font=FONT_HEAD):
    kw = dict(text=text, command=command, bg=bg, fg=fg, font=font,
              relief="flat", bd=0, padx=12, pady=6, cursor="hand2",
              activebackground=ACCENT_HO, activeforeground=BTN_FG)
    if width:
        kw["width"] = width
    b = tk.Button(parent, **kw)
    b.bind("<Enter>", lambda e: b.config(bg=ACCENT_HO))
    b.bind("<Leave>", lambda e: b.config(bg=bg))
    return b

def divider(parent):
    tk.Frame(parent, height=1, bg=FG_HINT).pack(fill="x", pady=(0, 0))

class JSBSaveTool(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Just Shapes and Beats Save Editor")
        self.configure(bg=BG)
        self.resizable(False, False)
        self._tmp_json = None
        self._build()
        self._center()

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw-w)//2}+{(sh-h)//2}")

    def _build(self):
        root = self
        hdr = tk.Frame(root, bg=BG2, pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text="🎵 JSaB Save Decoder/Encoder", bg=BG2, fg=FG,
                 font=FONT_TITLE).pack(side="left", padx=18)
        link = tk.Label(hdr, text="by tomandesMSH", bg=BG2, fg=ACCENT,
                font=FONT_HEAD, cursor="hand2")
        link.pack(side="right", padx=18)
        link.bind("<Button-1>", lambda e: __import__("webbrowser").open("https://github.com/tomandesmsh"))
        link.bind("<Enter>", lambda e: link.config(fg=ACCENT_HO))
        link.bind("<Leave>", lambda e: link.config(fg=ACCENT))
        card = tk.Frame(root, bg=BG, padx=24, pady=20)
        card.pack(fill="both", expand=True)

        self._section_label(card, "① Locate the encoded save file")

        row1 = tk.Frame(card, bg=BG)
        row1.pack(fill="x", pady=(6, 0))

        self.src_var = tk.StringVar()
        src_entry = tk.Entry(row1, textvariable=self.src_var,
                             bg=ENTRY_BG, fg=FG, insertbackground=FG,
                             relief="flat", font=FONT,
                             highlightthickness=1, highlightbackground=FG_HINT,
                             highlightcolor=ACCENT)
        src_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))

        styled_btn(row1, "Browse…", self._browse_src, width=10).pack(side="left")

        tk.Label(card,
                 text=f"Usually found at: {STEAM_HINT}",
                 bg=BG, fg=FG_DIM, font=FONT_SM,
                 wraplength=560, justify="left"
                 ).pack(anchor="w", pady=(4, 0))

        btn_row = tk.Frame(card, bg=BG)
        btn_row.pack(fill="x", pady=(14, 0))

        decode_btn = styled_btn(btn_row, "Decode & Open in Notepad",
                                self._do_decode, bg=ACCENT)
        decode_btn.pack(side="left")

        self.decode_status = tk.Label(btn_row, text="", bg=BG, fg=FG_DIM,
                                      font=FONT_SM)
        self.decode_status.pack(side="left", padx=12)

        tk.Frame(card, height=1, bg=FG_HINT).pack(fill="x", pady=(20, 16))

        self._section_label(card, "② Edited JSON file - Remember to save in notepad! (Ctrl+S)")

        row2 = tk.Frame(card, bg=BG)
        row2.pack(fill="x", pady=(6, 0))

        self.json_var = tk.StringVar()
        json_entry = tk.Entry(row2, textvariable=self.json_var,
                              bg=ENTRY_BG, fg=FG, insertbackground=FG,
                              relief="flat", font=FONT,
                              highlightthickness=1, highlightbackground=FG_HINT,
                              highlightcolor=ACCENT)
        json_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))

        styled_btn(row2, "Browse…", self._browse_json, width=10).pack(side="left")

        tk.Label(card,
                 text="If you used the Decode button above, this field is filled automatically.",
                 bg=BG, fg=FG_DIM, font=FONT_SM
                 ).pack(anchor="w", pady=(4, 0))

        tk.Frame(card, height=1, bg=FG_HINT).pack(fill="x", pady=(20, 16))

        self._section_label(card, "③ Save encoded file to…")

        row3 = tk.Frame(card, bg=BG)
        row3.pack(fill="x", pady=(6, 0))

        self.dst_var = tk.StringVar()
        dst_entry = tk.Entry(row3, textvariable=self.dst_var,
                             bg=ENTRY_BG, fg=FG, insertbackground=FG,
                             relief="flat", font=FONT,
                             highlightthickness=1, highlightbackground=FG_HINT,
                             highlightcolor=ACCENT)
        dst_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))

        styled_btn(row3, "Browse…", self._browse_dst, width=10).pack(side="left")

        tk.Label(card,
                 text="Choose the folder where the encoded save will be written (filename: JSBSave_SaveData).",
                 bg=BG, fg=FG_DIM, font=FONT_SM, wraplength=560, justify="left"
                 ).pack(anchor="w", pady=(4, 0))

        enc_row = tk.Frame(card, bg=BG)
        enc_row.pack(fill="x", pady=(14, 0))

        styled_btn(enc_row, "⬆  Encode & Save",
                   self._do_encode, bg="#00b8d4").pack(side="left")

        self.encode_status = tk.Label(enc_row, text="", bg=BG, fg=FG_DIM,
                                      font=FONT_SM)
        self.encode_status.pack(side="left", padx=12)

        tk.Frame(card, height=8, bg=BG).pack()

    def _section_label(self, parent, text):
        tk.Label(parent, text=text, bg=BG, fg=FG,
                 font=FONT_HEAD).pack(anchor="w")

    def _browse_src(self):
        path = filedialog.askopenfilename(
            title="Select encoded save file",
            initialdir=r"C:\Program Files (x86)\Steam\userdata",
            filetypes=[("Save files", "JSBSave_SaveData"), ("All files", "*.*")]
        )
        if path:
            self.src_var.set(path)

    def _browse_json(self):
        path = filedialog.askopenfilename(
            title="Select decoded JSON file",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if path:
            self.json_var.set(path)

    def _browse_dst(self):
        folder = filedialog.askdirectory(title="Choose output folder")
        if folder:
            self.dst_var.set(folder)

    def _do_decode(self):
        src = self.src_var.get().strip()
        if not src:
            messagebox.showwarning("No file", "Please select an encoded save file first.")
            return
        if not os.path.isfile(src):
            messagebox.showerror("Not found", f"File not found:\n{src}")
            return

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json",
                                          prefix="jsb_decoded_")
        tmp.close()
        self._tmp_json = tmp.name

        try:
            decode(src, self._tmp_json)
        except Exception as exc:
            self._status(self.decode_status, f"✗  {exc}", ERR)
            return

        self.json_var.set(self._tmp_json)

        try:
            subprocess.Popen(["notepad.exe", self._tmp_json])
        except FileNotFoundError:
            subprocess.Popen(["xdg-open", self._tmp_json])

        self._status(self.decode_status, "✓  Decoded. Edit in Notepad, then encode below.", SUCCESS)

    def _do_encode(self):
        json_path = self.json_var.get().strip()
        dst_folder = self.dst_var.get().strip()

        if not json_path:
            messagebox.showwarning("No JSON file", "Please select or decode a JSON file first.")
            return
        if not os.path.isfile(json_path):
            messagebox.showerror("Not found", f"JSON file not found:\n{json_path}")
            return
        if not dst_folder:
            messagebox.showwarning("No output folder", "Please choose an output folder.")
            return
        if not os.path.isdir(dst_folder):
            messagebox.showerror("Invalid folder", f"Folder not found:\n{dst_folder}")
            return

        out_path = os.path.join(dst_folder, "JSBSave_SaveData")

        try:
            encode(json_path, out_path)
        except Exception as exc:
            self._status(self.encode_status, f"✗  {exc}", ERR)
            return

        self._status(self.encode_status, f"✓  Saved to {out_path}", SUCCESS)
        messagebox.showinfo("Done", f"Encoded save written to:\n{out_path}")

    @staticmethod
    def _status(label, text, color):
        label.config(text=text, fg=color)

if __name__ == "__main__":
    app = JSBSaveTool()
    app.mainloop()
