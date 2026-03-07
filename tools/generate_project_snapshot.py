#!/usr/bin/env python3
"""
generate_project_snapshot.py
- Repo ve sistem bilgisini toplar
- docs/AI_BRIEF.md içindeki AUTOGEN bloğunu günceller
- docs/_generated/project_snapshot.{json,md} üretir
"""
from __future__ import annotations
import argparse, json, os, platform, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

AUTOGEN_START = "<!-- AUTOGEN:START"
AUTOGEN_END   = "<!-- AUTOGEN:END -->"

def run_cmd(cmd: List[str], cwd: Optional[Path]=None, timeout: int=8) -> Tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True, timeout=timeout, shell=False)
        out = (p.stdout or "") + (p.stderr or "")
        return p.returncode, out.strip()
    except Exception as e:
        return 999, f"{type(e).__name__}: {e}"

def detect_git(root: Path) -> bool:
    return (root / ".git").exists()

def git_head(root: Path) -> Dict[str, str]:
    info = {}
    rc, out = run_cmd(["git","rev-parse","--short","HEAD"], cwd=root)
    if rc == 0: info["commit"] = out
    rc, out = run_cmd(["git","status","--porcelain"], cwd=root)
    if rc == 0: info["dirty"] = "yes" if out else "no"
    rc, out = run_cmd(["git","rev-parse","--abbrev-ref","HEAD"], cwd=root)
    if rc == 0: info["branch"] = out
    return info

def file_tree(root: Path, max_lines: int=200) -> List[str]:
    lines: List[str] = []
    def walk(p: Path, prefix: str="", depth: int=0, max_depth: int=4):
        nonlocal lines
        if depth > max_depth or len(lines) >= max_lines:
            return
        try:
            entries = sorted(list(p.iterdir()), key=lambda x: (x.is_file(), x.name.lower()))
        except Exception:
            return
        for i,e in enumerate(entries):
            if e.name in {".git","venv",".venv","__pycache__","node_modules","reservation_pdfs","logs"}:
                continue
            connector = "└── " if i == len(entries)-1 else "├── "
            lines.append(f"{prefix}{connector}{e.name}")
            if e.is_dir():
                new_prefix = prefix + ("    " if i == len(entries)-1 else "│   ")
                walk(e, new_prefix, depth+1, max_depth)
            if len(lines) >= max_lines:
                break
    lines.append(str(root))
    walk(root)
    if len(lines) >= max_lines:
        lines.append("… (kısaltıldı)")
    return lines

def env_presence(keys: List[str]) -> Dict[str, str]:
    return {k: ("SET" if os.getenv(k) else "NOT SET") for k in keys}

def tool_versions(root: Path) -> Dict[str, str]:
    versions={}
    versions["python_exe"] = sys.executable
    versions["python_version"] = sys.version.split()[0]
    for name, cmd in [
        ("node", ["node","-v"]),
        ("npm", ["npm","-v"]),
        ("cloudflared", ["cloudflared","--version"]),
        ("git", ["git","--version"]),
    ]:
        rc,out = run_cmd(cmd, cwd=root)
        versions[name] = out if rc==0 else f"NOT FOUND ({out})"
    return versions

def update_autogen_block(ai_brief_path: Path, new_block_md: str) -> None:
    txt = ai_brief_path.read_text(encoding="utf-8")
    start_idx = txt.find(AUTOGEN_START)
    end_idx = txt.find(AUTOGEN_END)
    if start_idx == -1 or end_idx == -1 or end_idx < start_idx:
        raise RuntimeError("AUTOGEN blok marker'lari bulunamadi (AI_BRIEF.md).")
    start_line_end = txt.find("\n", start_idx)
    if start_line_end == -1:
        start_line_end = start_idx
    end_marker_end = end_idx + len(AUTOGEN_END)
    updated = txt[:start_line_end+1] + new_block_md.rstrip() + "\n" + txt[end_marker_end:]
    ai_brief_path.write_text(updated, encoding="utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    args = ap.parse_args()
    root = Path(args.root).resolve()
    docs = root / "docs"
    ai_brief = docs / "AI_BRIEF.md"
    gen_dir = docs / "_generated"
    gen_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    snapshot: Dict[str, Any] = {
        "timestamp": now,
        "root": str(root),
        "system": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": {"exe": sys.executable, "version": sys.version},
        },
        "tools": tool_versions(root),
        "env_presence": env_presence([
            "OPENAI_API_KEY","OPENAI_MODEL",
            "WHATSAPP_TOKEN","WHATSAPP_PHONE_ID",
            "Elektra_Booking","ELEKTRA_HOTEL_ID","ELEKTRA_API_BASE_URL",
            "WEBHOOK_URL"
        ]),
        "git": git_head(root) if detect_git(root) else {"enabled":"no"},
        "tree": file_tree(root, max_lines=220),
    }

    (gen_dir / "project_snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    md = []
    md.append("## Anlık Sistem & Repo Özeti (AUTOGEN)\\n\\n")
    md.append(f"- Güncelleme zamanı: `{snapshot['timestamp']}`\\n")
    md.append(f"- Repo: `{snapshot['root']}`\\n")
    if snapshot["git"].get("enabled") == "no":
        md.append("- Git: **yok / algılanmadı**\\n")
    else:
        md.append(f"- Git: branch `{snapshot['git'].get('branch','?')}`, commit `{snapshot['git'].get('commit','?')}`, dirty `{snapshot['git'].get('dirty','?')}`\\n")
    md.append("\\n### Tool Versiyonları\\n")
    for k,v in snapshot["tools"].items():
        md.append(f"- `{k}`: {v}\\n")
    md.append("\\n### ENV (sadece SET/NOT SET)\\n")
    for k,v in snapshot["env_presence"].items():
        md.append(f"- `{k}`: {v}\\n")
    md.append("\\n### Kısa Dizin Ağacı (kısaltılmış)\\n")
    md.append("```text\\n" + "\\n".join(snapshot["tree"]) + "\\n```\\n")
    md_text = "".join(md)
    (gen_dir / "project_snapshot.md").write_text(md_text, encoding="utf-8")

    if ai_brief.exists():
        update_autogen_block(ai_brief, md_text)
        print("OK: AI_BRIEF.md AUTOGEN güncellendi.")
    else:
        print("UYARI: docs/AI_BRIEF.md bulunamadi, sadece _generated üretildi.")
    print("OK: docs/_generated/project_snapshot.{json,md} üretildi.")

if __name__ == "__main__":
    main()
