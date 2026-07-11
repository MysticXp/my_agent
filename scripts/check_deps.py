"""Validate ALL requirements can be installed.
Runs pip install --dry-run on each package individually
and reports ALL failures at once."""
import re, subprocess, sys, os
os.environ["PYTHONIOENCODING"] = "utf-8"

with open("requirements_full.txt", encoding="utf-8-sig") as f:
    lines = f.readlines()

pkgs = []
for line in lines:
    s = line.strip()
    if not s or s.startswith("#"):
        continue
    pkgs.append(s)

print(f"Checking {len(pkgs)} packages...")
failed = []
ok = 0
for i, pkg in enumerate(pkgs, 1):
    label = pkg[:55]
    print(f"  [{i:3d}/{len(pkgs)}] {label:55s}  ", end="", flush=True)
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", pkg, "--dry-run", "--quiet"],
        capture_output=True, text=True, timeout=60,
    )
    if r.returncode == 0:
        ok += 1
        print("OK")
    else:
        failed.append(pkg)
        print("FAIL")

print()
print(f"=== RESULTS: {ok} OK, {len(failed)} FAILED ===")
for pkg in failed:
    print(f"  FAIL: {pkg}")
sys.exit(1 if failed else 0)
