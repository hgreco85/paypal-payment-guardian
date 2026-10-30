#!/usr/bin/env python3
"""Copy this directory to a clean folder laid out as the standalone public repo.
Does NOT publish, push or create any remote. Usage: export_public_repo.py <dest>"""
import pathlib, shutil, subprocess, sys

src = pathlib.Path(__file__).resolve().parents[1]
dest = pathlib.Path(sys.argv[1]).resolve()
if dest.exists() and any(dest.iterdir()):
    sys.exit(f"refusing: {dest} not empty")
shutil.copytree(src, dest, dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__", "out", "*.pyc", "internal", "*.jsonl"))
r = subprocess.run([sys.executable, str(dest / "scripts" / "sanitize_check.py"), str(dest)])
sys.exit(r.returncode)
