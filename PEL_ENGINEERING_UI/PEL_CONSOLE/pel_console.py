from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

APP_NAME = "PEL Engineering Console"
APP_VERSION = "0.1 prototype"

BG = "#0B1020"
PANEL = "#121A2B"
PANEL_2 = "#172138"
TEXT = "#F5F7FB"
MUTED = "#95A2B8"
ACCENT = "#6C8CFF"
GOOD = "#41D3A2"
WARN = "#FFCC66"
BAD = "#FF6B7A"
BORDER = "#26334D"


def natural_key(value: str):
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", value)]


def find_root(explicit: str | None = None) -> Path:
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    here = Path(__file__).resolve().parent
    candidates += [here, here.parent, Path.cwd(), Path(r"C:\PEL_ENGINEERING_UI")]
    for c in candidates:
        if (c / "UNITS").is_dir() and (c / "GROUPS").is_dir():
            return c
        if (c / "PEL_ENGINEERING_UI" / "UNITS").is_dir():
            return c / "PEL_ENGINEERING_UI"
    raise FileNotFoundError("Could not locate the PEL_ENGINEERING_UI installation. Use --root PATH.")


class Repository:
    def __init__(self, root: Path):
        self.root = root
        self.units_dir = root / "UNITS"
        self.groups_dir = root / "GROUPS"
        self.audio_dir = root / "AUDIO_FILES"
        self.firmware_dir = root / "FIRMWARE_IMAGESDean"
        if not self.firmware_dir.exists():
            self.firmware_dir = root / "FIRMWARE_IMAGES"

    def units(self):
        return sorted([p.name for p in self.units_dir.iterdir() if p.is_dir()], key=natural_key)

    def groups(self):
        return sorted([p for p in self.groups_dir.glob("*.grp") if p.is_file()], key=lambda p:natural_key(p.name))

    def assets(self, folder: Path, extensions=None):
        if not folder.exists(): return []
        items=[p for p in folder.rglob("*") if p.is_file()]
        if extensions:
            items=[p for p in items if p.suffix.lower() in extensions]
        return sorted(items, key=lambda p:natural_key(p.name))

    def executables(self):
        candidates = []
        for p in self.root.rglob("*.exe"):
            n=p.name.lower()
            rel=str(p.relative_to(self.root)).lower()
            if "v0.7" in n or "v0.7" in rel or "v0.11" in n or "v0.11" in rel or rel.endswith("main/main/main.exe"):
                candidates.append(p)
        # Prefer clearly versioned binaries; keep main only if no versioned counterpart.
        return sorted(set(candidates), key=lambda p:natural_key(str(p)))

    def statistics(self):
        return {
            "units": len(self.units()),
            "groups": len(self.groups()),
            "audio": len(self.assets(self.audio_dir, {".wav", ".mp3"})),
            "firmware": len(self.assets(self.firmware_dir, {".bin"})),
        }

    def diagnostics(self):
        findings=[]
        # Required per-unit files
        required=["_machine.cfg","_network.cfg","_file_list.cfg"]
        for uid in self.units():
            folder=self.units_dir/uid
            names={p.name for p in folder.iterdir() if p.is_file()}
            for suffix in required:
                if f"{uid}{suffix}" not in names:
                    findings.append(("error", uid, f"Missing {uid}{suffix}"))

        # Known malformed IP token / obvious raw data corruption.
        for p in self.units_dir.glob("*/*_network.cfg"):
            try: data=p.read_bytes()
            except OSError: continue
            if b"0..." in data:
                findings.append(("error", p.parent.name, "Network configuration contains malformed value '0...'"))

        # Hash coverage + verification for audio and firmware.
        for base, label, ext in [(self.audio_dir, "Audio", {".wav", ".mp3"}), (self.firmware_dir, "Firmware", {".bin"})]:
            if not base.exists():
                findings.append(("warning", label, f"Directory not found: {base}"))
                continue
            for asset in self.assets(base, ext):
                hp=Path(str(asset)+"_hash.sha")
                if not hp.exists():
                    findings.append(("warning", label, f"No SHA-256 sidecar for {asset.name}"))
                    continue
                try:
                    raw=hp.read_bytes()
                    digest=hashlib.sha256(asset.read_bytes()).digest()
                    # Existing PEL sidecars are raw 32-byte SHA-256 values; accept hex text too.
                    if len(raw) == 32:
                        valid = (raw == digest)
                    else:
                        text = raw.decode("ascii", errors="ignore").strip().split()[0].lower() if raw.strip() else ""
                        valid = (text == digest.hex())
                    if not valid:
                        findings.append(("error", label, f"Hash mismatch: {asset.name}"))
                except Exception as e:
                    findings.append(("warning", label, f"Could not verify {asset.name}: {e}"))

        # Naming inconsistency that can break hardcoded firmware lookup.
        if (self.root / "FIRMWARE_IMAGESDean").exists() and not (self.root / "FIRMWARE_IMAGES").exists():
            findings.append(("warning", "Firmware", "Folder is named FIRMWARE_IMAGESDean; older code may expect FIRMWARE_IMAGES"))

        # Unicode-escaped filenames worth drawing attention to.
        escaped=[p for p in self.assets(self.audio_dir) if "#U" in p.name and p.suffix.lower()==".wav"]
        if escaped:
            findings.append(("info", "Audio", f"{len(escaped)} audio filenames use #Uxxxx Unicode escaping; configuration names must be normalized consistently"))
        return findings


class Console(tk.Tk):
    def __init__(self, repo: Repository):
        super().__init__()
        self.repo=repo
        self.title(f"{APP_NAME} — {repo.root}")
        self.geometry("1440x900")
        self.minsize(1120, 700)
        self.configure(bg=BG)
        self.option_add("*Font", "Segoe UI 10")
        self._style()
        self.nav={}
        self.page=None
        self._shell()
        self.show_dashboard()

    def _style(self):
        s=ttk.Style(self)
        try: s.theme_use("clam")
        except tk.TclError: pass
        s.configure("Treeview", background=PANEL, foreground=TEXT, fieldbackground=PANEL, borderwidth=0, rowheight=31)
        s.configure("Treeview.Heading", background=PANEL_2, foreground=MUTED, relief="flat", font=("Segoe UI Semibold",10))
        s.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "white")])
        s.configure("Vertical.TScrollbar", background=PANEL_2, troughcolor=BG, bordercolor=BG, arrowcolor=MUTED)

    def _shell(self):
        top=tk.Frame(self,bg=BG,height=78); top.pack(fill="x"); top.pack_propagate(False)
        tk.Label(top,text="PEL",bg=BG,fg=TEXT,font=("Segoe UI Semibold",24)).pack(side="left",padx=(28,8),pady=20)
        tk.Label(top,text="ENGINEERING CONSOLE",bg=BG,fg=MUTED,font=("Segoe UI",10)).pack(side="left",pady=(30,20))
        tk.Label(top,text=f"●  {self.repo.root}",bg=PANEL,fg=GOOD,font=("Segoe UI",9),padx=14,pady=8).pack(side="right",padx=28)

        body=tk.Frame(self,bg=BG); body.pack(fill="both",expand=True)
        self.sidebar=tk.Frame(body,bg="#0D1424",width=224); self.sidebar.pack(side="left",fill="y"); self.sidebar.pack_propagate(False)
        self.content=tk.Frame(body,bg=BG); self.content.pack(side="left",fill="both",expand=True)
        navs=[("Overview",self.show_dashboard),("Units",self.show_units),("Groups",self.show_groups),("Audio",lambda:self.show_assets("Audio")),("Firmware",lambda:self.show_assets("Firmware")),("Diagnostics",self.show_diagnostics),("Versions",self.show_versions)]
        tk.Label(self.sidebar,text="WORKSPACE",bg="#0D1424",fg=MUTED,font=("Segoe UI Semibold",9)).pack(anchor="w",padx=24,pady=(28,10))
        for name,cmd in navs:
            b=tk.Button(self.sidebar,text=name,command=lambda n=name,c=cmd:self._navigate(n,c),anchor="w",relief="flat",bd=0,bg="#0D1424",fg=MUTED,activebackground=PANEL_2,activeforeground=TEXT,font=("Segoe UI Semibold",11),padx=24,pady=12,cursor="hand2")
            b.pack(fill="x",padx=10,pady=2); self.nav[name]=b
        tk.Label(self.sidebar,text=f"{APP_VERSION}",bg="#0D1424",fg="#5C6880",font=("Segoe UI",8)).pack(side="bottom",anchor="w",padx=24,pady=20)

    def _navigate(self,name,cmd):
        for n,b in self.nav.items(): b.configure(bg="#0D1424",fg=MUTED)
        self.nav[name].configure(bg=PANEL_2,fg=TEXT)
        cmd()

    def _clear(self):
        for w in self.content.winfo_children(): w.destroy()

    def _header(self,title,subtitle=""):
        box=tk.Frame(self.content,bg=BG); box.pack(fill="x",padx=32,pady=(24,18))
        tk.Label(box,text=title,bg=BG,fg=TEXT,font=("Segoe UI Semibold",25)).pack(anchor="w")
        if subtitle: tk.Label(box,text=subtitle,bg=BG,fg=MUTED,font=("Segoe UI",10)).pack(anchor="w",pady=(5,0))
        return box

    def _card(self,parent,title,value,caption):
        c=tk.Frame(parent,bg=PANEL,highlightbackground=BORDER,highlightthickness=1)
        tk.Label(c,text=title.upper(),bg=PANEL,fg=MUTED,font=("Segoe UI Semibold",9)).pack(anchor="w",padx=20,pady=(18,5))
        tk.Label(c,text=str(value),bg=PANEL,fg=TEXT,font=("Segoe UI Semibold",29)).pack(anchor="w",padx=20)
        tk.Label(c,text=caption,bg=PANEL,fg=MUTED,font=("Segoe UI",9)).pack(anchor="w",padx=20,pady=(4,18))
        return c

    def _button(self,parent,text,command,primary=False):
        return tk.Button(parent,text=text,command=command,bg=ACCENT if primary else PANEL_2,fg="white" if primary else TEXT,activebackground="#7896FF" if primary else "#22304C",activeforeground="white",relief="flat",bd=0,font=("Segoe UI Semibold",10),padx=16,pady=10,cursor="hand2")

    def show_dashboard(self):
        self._clear(); self._navigate_state("Overview")
        self._header("Good morning, engineer.","Everything you need to inspect and launch the PEL system, in one calm workspace.")
        stats=self.repo.statistics(); row=tk.Frame(self.content,bg=BG); row.pack(fill="x",padx=32)
        cards=[("Units",stats['units'],"device workspaces"),("Groups",stats['groups'],"deployment groups"),("Audio",stats['audio'],"playable assets"),("Firmware",stats['firmware'],"binary images")]
        for i,x in enumerate(cards):
            c=self._card(row,*x); c.grid(row=0,column=i,sticky="nsew",padx=(0 if i==0 else 6,0 if i==3 else 6)); row.grid_columnconfigure(i,weight=1)
        lower=tk.Frame(self.content,bg=BG); lower.pack(fill="both",expand=True,padx=32,pady=22)
        left=tk.Frame(lower,bg=PANEL,highlightbackground=BORDER,highlightthickness=1); left.pack(side="left",fill="both",expand=True,padx=(0,8))
        right=tk.Frame(lower,bg=PANEL,highlightbackground=BORDER,highlightthickness=1,width=360); right.pack(side="left",fill="y",padx=(8,0)); right.pack_propagate(False)
        tk.Label(left,text="Quick launch",bg=PANEL,fg=TEXT,font=("Segoe UI Semibold",15)).pack(anchor="w",padx=22,pady=(22,4))
        tk.Label(left,text="Choose the application generation required for this job.",bg=PANEL,fg=MUTED).pack(anchor="w",padx=22,pady=(0,18))
        versions=self.repo.executables()
        for p in versions:
            r=tk.Frame(left,bg=PANEL_2); r.pack(fill="x",padx=22,pady=6)
            name=self._version_name(p)
            tk.Label(r,text=name,bg=PANEL_2,fg=TEXT,font=("Segoe UI Semibold",12)).pack(side="left",padx=16,pady=15)
            self._button(r,"Launch",lambda p=p:self.launch(p),True).pack(side="right",padx=10,pady=8)
        tk.Label(right,text="System health",bg=PANEL,fg=TEXT,font=("Segoe UI Semibold",15)).pack(anchor="w",padx=22,pady=(22,4))
        findings=self.repo.diagnostics(); errors=sum(1 for x in findings if x[0]=="error"); warnings=sum(1 for x in findings if x[0]=="warning")
        status="Needs attention" if errors else ("Review recommended" if warnings else "All checks passed")
        fg=BAD if errors else WARN if warnings else GOOD
        tk.Label(right,text=status,bg=PANEL,fg=fg,font=("Segoe UI Semibold",20)).pack(anchor="w",padx=22,pady=(14,2))
        tk.Label(right,text=f"{errors} errors  •  {warnings} warnings",bg=PANEL,fg=MUTED).pack(anchor="w",padx=22)
        self._button(right,"Open diagnostics",lambda:self._navigate("Diagnostics",self.show_diagnostics)).pack(anchor="w",padx=22,pady=22)

    def _navigate_state(self,name):
        for n,b in self.nav.items(): b.configure(bg=PANEL_2 if n==name else "#0D1424",fg=TEXT if n==name else MUTED)

    def show_units(self):
        self._clear(); self._navigate_state("Units")
        head=self._header("Units","Search and inspect every unit workspace without digging through folders.")
        controls=tk.Frame(self.content,bg=BG); controls.pack(fill="x",padx=32,pady=(0,12))
        q=tk.StringVar(); e=tk.Entry(controls,textvariable=q,bg=PANEL,fg=TEXT,insertbackground=TEXT,relief="flat",font=("Segoe UI",11)); e.pack(side="left",fill="x",expand=True,ipady=10)
        self._button(controls,"Open UNITS folder",lambda:self.open_path(self.repo.units_dir)).pack(side="left",padx=(12,0))
        wrap=tk.Frame(self.content,bg=PANEL,highlightbackground=BORDER,highlightthickness=1); wrap.pack(fill="both",expand=True,padx=32,pady=(0,28))
        tree=ttk.Treeview(wrap,columns=("id","files","status"),show="headings"); tree.heading("id",text="UNIT ID"); tree.heading("files",text="FILES"); tree.heading("status",text="CONFIGURATION"); tree.column("id",width=260); tree.column("files",width=100,anchor="center"); tree.column("status",width=220)
        sb=ttk.Scrollbar(wrap,orient="vertical",command=tree.yview); tree.configure(yscrollcommand=sb.set); sb.pack(side="right",fill="y"); tree.pack(fill="both",expand=True,padx=1,pady=1)
        units=self.repo.units()
        def fill(*_):
            term=q.get().strip().lower(); tree.delete(*tree.get_children())
            for uid in units:
                if term and term not in uid.lower(): continue
                folder=self.repo.units_dir/uid; count=sum(1 for p in folder.iterdir() if p.is_file())
                required=all((folder/f"{uid}{s}").exists() for s in ["_machine.cfg","_network.cfg","_file_list.cfg"])
                tree.insert("", "end", values=(uid,count,"Ready" if required else "Missing required file"))
        q.trace_add("write",fill); fill()
        def open_sel(_=None):
            sel=tree.selection()
            if sel: self.open_path(self.repo.units_dir/tree.item(sel[0],"values")[0])
        tree.bind("<Double-1>",open_sel)

    def show_groups(self):
        self._clear(); self._navigate_state("Groups"); self._header("Groups","Deployment and site group definitions.")
        wrap=tk.Frame(self.content,bg=PANEL,highlightbackground=BORDER,highlightthickness=1); wrap.pack(fill="both",expand=True,padx=32,pady=(0,28))
        for p in self.repo.groups():
            r=tk.Frame(wrap,bg=PANEL_2); r.pack(fill="x",padx=14,pady=5)
            tk.Label(r,text=p.stem,bg=PANEL_2,fg=TEXT,font=("Segoe UI Semibold",11)).pack(side="left",padx=14,pady=13)
            tk.Label(r,text=f"{p.stat().st_size:,} bytes",bg=PANEL_2,fg=MUTED).pack(side="right",padx=14)

    def show_assets(self,kind):
        self._clear(); self._navigate_state(kind)
        base=self.repo.audio_dir if kind=="Audio" else self.repo.firmware_dir
        exts={".wav",".mp3"} if kind=="Audio" else {".bin"}
        items=self.repo.assets(base,exts)
        self._header(kind,f"{len(items)} assets available in {base.name}.")
        controls=tk.Frame(self.content,bg=BG); controls.pack(fill="x",padx=32,pady=(0,12)); self._button(controls,f"Open {kind} folder",lambda:self.open_path(base)).pack(side="right")
        wrap=tk.Frame(self.content,bg=PANEL,highlightbackground=BORDER,highlightthickness=1); wrap.pack(fill="both",expand=True,padx=32,pady=(0,28))
        tree=ttk.Treeview(wrap,columns=("name","location","hash"),show="headings"); tree.heading("name",text="FILE"); tree.heading("location",text="LOCATION"); tree.heading("hash",text="SHA-256"); tree.column("name",width=450); tree.column("location",width=300); tree.column("hash",width=130,anchor="center")
        tree.pack(fill="both",expand=True)
        for p in items:
            hp=Path(str(p)+"_hash.sha")
            tree.insert("","end",values=(p.name,str(p.parent.relative_to(base)),"Present" if hp.exists() else "Missing"))

    def show_diagnostics(self):
        self._clear(); self._navigate_state("Diagnostics"); self._header("Diagnostics","Read-only checks. Nothing here modifies a unit or deployment file.")
        findings=self.repo.diagnostics(); bar=tk.Frame(self.content,bg=BG); bar.pack(fill="x",padx=32,pady=(0,14)); self._button(bar,"Run again",self.show_diagnostics,True).pack(side="right")
        wrap=tk.Frame(self.content,bg=PANEL,highlightbackground=BORDER,highlightthickness=1); wrap.pack(fill="both",expand=True,padx=32,pady=(0,28))
        if not findings:
            tk.Label(wrap,text="✓  All checks passed",bg=PANEL,fg=GOOD,font=("Segoe UI Semibold",18)).pack(pady=50)
            return
        for sev,scope,msg in findings:
            r=tk.Frame(wrap,bg=PANEL_2); r.pack(fill="x",padx=12,pady=5)
            fg={"error":BAD,"warning":WARN,"info":ACCENT}.get(sev,MUTED)
            tk.Label(r,text=sev.upper(),bg=PANEL_2,fg=fg,font=("Segoe UI Semibold",9),width=10,anchor="w").pack(side="left",padx=(14,4),pady=13)
            tk.Label(r,text=scope,bg=PANEL_2,fg=TEXT,font=("Segoe UI Semibold",10),width=17,anchor="w").pack(side="left")
            tk.Label(r,text=msg,bg=PANEL_2,fg=MUTED,font=("Segoe UI",10),anchor="w").pack(side="left",fill="x",expand=True,padx=10)

    def show_versions(self):
        self._clear(); self._navigate_state("Versions"); self._header("Application versions","v0.7 and v0.11 are both first-class supported tools.")
        for p in self.repo.executables():
            card=tk.Frame(self.content,bg=PANEL,highlightbackground=BORDER,highlightthickness=1); card.pack(fill="x",padx=32,pady=7)
            tk.Label(card,text=self._version_name(p),bg=PANEL,fg=TEXT,font=("Segoe UI Semibold",16)).pack(anchor="w",padx=20,pady=(18,4))
            tk.Label(card,text=str(p.relative_to(self.repo.root)),bg=PANEL,fg=MUTED,font=("Consolas",9)).pack(anchor="w",padx=20)
            actions=tk.Frame(card,bg=PANEL); actions.pack(fill="x",padx=20,pady=16)
            self._button(actions,"Launch",lambda p=p:self.launch(p),True).pack(side="left")
            self._button(actions,"Open location",lambda p=p:self.open_path(p.parent)).pack(side="left",padx=8)

    def _version_name(self,p:Path):
        s=str(p).lower()
        if "v0.11" in s: return "PEL Engineering UI  •  v0.11"
        if "v0.7" in s or p.name.lower()=="main.exe": return "PEL Engineering UI  •  v0.7"
        return p.stem

    def launch(self,p:Path):
        if os.name != "nt":
            messagebox.showinfo("Windows required",f"This binary is a Windows executable:\n\n{p}")
            return
        try: subprocess.Popen([str(p)],cwd=str(p.parent))
        except Exception as e: messagebox.showerror("Launch failed",str(e))

    def open_path(self,p:Path):
        try:
            if os.name=="nt": os.startfile(str(p))
            elif sys.platform=="darwin": subprocess.Popen(["open",str(p)])
            else: subprocess.Popen(["xdg-open",str(p)])
        except Exception as e: messagebox.showerror("Could not open",str(e))


def cli_diagnostics(repo: Repository):
    stats=repo.statistics(); findings=repo.diagnostics()
    print(json.dumps({"root":str(repo.root),"statistics":stats,"findings":[{"severity":a,"scope":b,"message":c} for a,b,c in findings]},indent=2))
    return 1 if any(x[0]=="error" for x in findings) else 0


def main():
    ap=argparse.ArgumentParser(description=APP_NAME)
    ap.add_argument("--root",help="Path to PEL_ENGINEERING_UI")
    ap.add_argument("--diagnostics",action="store_true",help="Run headless diagnostics and print JSON")
    args=ap.parse_args()
    try: repo=Repository(find_root(args.root))
    except Exception as e:
        print(e,file=sys.stderr); return 2
    if args.diagnostics: return cli_diagnostics(repo)
    Console(repo).mainloop(); return 0

if __name__=="__main__":
    raise SystemExit(main())
