import json, os, re, sys, subprocess, tempfile, shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp-server"))

PASS, FAIL = 0, 0

def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} -- {detail}")

import httpx

print("=" * 60)
print("GROUP 1: Configuration Integrity")
print("=" * 60)
from bug_core import load_config, get_instance_config
config = load_config()
instances = config["instances"]
test("5 instances configured", len(instances) == 5)
for name in ["kernel", "mozilla", "gnome", "unisoc", "local"]:
    test(f"  Instance '{name}' exists", name in instances)
test("unisoc has api_key", len(instances["unisoc"]["api_key"]) == 40)
test("unisoc has ftp_host", instances["unisoc"]["ftp_host"] == "unitrans.unisoc.com")
test("unisoc has ftp_user/password", bool(instances["unisoc"]["ftp_user"]))
test("default_instance is kernel", config.get("default_instance") == "kernel")
test("get_instance_config default returns kernel", get_instance_config()[1]["name"] == "Linux Kernel Bugzilla")
test("get_instance_config('unisoc') correct", get_instance_config("unisoc")[1]["ftp_host"] == "unitrans.unisoc.com")

print()
print("=" * 60)
print("GROUP 2: REST API — All 5 Instances")
print("=" * 60)
from bug_core import fetch_bug_rest, fetch_bug_offline

def safe_fetch(bug_id, instance):
    try:
        return fetch_bug_rest(bug_id, instance=instance)
    except Exception as e:
        return {"error": str(e)}

# kernel
bug = safe_fetch("1", "kernel")
test("kernel bug/1 returns 200", bug and "error" not in bug, str(bug.get("error","")))
if bug and "error" not in bug:
    test("kernel bug has summary", bool(bug.get("summary")))

# mozilla
bug = safe_fetch("35", "mozilla")
test("mozilla bug/35 returns 200", bug and "error" not in bug, str(bug.get("error","")))
if bug and "error" not in bug:
    test("mozilla bug has summary", bool(bug.get("summary")))

# gnome (may have access restrictions)
bug = safe_fetch("1", "gnome")
test("gnome bug/1 has response", bug is not None)
if bug and "error" not in bug:
    test("gnome bug has summary", bool(bug.get("summary")))
elif bug:
    test("gnome 403 (expected)", "403" in bug.get("error","") or "Forbidden" in bug.get("error",""),
         bug.get("error","")[:80])

# unisoc
bug = safe_fetch("219041", "unisoc")
test("unisoc bug/219041 returns 200", bug and "error" not in bug, str(bug.get("error","")))
if bug and "error" not in bug:
    test("unisoc bug has summary", bool(bug.get("summary")))
    test("unisoc bug has ftp_urls", len(bug.get("ftp_urls",[])) > 0)
    test("unisoc bug has comments", bug.get("comments_count", 0) > 0)

# local
bug = fetch_bug_offline("BUG-20261")
test("local BUG-20261 offline", bug and "error" not in bug, str(bug.get("error","")))
if bug and "error" not in bug:
    test("local bug has summary", bool(bug.get("summary")))

print()
print("=" * 60)
print("GROUP 3: MCP Server API Key Fix Verification")
print("=" * 60)
from server import _get_api_key_for_url, _load_config, CONFIG_PATH

test("CONFIG_PATH exists", os.path.exists(CONFIG_PATH))
test("_load_config returns non-empty", len(_load_config()) > 0)
test("unisoc URL resolves API key", len(_get_api_key_for_url("https://bugzilla.unisoc.com/bugzilla")) == 40)
test("kernel URL returns empty key", _get_api_key_for_url("https://bugzilla.kernel.org") == "")
test("mozilla URL returns empty key", _get_api_key_for_url("https://bugzilla.mozilla.org") == "")
test("gnome URL returns empty key", _get_api_key_for_url("https://bugzilla.gnome.org") == "")
test("unknown URL returns empty key", _get_api_key_for_url("https://unknown.example.com") == "")

print()
print("=" * 60)
print("GROUP 4: MCP-Style Direct API Calls (Simulating MCP Tools)")
print("=" * 60)

def mcp_bug_info(bug_id, base_url):
    key = _get_api_key_for_url(base_url)
    params = {"include_fields": "_all"}
    if key:
        params["api_key"] = key
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if key:
        headers["api_key"] = key
    try:
        resp = httpx.get(f"{base_url}/rest/bug/{bug_id}", params=params, headers=headers, timeout=15)
        return resp.status_code, resp.json() if resp.status_code == 200 else resp.text[:200]
    except Exception as e:
        return 0, str(e)

# kernel
code, data = mcp_bug_info("1", "https://bugzilla.kernel.org")
test("MCP kernel bug/1 status=200", code == 200, f"got {code}")
test("MCP kernel returns bugs array", code == 200 and len(data.get("bugs",[])) > 0)

# mozilla
code, data = mcp_bug_info("35", "https://bugzilla.mozilla.org")
test("MCP mozilla bug/35 status=200", code == 200, f"got {code}")

# gnome (blocks API access, 403 expected)
code, data = mcp_bug_info("1", "https://bugzilla.gnome.org")
test("MCP gnome bug/1 has response", code in (200, 403), f"got {code}")
if code == 403:
    print(f"      (gnome blocks API access with 403 - expected)")

# unisoc
code, data = mcp_bug_info("219041", "https://bugzilla.unisoc.com/bugzilla")
test("MCP unisoc bug/219041 status=200", code == 200, f"got {code}")
test("MCP unisoc returns summary", code == 200 and bool(data.get("bugs",[{}])[0].get("summary")))

# unisoc comments
key = _get_api_key_for_url("https://bugzilla.unisoc.com/bugzilla")
params = {"api_key": key}
headers = {"Accept": "application/json", "Content-Type": "application/json", "api_key": key}
resp = httpx.get("https://bugzilla.unisoc.com/bugzilla/rest/bug/219041/comment", params=params, headers=headers, timeout=15)
test("MCP unisoc comments status=200", resp.status_code == 200)
if resp.status_code == 200:
    all_text = " ".join(c.get("text","") for bc in resp.json().get("bugs",{}).values() for c in bc.get("comments",[]))
    ftps = list(set(re.findall(r'ftp://[^\s)\]]+', all_text)))
    uncs = list(set(re.findall(r'\\\\[a-zA-Z0-9_.-]+\\(?:[^\s)\]]+\\)*[^\s)\]]+', all_text)))
    test("MCP FTP URLs extracted", len(ftps) > 0, f"found {len(ftps)}")
    print(f"      FTP URLs: {ftps}")
    print(f"      UNC paths: {uncs}")

print()
print("=" * 60)
print("GROUP 6: CLI End-to-End")
print("=" * 60)
CLI = os.path.join(os.path.dirname(__file__), "..", "bug_core.py")
PY = r"C:\Program Files\Python310\python.exe"

def run_cli(*args):
    """Run CLI with proper encoding handling for Windows GBK"""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    r = subprocess.run([PY, CLI] + list(args), capture_output=True, text=True,
                       timeout=30, encoding="utf-8", errors="replace", env=env)
    return r

# CLI --help (no args -> shows help)
r = run_cli()
test("CLI --help exit code non-zero (no args)", r.returncode != 0, f"rc={r.returncode}")
test("CLI --help contains instance", "instance" in (r.stdout or "").lower())
test("CLI --help contains json", "json" in (r.stdout or "").lower())
test("CLI --help NO workspace flag", "workspace" not in (r.stdout or "").lower(),
     "workspace flag should not appear in bug-core CLI")

# CLI kernel (positional: bug_id instance)
r = run_cli("1", "kernel")
test("CLI kernel bug 1 exit code 0", r.returncode == 0, f"stderr: {r.stderr[:200]}")
test("CLI kernel bug 1 contains summary", "ide-cd" in r.stdout or "oops" in r.stdout.lower())

# CLI mozilla
r = run_cli("35", "mozilla")
test("CLI mozilla bug 35 exit code 0", r.returncode == 0, f"stderr: {r.stderr[:200]}")
test("CLI mozilla bug 35 contains Navigator", "Navigator" in r.stdout or "preference" in r.stdout.lower())

# CLI gnome (may fail with 403)
r = run_cli("1", "gnome")
test("CLI gnome bug 1 has response", r.returncode in (0, 1), f"rc={r.returncode}")

# CLI unisoc
r = run_cli("219041", "unisoc")
test("CLI unisoc bug 219041 exit code 0", r.returncode == 0, f"stderr: {r.stderr[:200]}")
test("CLI unisoc contains FTP Path", "ftp://" in r.stdout.lower())

# CLI --json
r = run_cli("219041", "unisoc", "--json")
test("CLI --json exit code 0", r.returncode == 0, f"stderr: {r.stderr[:200]}")
# JSON output is after the "[Query] ..." prefix line
json_start = r.stdout.find("{")
if json_start >= 0:
    try:
        j = json.loads(r.stdout[json_start:])
        test("CLI --json is valid JSON", True)
        test("CLI --json contains bug_id", "bug_id" in j)
        test("CLI --json contains ftp_urls", "ftp_urls" in j)
    except json.JSONDecodeError:
        test("CLI --json is valid JSON", False, r.stdout[json_start:json_start+200])
else:
    test("CLI --json is valid JSON", False, "no JSON found in output")

# CLI --offline
r = run_cli("BUG-20261", "local", "--offline")
test("CLI --offline local BUG-20261 exit code 0", r.returncode == 0, f"stderr: {r.stderr[:200]}")
test("CLI offline contains PD charge", "PD" in r.stdout or "20261" in r.stdout)

# CLI --list
r = run_cli("--list")
test("CLI --list exit code 0", r.returncode == 0, f"stderr: {r.stderr[:200]}")
test("CLI --list contains BUG-20261", "BUG-20261" in r.stdout)

print()
print("=" * 60)
print("GROUP 7: Error Handling")
print("=" * 60)

# No API key accessing unisoc
try:
    resp = httpx.get("https://bugzilla.unisoc.com/bugzilla/rest/bug/219041",
                     headers={"Accept": "application/json"}, timeout=15)
    test("No API key accessing unisoc returns 401", resp.status_code == 401, f"got {resp.status_code}")
except Exception as e:
    test("No API key accessing unisoc connection failed", "401" in str(e) or "Connection" in str(e),
         str(e)[:100])

# Wrong API key
resp = httpx.get("https://bugzilla.unisoc.com/bugzilla/rest/bug/219041",
                 params={"api_key": "invalid_key_xxx"},
                 headers={"Accept": "application/json"},
                 timeout=15)
test("Wrong API key returns 401 or 400", resp.status_code in (401, 400), f"got {resp.status_code}")

# 404 - non-existent bug
code, data = mcp_bug_info("99999999", "https://bugzilla.kernel.org")
test("kernel non-existent bug returns 404", code == 404, f"got {code}")

# Offline mode query non-existent bug
bug = fetch_bug_offline("NONEXISTENT")
test("Offline mode non-existent bug returns error", "error" in bug)

# CLI invalid instance (the CLI catches ValueError and prints [ERROR])
r = run_cli("1", "nonexistent_xyz")
test("CLI invalid instance contains ERROR", "ERROR" in (r.stdout or "").upper() or "ERROR" in (r.stderr or "").upper(),
     f"stdout: {r.stdout[:100] if r.stdout else 'None'}")

print()
print("=" * 60)
print(f"RESULTS: {PASS} passed, {FAIL} failed (total {PASS+FAIL})")
print("=" * 60)

if FAIL > 0:
    sys.exit(1)
