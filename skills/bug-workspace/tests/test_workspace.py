import json, os, re, sys, tempfile, shutil

sys.path.insert(0, r"D:\06_Project\arkclaw_create\owlmyclaw\skills\bug-workspace")
sys.path.insert(0, r"D:\06_Project\arkclaw_create\owlmyclaw\skills\bug-core")

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
print("GROUP 5: Workspace Functionality")
print("=" * 60)
from bug_workspace import (generate_workspace, generate_folder_name, get_rayfile_command,
                           get_default_workspace_path, create_bug_shortcut)
from bug_core import fetch_bug_rest, format_bug_summary

# Get unisoc bug
bug_unisoc = fetch_bug_rest("219041", instance="unisoc")
test("Get unisoc bug success", bug_unisoc and "error" not in bug_unisoc)

# Folder name
fn = generate_folder_name(bug_unisoc)
test(f"Folder name starts with [219041]", fn.startswith("[219041]"), fn)
test("Folder name no illegal chars", all(c not in r'\/:*?"<>|' for c in fn[len("[219041]"):]))

# Default workspace path
default_ws = get_default_workspace_path()
test("Default workspace path directory accessible", default_ws is not None and len(default_ws) > 0)

# Rayfile command (corrected: -o download -d local_dir -s ftp_path)
ftp_url = bug_unisoc.get("ftp_urls",[""])[0]
cmd = get_rayfile_command(ftp_url, r"E:\08_Bug\test")
test("Rayfile command is dict", isinstance(cmd, dict))
test("Rayfile command contains exe", "rayfile-c_cmd.exe" in cmd["command"])
test("Rayfile command contains host", "unitrans.unisoc.com" in cmd["command"])
test("Rayfile command contains -ssl", "-ssl" in cmd["command"])
test("Rayfile command contains -o download", "-o" in cmd["command"] and "download" in cmd["command"])
test("Rayfile command contains -d", "-d" in cmd["command"])
test("Rayfile command contains -s", "-s" in cmd["command"])
test("Rayfile command contains -space_id", "-space_id" in cmd["command"] and "2" in cmd["command"])
test("Rayfile command contains -gr", "-gr" in cmd["command"] and "31240" in cmd["command"])
test("Rayfile command contains -file-update", "-file-update" in cmd["command"] and "append" in cmd["command"])
test("Rayfile args is list", isinstance(cmd["args"], list) and len(cmd["args"]) > 10)

# Full workspace creation
tmpdir = tempfile.mkdtemp(prefix="bugtest_")
try:
    ws = generate_workspace(bug_unisoc, base_path=tmpdir)
    test("Workspace created successfully", ws.get("created"))
    test("folder_path exists", os.path.exists(ws.get("folder_path","")))
    test("shortcut_file exists", os.path.exists(ws.get("shortcut_file","")))
    test("summary_file exists", os.path.exists(ws.get("summary_file","")))
    test("rayfile_commands non-empty", len(ws.get("rayfile_commands",[])) > 0)

    # Verify shortcut content
    with open(ws["shortcut_file"], "r") as f:
        sc = f.read()
    test("shortcut contains URL", "URL=" in sc)
    test("shortcut contains Bug number", "219041" in sc)

    # Verify summary content
    with open(ws["summary_file"], "r", encoding="utf-8") as f:
        sm = f.read()
    test("summary contains [Bug Summary]", "[Bug Summary]" in sm)
    test("summary contains FTP path", "ftp://" in sm.lower())

    print(f"      Folder: {ws['folder_path']}")
    for i, cmd in enumerate(ws["rayfile_commands"]):
        print(f"      Rayfile[{i}]: {str(cmd)[:100]}...")
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

# Test format_bug_summary
summary_text = format_bug_summary(bug_unisoc)
test("format_bug_summary contains Bug ID", "219041" in summary_text)
test("format_bug_summary contains FTP Path", "FTP Path" in summary_text or "ftp://" in summary_text.lower())
# Verify no emoji (Unicode emoji range U+1F600+)
test("format_bug_summary no emoji", not any(ord(c) >= 0x1F600 for c in summary_text))

# Test cross-skill import: bug_workspace's generate_workspace internally imports from bug_core
# Verify that bug_workspace can be imported standalone
test_bug = {
    "bug_id": "9999",
    "summary": "Test bug for workspace standalone",
    "status": "NEW",
    "priority": "P2",
    "severity": "normal",
    "product": "TestProduct",
    "component": "TestComponent",
    "assignee": "tester",
    "ftp_urls": ["ftp://unitrans.unisoc.com/TestLogs/test/"],
    "unc_paths": [],
    "url": "https://bugzilla.unisoc.com/bugzilla/show_bug.cgi?id=9999",
}
tmpdir2 = tempfile.mkdtemp(prefix="bugws2_")
try:
    ws2 = generate_workspace(test_bug, base_path=tmpdir2)
    test("Workspace standalone bug created", ws2.get("created"))
    test("Workspace standalone folder_name starts with [9999]", ws2["folder_name"].startswith("[9999]"))
finally:
    shutil.rmtree(tmpdir2, ignore_errors=True)

# ============================================================
# GROUP 9: Workspace Enhancement — 编排功能 + Bug Z 模板 + 路径历史
# ============================================================
from bug_workspace import (copy_bug_z_template, create_url_shortcut,
                           load_workspace_paths, save_workspace_paths,
                           open_workspace_path, generate_workspace_with_download)

print()
print("=" * 60)
print("GROUP 9: Workspace Enhancement Functions")
print("=" * 60)

# --- 9.1: copy_bug_z_template — exists (mock Bug Z dir) ---
tmp_bz = tempfile.mkdtemp(prefix="test_bz_")
try:
    bug_z_src = os.path.join(tmp_bz, "Bug Z")
    os.makedirs(os.path.join(bug_z_src, "SubFolder"))
    with open(os.path.join(bug_z_src, "template.txt"), "w") as f:
        f.write("Bug Z template content")
    with open(os.path.join(bug_z_src, "SubFolder", "data.txt"), "w") as f:
        f.write("sub data")

    dest = os.path.join(tmp_bz, "target_ws")
    os.makedirs(dest)
    copied = copy_bug_z_template(tmp_bz, dest)
    test("9.1 Bug Z template copied successfully", copied == True)
    test("9.1 Bug Z content exists in dest",
         os.path.exists(os.path.join(dest, "template.txt")))
    test("9.1 Bug Z subfolder exists in dest",
         os.path.exists(os.path.join(dest, "SubFolder", "data.txt")))
finally:
    shutil.rmtree(tmp_bz, ignore_errors=True)

# --- 9.2: copy_bug_z_template — not exists ---
tmp_no_bz = tempfile.mkdtemp(prefix="test_no_bz_")
try:
    dest_no = os.path.join(tmp_no_bz, "target")
    os.makedirs(dest_no)
    copied_no = copy_bug_z_template(tmp_no_bz, dest_no)
    test("9.2 Bug Z template not exists returns False", copied_no == False)
finally:
    shutil.rmtree(tmp_no_bz, ignore_errors=True)

# --- 9.3: create_url_shortcut — normal path ---
tmp_url = tempfile.mkdtemp(prefix="test_url_")
try:
    sp = create_url_shortcut("https://bugzilla.unisoc.com/show_bug.cgi?id=219041",
                             tmp_url, name="TestLink")
    test("9.3 URL shortcut created", os.path.exists(sp))
    test("9.3 URL shortcut ends with .url", sp.endswith(".url"))
    with open(sp, "r") as f:
        url_content = f.read()
    test("9.3 URL shortcut has [InternetShortcut]", "[InternetShortcut]" in url_content)
    test("9.3 URL shortcut has URL=", "https://bugzilla.unisoc.com" in url_content)
finally:
    shutil.rmtree(tmp_url, ignore_errors=True)

# --- 9.4: create_url_shortcut — long path (>200 chars) ---
tmp_long = tempfile.mkdtemp(prefix="test_long_url_")
try:
    long_name = "A" * 150 + "VeryLongTestName"
    sp_long = create_url_shortcut("https://example.com/test", tmp_long, name=long_name)
    test("9.4 Long URL shortcut created", os.path.exists(sp_long))
    test("9.4 Long URL shortcut simplified to Bug.url", os.path.basename(sp_long) == "Bug.url")
finally:
    shutil.rmtree(tmp_long, ignore_errors=True)

# --- 9.5: load_workspace_paths ---
paths = load_workspace_paths()
test("9.5 load_workspace_paths returns list", isinstance(paths, list))
test("9.5 load_workspace_paths non-empty", len(paths) > 0)
test("9.5 load_workspace_paths has E:\\08_Bug",
     any("08_Bug" in p for p in paths))
test("9.5 load_workspace_paths has F:\\PD认证",
     any("PD认证" in p for p in paths))

# --- 9.6: save_workspace_paths (temp config) ---
tmp_cfg = tempfile.mkdtemp(prefix="test_paths_cfg_")
try:
    test_paths = [
        r"E:\08_Bug",
        r"E:\08_Bug\CQ",
        r"E:\08_Bug\Task",
    ]
    saved = save_workspace_paths(test_paths, config_dir=tmp_cfg)
    test("9.6 save_workspace_paths returns True", saved == True)

    # Verify file was written
    paths_file = os.path.join(tmp_cfg, "paths.json")
    test("9.6 paths.json created", os.path.exists(paths_file))
    if os.path.exists(paths_file):
        with open(paths_file, "r") as f:
            loaded = json.load(f)
        test("9.6 loaded paths match saved", loaded == test_paths)

        # Test dedup
        saved_dedup = save_workspace_paths(
            [r"E:\08_Bug", r"E:\08_Bug", r"E:\08_Bug\CQ"], config_dir=tmp_cfg)
        test("9.6 save dedup returns True", saved_dedup == True)
        if os.path.exists(paths_file):
            with open(paths_file, "r") as f:
                deduped = json.load(f)
            test("9.6 dup paths deduplicated", len(deduped) == 2)
finally:
    shutil.rmtree(tmp_cfg, ignore_errors=True)

# --- 9.7: open_workspace_path ---
# open_existing: opens an actual directory (no OS error)
test("9.7 open_workspace_path existing dir returns True",
     open_workspace_path(tempfile.gettempdir()) == True)
test("9.7 open_workspace_path nonexistent returns False",
     open_workspace_path("\\\\nonexistent\\no_such_path") == False)
test("9.7 open_workspace_path empty returns False",
     open_workspace_path("") == False)

# --- 9.8: generate_workspace_with_download — e2e orchestration (no download) ---
test_bug_full = {
    "bug_id": "8888",
    "summary": "Full orchestration test bug",
    "status": "NEW",
    "priority": "P2",
    "severity": "normal",
    "product": "TestProduct",
    "component": "TestComponent",
    "assignee": "tester",
    "ftp_urls": [],
    "unc_paths": [],
    "url": "https://bugzilla.unisoc.com/bugzilla/show_bug.cgi?id=8888",
}
tmp_full = tempfile.mkdtemp(prefix="bug_full_")
try:
    # Without download (pure folder creation + shortcut)
    result = generate_workspace_with_download(
        test_bug_full, base_path=tmp_full, download=False, copy_bug_z=False)
    test("9.8 orchestration no-download success", result["success"] == True,
         str(result.get("errors", [])))
    test("9.8 orchestration folder created",
         os.path.exists(result["folder"]["folder_path"]))
    test("9.8 orchestration has shortcut",
         os.path.exists(result["folder"]["shortcut_file"]))
    test("9.8 orchestration has summary",
         os.path.exists(result["folder"]["summary_file"]))
    test("9.8 orchestration no Bug Z copied", result["bug_z_copied"] == False)
    # Download should be empty dict (no download requested)
    test("9.8 orchestration download is empty", result["download"] == {})
finally:
    shutil.rmtree(tmp_full, ignore_errors=True)

print()
print("=" * 60)
print(f"RESULTS: {PASS} passed, {FAIL} failed (total {PASS+FAIL})")
print("=" * 60)

if FAIL > 0:
    sys.exit(1)
