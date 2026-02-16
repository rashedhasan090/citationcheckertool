#!/usr/bin/env python3
"""
Citation Checker - Desktop GUI (Tkinter). Run: python gui_desktop.py
"""

import sys
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
from pathlib import Path

# Allow running from repo root or from citation_checker/
sys.path.insert(0, str(Path(__file__).resolve().parent))

from citation_checker import (
    CitationChecker,
    parse_citations,
    export_json,
    export_csv,
    export_pdf,
)


def run_check():
    text = input_text.get("1.0", tk.END).strip()
    if not text:
        messagebox.showwarning("No input", "Paste citations in the text area first.")
        return
    citations, fmt = parse_citations(text)
    if not citations:
        messagebox.showerror("Parse error", "No citations could be parsed.")
        return
    checker = CitationChecker(
        check_doi_online=var_doi.get(),
        check_url_online=var_url.get(),
    )
    results = checker.check_many(citations)
    # Clear and show results
    result_text.delete("1.0", tk.END)
    summary = {}
    for r in results:
        summary[r.status] = summary.get(r.status, 0) + 1
    result_text.insert(tk.END, f"Format: {fmt} | Parsed: {len(citations)}\n")
    result_text.insert(tk.END, "Summary: " + ", ".join(f"{s}: {c}" for s, c in sorted(summary.items())) + "\n\n")
    for r in results:
        icon = {"valid": "[OK]", "warning": "[!]", "suspected_fake": "[?FAKE]"}.get(r.status, "[?]")
        result_text.insert(tk.END, f"{icon} #{r.index} {r.status}\n")
        if r.doi:
            result_text.insert(tk.END, f"  DOI: {r.doi} (resolved: {r.doi_resolved})\n")
        if r.issues:
            for i in r.issues:
                result_text.insert(tk.END, f"  Issue: {i}\n")
        if r.suggestions:
            for s in r.suggestions:
                result_text.insert(tk.END, f"  Fix: {s}\n")
        result_text.insert(tk.END, "\n")
    root.results = results


def export_report():
    if not getattr(root, "results", None):
        messagebox.showwarning("No results", "Run a check first.")
        return
    path = filedialog.asksaveasfilename(
        defaultextension=".json",
        filetypes=[
            ("JSON report", "*.json"),
            ("CSV report", "*.csv"),
            ("PDF report", "*.pdf"),
            ("All files", "*.*"),
        ],
    )
    if not path:
        return
    try:
        p = Path(path)
        if p.suffix.lower() == ".json":
            export_json(root.results, path)
        elif p.suffix.lower() == ".csv":
            export_csv(root.results, path)
        elif p.suffix.lower() == ".pdf":
            export_pdf(root.results, path)
        else:
            export_json(root.results, path)
        messagebox.showinfo("Exported", f"Report saved to {path}")
    except Exception as e:
        messagebox.showerror("Export failed", str(e))


root = tk.Tk()
root.title("Citation Checker")
root.geometry("900x700")
root.results = None

# Options
opt_frame = ttk.Frame(root, padding=5)
opt_frame.pack(fill=tk.X)
var_doi = tk.BooleanVar(value=True)
var_url = tk.BooleanVar(value=True)
ttk.Checkbutton(opt_frame, text="Validate DOI online", variable=var_doi).pack(side=tk.LEFT, padx=5)
ttk.Checkbutton(opt_frame, text="Check URL accessibility", variable=var_url).pack(side=tk.LEFT, padx=5)
ttk.Button(opt_frame, text="Check citations", command=run_check).pack(side=tk.LEFT, padx=10)
ttk.Button(opt_frame, text="Export report…", command=export_report).pack(side=tk.LEFT, padx=5)

# Input
ttk.Label(root, text="Paste citations (BibTeX, APA, or one per line):").pack(anchor=tk.W, padx=5, pady=(5, 0))
input_text = scrolledtext.ScrolledText(root, height=12, wrap=tk.WORD, font=("Consolas", 10))
input_text.pack(fill=tk.BOTH, expand=False, padx=5, pady=5)

# Results
ttk.Label(root, text="Status & report:").pack(anchor=tk.W, padx=5, pady=(5, 0))
result_text = scrolledtext.ScrolledText(root, height=20, wrap=tk.WORD, font=("Consolas", 10))
result_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

root.mainloop()
