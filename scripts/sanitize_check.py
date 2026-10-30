#!/usr/bin/env python3
"""Pre-publication sanitiser: fails if the tree contains likely secrets or
internal-only references. Run before copying to the public repo."""
import pathlib, re, sys

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
PATTERNS = {
    "paypal-live-or-long-secret": re.compile(r"(?i)(client[_-]?secret|secret)\s*[:=]\s*['\"]?(?![A-Z_]+['\"]?\s*$)(?![A-Z_]+['\"]?\s*\n)[A-Za-z0-9_\-]{24,}"),
    "bearer-token": re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{30,}"),
    "bws/bitwarden-token": re.compile(r"\b0\.[0-9a-f\-]{36}\.[A-Za-z0-9+/=:]{20,}"),
    "github-token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "private-key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "internal-ref": re.compile(r"(?i)PAID_RUN_FREEZE|hgreco85|HG-Market-System|C:\\\\Users\\\\|/home/box"),
    "live-paypal-host": re.compile(r"api-m\.paypal\.com|api\.paypal\.com"),
}
ALLOW_LIVE_HOST_IN = {"tests/test_client_policy.py", "src/payment_guardian/paypal_client.py", "scripts/sanitize_check.py"}
bad = []
for p in ROOT.rglob("*"):
    if not p.is_file() or any(x in p.parts for x in (".git", "__pycache__", "out")) or p.suffix in {".png", ".jpg", ".mp4"}:
        continue
    rel = p.relative_to(ROOT).as_posix()
    if rel == "scripts/sanitize_check.py":
        continue
    text = p.read_text(errors="ignore")
    for name, rx in PATTERNS.items():
        if name == "live-paypal-host" and rel in ALLOW_LIVE_HOST_IN:
            continue
        for m in rx.finditer(text):
            bad.append(f"{rel}: {name}")
            break
if bad:
    print("SANITIZE FAIL:\n  " + "\n  ".join(bad)); sys.exit(1)
print(f"SANITIZE OK ({ROOT})")
