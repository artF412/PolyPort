"""
PLY Converter GUI
Convert PLY files (meshes & point clouds, including 3DGS format) to OBJ or FBX.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from pathlib import Path
import sys
import os

sys.path.insert(0, str(Path(__file__).parent))
from converter import PLYConverter, check_dependencies, read_ply


# ── Colour palette ─────────────────────────────────────────────────────────
BG          = "#1e1e2e"
SURFACE     = "#2a2a3e"
ACCENT      = "#7c6af7"
ACCENT_DARK = "#5a4bd4"
TEXT        = "#cdd6f4"
TEXT_DIM    = "#6c7086"
SUCCESS     = "#a6e3a1"
ERROR       = "#f38ba8"
WARNING     = "#f9e2af"
BORDER      = "#45475a"


class PLYConverterApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PLY Converter  ·  Maya & Blender")
        self.root.geometry("780x640")
        self.root.minsize(680, 560)
        self.root.configure(bg=BG)

        # State
        self.input_file    = tk.StringVar()
        self.output_dir    = tk.StringVar()
        self.output_format = tk.StringVar(value="obj")
        self._converting   = False

        self._build_styles()
        self._build_ui()
        self._check_deps()

    # ── Styles ───────────────────────────────────────────────────────────
    def _build_styles(self):
        s = ttk.Style(self.root)
        s.theme_use("clam")

        s.configure(".",
                     background=BG,
                     foreground=TEXT,
                     fieldbackground=SURFACE,
                     font=("Segoe UI", 10))

        s.configure("TFrame",      background=BG)
        s.configure("TLabelframe", background=BG,  relief="flat",
                     borderwidth=1)
        s.configure("TLabelframe.Label",
                     background=BG, foreground=ACCENT,
                     font=("Segoe UI", 9, "bold"))

        s.configure("TEntry",
                     fieldbackground=SURFACE, foreground=TEXT,
                     insertcolor=TEXT, relief="flat", borderwidth=0)
        s.map("TEntry", fieldbackground=[("focus", "#32324a")])

        s.configure("TButton",
                     background=SURFACE, foreground=TEXT,
                     relief="flat", borderwidth=0, padding=(10, 6))
        s.map("TButton",
              background=[("active", BORDER), ("pressed", BORDER)])

        s.configure("Accent.TButton",
                     background=ACCENT, foreground="#ffffff",
                     font=("Segoe UI", 11, "bold"),
                     relief="flat", padding=(20, 8))
        s.map("Accent.TButton",
              background=[("active", ACCENT_DARK), ("pressed", ACCENT_DARK),
                          ("disabled", BORDER)])

        s.configure("TRadiobutton",
                     background=SURFACE, foreground=TEXT,
                     indicatorcolor=ACCENT, font=("Segoe UI", 10))
        s.map("TRadiobutton",
              background=[("active", SURFACE)],
              indicatorcolor=[("selected", ACCENT)])

        s.configure("TProgressbar",
                     background=ACCENT, troughcolor=SURFACE,
                     bordercolor=SURFACE, darkcolor=ACCENT,
                     lightcolor=ACCENT, thickness=6)

    # ── UI ───────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = self.root

        # ── Title bar ────────────────────────────────────────────────────
        header = tk.Frame(root, bg=SURFACE, height=56)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="PLY Converter",
                 bg=SURFACE, fg=TEXT,
                 font=("Segoe UI", 18, "bold")).pack(side="left", padx=20, pady=10)
        tk.Label(header,
                 text="Maya · Blender",
                 bg=SURFACE, fg=TEXT_DIM,
                 font=("Segoe UI", 10)).pack(side="left", pady=10)

        # ── Main content ─────────────────────────────────────────────────
        content = tk.Frame(root, bg=BG)
        content.pack(fill="both", expand=True, padx=24, pady=18)
        content.columnconfigure(0, weight=1)

        # Input file
        self._section_label(content, "Input PLY File", row=0)
        input_row = tk.Frame(content, bg=BG)
        input_row.grid(row=1, column=0, sticky="ew", pady=(4, 16))
        input_row.columnconfigure(0, weight=1)

        self._entry(input_row, self.input_file, col=0)
        self._btn(input_row, "Browse…", self._browse_input, col=1)

        # File info label (shown after file selected)
        self.info_var = tk.StringVar()
        self.info_lbl = tk.Label(content, textvariable=self.info_var,
                                  bg=BG, fg=TEXT_DIM,
                                  font=("Segoe UI", 9), anchor="w",
                                  justify="left", wraplength=680)
        self.info_lbl.grid(row=2, column=0, sticky="ew", pady=(0, 10))

        # Output directory
        self._section_label(content, "Output Directory", row=3)
        out_row = tk.Frame(content, bg=BG)
        out_row.grid(row=4, column=0, sticky="ew", pady=(4, 16))
        out_row.columnconfigure(0, weight=1)

        self._entry(out_row, self.output_dir, col=0)
        self._btn(out_row, "Browse…", self._browse_output, col=1)

        # Format selection
        fmt_frame = ttk.LabelFrame(content, text="Export Format", padding=12)
        fmt_frame.grid(row=5, column=0, sticky="ew", pady=(0, 16))
        fmt_frame.columnconfigure(1, weight=1)

        self._radio(fmt_frame, "OBJ — Wavefront Object",
                    "obj",
                    "Universal 3D format · vertex colors · Maya & Blender",
                    row=0)
        self._radio(fmt_frame, "FBX — Filmbox ASCII",
                    "fbx",
                    "Native Maya format · vertex colors · also Blender",
                    row=1)

        # Progress bar
        self.progress = ttk.Progressbar(content, mode="determinate",
                                         style="TProgressbar", maximum=100)
        self.progress.grid(row=6, column=0, sticky="ew", pady=(0, 12))

        # Status log
        log_frame = ttk.LabelFrame(content, text="Log", padding=6)
        log_frame.grid(row=7, column=0, sticky="nsew", pady=(0, 16))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        content.rowconfigure(7, weight=1)

        self.log_box = tk.Text(log_frame, height=7, wrap="word",
                               bg=SURFACE, fg=TEXT, insertbackground=TEXT,
                               font=("Consolas", 9), state="disabled",
                               relief="flat", borderwidth=0,
                               selectbackground=ACCENT)
        sb = ttk.Scrollbar(log_frame, command=self.log_box.yview)
        self.log_box.configure(yscrollcommand=sb.set)
        self.log_box.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")

        # Configure log tag colours
        self.log_box.tag_configure("success", foreground=SUCCESS)
        self.log_box.tag_configure("error",   foreground=ERROR)
        self.log_box.tag_configure("warn",    foreground=WARNING)
        self.log_box.tag_configure("dim",     foreground=TEXT_DIM)

        # Convert button
        self.convert_btn = ttk.Button(content, text="Convert & Export",
                                       style="Accent.TButton",
                                       command=self._start_conversion)
        self.convert_btn.grid(row=8, column=0, pady=(0, 4))

    # ── Widget helpers ────────────────────────────────────────────────────
    def _section_label(self, parent, text, row):
        tk.Label(parent, text=text.upper(),
                 bg=BG, fg=TEXT_DIM,
                 font=("Segoe UI", 8, "bold")).grid(
                     row=row, column=0, sticky="w")

    def _entry(self, parent, var, col):
        frame = tk.Frame(parent, bg=BORDER, bd=0)
        frame.grid(row=0, column=col, sticky="ew", padx=(0, 8))
        frame.columnconfigure(0, weight=1)
        e = ttk.Entry(frame, textvariable=var, font=("Segoe UI", 10))
        e.pack(fill="x", padx=1, pady=1)

    def _btn(self, parent, text, cmd, col):
        ttk.Button(parent, text=text, command=cmd).grid(
            row=0, column=col, padx=(0, 0))

    def _radio(self, parent, label, value, hint, row):
        f = tk.Frame(parent, bg=SURFACE, bd=0)
        f.grid(row=row, column=0, columnspan=2, sticky="ew",
               pady=3, ipady=4, ipadx=8)
        f.columnconfigure(1, weight=1)

        rb = ttk.Radiobutton(f, text=label, variable=self.output_format,
                              value=value, style="TRadiobutton")
        rb.grid(row=0, column=0, sticky="w", padx=(8, 16))

        tk.Label(f, text=hint, bg=SURFACE, fg=TEXT_DIM,
                 font=("Segoe UI", 9)).grid(row=0, column=1, sticky="w")

    # ── Logging ───────────────────────────────────────────────────────────
    def _log(self, msg, tag=None, progress=None):
        """Thread-safe log writer."""
        def _do():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", msg + "\n", tag or "")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
            if progress is not None:
                self.progress["value"] = progress
        self.root.after(0, _do)

    def _callback(self, msg, progress=None):
        tag = None
        low = msg.lower()
        if low.startswith("success") or low.startswith("obj saved") or low.startswith("fbx saved"):
            tag = "success"
        elif low.startswith("error") or "failed" in low:
            tag = "error"
        elif low.startswith("warn") or "warning" in low or "missing" in low:
            tag = "warn"
        elif low.startswith("  "):
            tag = "dim"
        self._log(msg, tag=tag, progress=progress)

    # ── Actions ───────────────────────────────────────────────────────────
    def _browse_input(self):
        path = filedialog.askopenfilename(
            title="Select PLY File",
            filetypes=[("PLY Files", "*.ply"), ("All Files", "*.*")])
        if path:
            self.input_file.set(path)
            if not self.output_dir.get():
                self.output_dir.set(str(Path(path).parent))
            self._log(f"Selected: {path}", tag="dim")
            # Show file info in background
            threading.Thread(target=self._load_file_info, args=(path,),
                             daemon=True).start()

    def _browse_output(self):
        d = filedialog.askdirectory(title="Select Output Directory")
        if d:
            self.output_dir.set(d)

    def _load_file_info(self, path):
        """Read PLY header info and show in UI (runs in background thread)."""
        try:
            from plyfile import PlyData
            ply = PlyData.read(path)
            vert_el = ply["vertex"]
            props = [p.name for p in vert_el.properties]
            n_v = len(vert_el.data)
            n_f = len(ply["face"].data) if "face" in ply else 0
            has_3dgs = "f_dc_0" in props
            has_col  = "red" in props or has_3dgs
            has_norm = "nx" in props
            info = (
                f"Vertices: {n_v:,}  ·  Faces: {n_f:,}  ·  "
                f"Colors: {'yes' if has_col else 'no'}  ·  "
                f"Normals: {'yes' if has_norm else 'no'}"
                + ("  ·  3DGS format detected" if has_3dgs else "")
            )
            self.root.after(0, lambda: self.info_var.set(info))
        except Exception as e:
            self.root.after(0, lambda: self.info_var.set(f"Could not read info: {e}"))

    def _check_deps(self):
        missing = check_dependencies()
        if missing:
            self._log(f"Missing packages: {', '.join(missing)}", tag="warn")
            self._log(f"Run: python -m pip install {' '.join(missing)}", tag="warn")
        else:
            self._log("Dependencies OK. Ready.", tag="dim")

    def _start_conversion(self):
        if self._converting:
            return

        inp = self.input_file.get().strip()
        out = self.output_dir.get().strip()
        fmt = self.output_format.get()

        if not inp:
            messagebox.showerror("Missing Input", "Please select a PLY file first.")
            return
        if not Path(inp).exists():
            messagebox.showerror("File Not Found", f"File does not exist:\n{inp}")
            return
        if not out:
            messagebox.showerror("Missing Output", "Please select an output directory.")
            return

        self._converting = True
        self.convert_btn.configure(state="disabled")
        self.progress["value"] = 0
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        self._log(f"\n{'─'*50}", tag="dim")
        self._log(f"Starting {fmt.upper()} conversion…")

        threading.Thread(target=self._run_conversion,
                         args=(inp, out, fmt), daemon=True).start()

    def _run_conversion(self, inp, out, fmt):
        try:
            # Switch to determinate mode once we start writing
            def cb(msg, progress=None):
                if progress is not None and self.progress["mode"] == "indeterminate":
                    self.root.after(0, self._switch_to_determinate)
                self._callback(msg, progress=progress)

            converter = PLYConverter(callback=cb)
            output_path = converter.convert(inp, out, fmt)
            self.root.after(0, self._on_success, output_path)
        except Exception as exc:
            self.root.after(0, self._on_error, str(exc))

    def _switch_to_determinate(self):
        self.progress.stop()
        self.progress.configure(mode="determinate")

    def _on_success(self, output_path):
        self._converting = False
        self.convert_btn.configure(state="normal")
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress["value"] = 100
        self._log(f"Done!  →  {output_path}", tag="success")
        messagebox.showinfo(
            "Conversion Complete",
            f"File saved to:\n{output_path}")

    def _on_error(self, error):
        self._converting = False
        self.convert_btn.configure(state="normal")
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress["value"] = 0
        self._log(f"ERROR: {error}", tag="error")
        messagebox.showerror("Conversion Failed", f"Error:\n{error}")


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()

    # Attempt high-DPI support on Windows
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    app = PLYConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
