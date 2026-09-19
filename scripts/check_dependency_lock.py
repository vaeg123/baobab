"""Ensure Vercel's uv resolution uses exactly the audited production versions."""
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import tomllib

root = Path(__file__).resolve().parents[1]

def packages(text):
    return set(re.findall(r"^([A-Za-z0-9_.-]+)==([^\s;]+)", text, re.MULTILINE))

expected = packages((root / "requirements.txt").read_text())
config = tomllib.loads((root / "pyproject.toml").read_text())
constraints = packages("\n".join(config["tool"]["uv"]["constraint-dependencies"]))
if expected != constraints:
    sys.exit("The audited requirements and Vercel constraints differ.")
with tempfile.TemporaryDirectory() as directory:
    target = Path(directory) / "production.txt"
    result = subprocess.run([sys.executable, "-m", "uv", "export", "--locked", "--no-dev",
                             "--no-emit-project", "--format", "requirements-txt", "--output-file", str(target)],
                            cwd=root, capture_output=True, text=True)
    if result.returncode:
        sys.exit("uv.lock is missing, stale or could not be exported: " + result.stderr)
    actual = packages(target.read_text())
    if actual != expected:
        sys.exit("Vercel production versions differ: " + json.dumps(sorted(actual ^ expected)))
print(f"Vercel uv.lock matches all {len(expected)} audited production package versions.")
