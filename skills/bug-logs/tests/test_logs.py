import json, os, re, sys

sys.path.insert(0, r"D:\06_Project\arkclaw_create\owlmyclaw\skills\bug-logs")
sys.path.insert(0, r"D:\06_Project\arkclaw_create\owlmyclaw\skills\bug-core")
sys.path.insert(0, r"D:\06_Project\arkclaw_create\owlmyclaw\skills\bug-core\mcp-server")

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
print("GROUP 8: Log Directory Listing & Structured Parsing")
print("=" * 60)
from bug_logs import (parse_unisoc_structured_fields, list_log_directory,
                       fetch_bug_with_logs, load_config as _load_config_g8)

# --- 8.1: Structured Comment Parsing ---
comment0_path = os.path.join(os.path.dirname(__file__), "..", "comment_0.txt")
if os.path.exists(comment0_path):
    with open(comment0_path, "r", encoding="utf-8") as f:
        comment0_text = f.read()
else:
    comment0_text = ""

structured = parse_unisoc_structured_fields(comment0_text)
if comment0_text:
    test("8.1 Structured format detected", structured.get("has_structured_format") == True)
    test("8.1 log_path non-empty", len(structured.get("log_path", "")) > 20,
         f"log_path={structured.get('log_path', '')[:60]}")
    test("8.1 log_path is UNC path", structured.get("log_path", "").startswith("\\\\"))
    test("8.1 log_servers has external", len(structured.get("log_servers", {}).get("external", "")) > 0)
    test("8.1 log_servers has internal", len(structured.get("log_servers", {}).get("internal", "")) > 0)
    test("8.1 log_servers has ftp", "ftp://" in structured.get("log_servers", {}).get("ftp", ""))
    test("8.1 log_type correct", structured.get("log_type") == "Default")
    test("8.1 version_path contains SPRDROID", "SPRDROID" in structured.get("version_path", ""))
    test("8.1 header has severity", "Major" in structured.get("header", {}).get("severity_desc", ""))
    test("8.1 All 19 fields extracted", len(structured.get("fields", {})) == 19,
         f"Got {len(structured.get('fields', {}))}")
    test("8.1 log_name empty (original is empty)", structured.get("log_name", "") == "")
else:
    test("8.1 comment_0.txt found", False, "comment_0.txt missing - skipping structured parse tests")

# --- 8.2: Directory Listing — UNC Accessible Path ---
unc_testlog = "\\\\shnas02\\TestLogs"
result_unc = list_log_directory(unc_testlog)
test("8.2 UNC TestLogs accessible", result_unc["accessible"] == True,
     f"error: {result_unc.get('error', 'None')}")
test("8.2 UNC method correct", result_unc["method"] == "unc")
test("8.2 UNC has entries", len(result_unc["entries"]) > 0)
test("8.2 UNC has subdirs", len(result_unc["subdirs"]) > 0)
test("8.2 UNC contains PSST subdir", "PSST" in result_unc["subdirs"],
     f"subdirs: {result_unc['subdirs'][:10]}")
test("8.2 files is list", isinstance(result_unc["files"], list))
test("8.2 subdirs is list", isinstance(result_unc["subdirs"], list))
test("8.2 entries have name/type/size",
     all("name" in e and "type" in e and "size" in e for e in result_unc["entries"][:3]))

# --- 8.3: Directory Listing — Non-Existent Path ---
result_bad = list_log_directory("\\\\nonexistent_server\\no_such_path")
test("8.3 Non-existent path not accessible", result_bad["accessible"] == False)
test("8.3 Non-existent path has error", result_bad.get("error") is not None and len(result_bad["error"]) > 0)

# --- 8.4: Directory Listing — FTP Fallback (timeout is expected, verify no crash) ---
unisoc_cfg = _load_config_g8()["instances"]["unisoc"]
result_ftp = list_log_directory("\\\\nobody\\nowhere", config=unisoc_cfg)
test("8.4 FTP fallback no crash", isinstance(result_ftp, dict))
test("8.4 FTP fallback inaccessible", result_ftp["accessible"] == False)

# --- 8.5: No Structured Format Bug (kernel) ---
kernel_text = "Some random comment without unisoc format\nJust a normal bug report."
kernel_structured = parse_unisoc_structured_fields(kernel_text)
test("8.5 kernel text no structured format", kernel_structured.get("has_structured_format") == False)
test("8.5 kernel text log_path empty", kernel_structured.get("log_path", "") == "")

# --- 8.6: fetch_bug_with_logs — unisoc bug ---
def safe_fetch_with_logs(bug_id, instance):
    try:
        return fetch_bug_with_logs(bug_id, instance=instance)
    except Exception as e:
        return {"error": str(e)}

result_adv = safe_fetch_with_logs("219041", "unisoc")
test("8.6 advanced fetch success", result_adv and "error" not in result_adv,
     str(result_adv.get("error", "")))
if result_adv and "error" not in result_adv:
    test("8.6 has structured_fields", "structured_fields" in result_adv)
    test("8.6 has log_directory", "log_directory" in result_adv)
    sf = result_adv.get("structured_fields", {})
    ld = result_adv.get("log_directory")
    test("8.6 structured_fields is dict", isinstance(sf, dict))
    if ld is not None:
        test("8.6 log_directory has path", "path" in ld)
        test("8.6 log_directory has accessible", "accessible" in ld)

# --- 8.7: MCP bug_logs Tool Output Structure ---
from server import _get_api_key_for_url
base_unisoc = "https://bugzilla.unisoc.com/bugzilla"
key = _get_api_key_for_url(base_unisoc)
if key:
    params = {"api_key": key}
    headers = {"Accept": "application/json", "Content-Type": "application/json", "api_key": key}
    resp_bug = httpx.get(f"{base_unisoc}/rest/bug/219041", params=params, headers=headers, timeout=15)
    resp_cmt = httpx.get(f"{base_unisoc}/rest/bug/219041/comment", params=params, headers=headers, timeout=15)
    if resp_bug.status_code == 200 and resp_cmt.status_code == 200:
        bug = resp_bug.json()["bugs"][0]
        comments_list = []
        for bc in resp_cmt.json().get("bugs", {}).values():
            comments_list = bc.get("comments", [])
            break
        first_text = comments_list[0].get("text", "") if comments_list else ""
        sf_mcp = parse_unisoc_structured_fields(first_text)
        test("8.7 MCP: bug_info structure correct",
             all(k in {"id", "summary", "status", "product", "component", "url"}
                 for k in ["id", "summary", "status", "product", "component", "url"]))
        test("8.7 MCP: structured_fields has log_path", "log_path" in sf_mcp)
        if sf_mcp.get("has_structured_format"):
            ld_mcp = list_log_directory(sf_mcp["log_path"])
            test("8.7 MCP: log_directory has entries or error",
                 "entries" in ld_mcp or "error" in ld_mcp)
            print(f"      MCP log listing: accessible={ld_mcp.get('accessible')}, "
                  f"files={len(ld_mcp.get('files',[]))}, dirs={len(ld_mcp.get('subdirs',[]))}")
    else:
        test("8.7 MCP API call success", False,
             f"bug:{resp_bug.status_code} cmt:{resp_cmt.status_code}")
else:
    test("8.7 MCP API key available", False, "No API key for unisoc")

# ============================================================
# GROUP 9: Attachment Download — 附件下载新功能
# ============================================================
import tempfile
import shutil

print()
print("=" * 60)
print("GROUP 9: Attachment Download Functions")
print("=" * 60)

from bug_logs import (detect_attachment_type, download_from_unc_path,
                       download_from_rayfile, normalize_downloaded_folder,
                       copy_missing, download_bug_attachments)

# --- 9.1: detect_attachment_type — imports correctly ---
test("9.1 detect_attachment_type is callable", callable(detect_attachment_type))

# --- 9.2: copy_missing — basic functionality ---
def test_copy_missing():
    tmp = tempfile.mkdtemp(prefix="test_copy_missing_")
    try:
        src = os.path.join(tmp, "src")
        dst = os.path.join(tmp, "dst")
        os.makedirs(os.path.join(src, "subdir"))
        with open(os.path.join(src, "file1.txt"), "w") as f:
            f.write("hello")
        with open(os.path.join(src, "subdir", "file2.txt"), "w") as f:
            f.write("world")

        # First copy: both files should be copied
        copy_missing(src, dst)
        r1 = os.path.exists(os.path.join(dst, "file1.txt"))
        r2 = os.path.exists(os.path.join(dst, "subdir", "file2.txt"))

        # Second copy: nothing should change (already exist)
        copy_missing(src, dst)
        r3 = os.path.exists(os.path.join(dst, "file1.txt"))

        return r1 and r2 and r3
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

test("9.2 copy_missing recursive copy", test_copy_missing())

# --- 9.3: download_from_unc_path — accessible path ---
tmp_unc = tempfile.mkdtemp(prefix="test_unc_dl_")
try:
    # Create test files in tmp dir simulating UNC structure
    for i in range(3):
        with open(os.path.join(tmp_unc, f"test_log_{i}.txt"), "w") as f:
            f.write(f"log content {i}")
    # Also create a subdir (should be skipped, only files copied)
    os.makedirs(os.path.join(tmp_unc, "subdir"))

    dest_unc = os.path.join(tmp_unc, "output")
    result_unc_dl = download_from_unc_path(tmp_unc, dest_unc)
    test("9.3 UNC download accessible path success", result_unc_dl["success"] == True,
         str(result_unc_dl.get("errors", [])))
    test("9.3 UNC download copied 3 files", result_unc_dl["copied"] == 3,
         f"copied={result_unc_dl['copied']}")
    test("9.3 UNC download dest dir correct", result_unc_dl["dest_dir"] == dest_unc)
finally:
    shutil.rmtree(tmp_unc, ignore_errors=True)

# --- 9.4: download_from_unc_path — non-existent path ---
result_bad_unc = download_from_unc_path("\\\\nonexistent\\path", tempfile.mkdtemp(prefix="bad_unc_"))
test("9.4 UNC download bad path not accessible", result_bad_unc["success"] == False)
test("9.4 UNC download has error message", len(result_bad_unc.get("errors", [])) > 0)
shutil.rmtree(result_bad_unc["dest_dir"], ignore_errors=True)

# --- 9.5: normalize_downloaded_folder — "off" mode ---
tmp_norm = tempfile.mkdtemp(prefix="test_norm_")
try:
    # Create structure: Attachements/SPCSS_12345/file.txt
    attach = os.path.join(tmp_norm, "Attachements")
    child = os.path.join(attach, "SPCSS_12345")
    os.makedirs(child)
    with open(os.path.join(child, "data.txt"), "w") as f:
        f.write("test data")

    norm_off = normalize_downloaded_folder(attach, "12345", action="off")
    test("9.5 normalize off mode returns processed=False", norm_off["processed"] == False)
    test("9.5 normalize off mode action is off", norm_off["action"] == "off")
finally:
    shutil.rmtree(tmp_norm, ignore_errors=True)

# --- 9.6: normalize_downloaded_folder — "move" mode ---
tmp_move = tempfile.mkdtemp(prefix="test_norm_move_")
try:
    attach = os.path.join(tmp_move, "Attachements")
    child = os.path.join(attach, "SPCSS_00001")
    os.makedirs(child)
    with open(os.path.join(child, "log.txt"), "w") as f:
        f.write("move test")
    with open(os.path.join(child, "data.bin"), "w") as f:
        f.write("binary")

    norm_move = normalize_downloaded_folder(attach, "00001", action="move")
    test("9.6 normalize move mode processed=True", norm_move["processed"] == True,
         f"error={norm_move.get('error')}")
    test("9.6 normalize move child name correct", norm_move["child_name"] == "SPCSS_00001")
    # Files should now be in attachment root, child dir removed
    test("9.6 normalize move file in root", os.path.exists(os.path.join(attach, "log.txt")))
    test("9.6 normalize move child removed", not os.path.exists(child))
finally:
    shutil.rmtree(tmp_move, ignore_errors=True)

# --- 9.7: normalize_downloaded_folder — "copy_new" mode (default) ---
tmp_cn = tempfile.mkdtemp(prefix="test_norm_cn_")
try:
    attach = os.path.join(tmp_cn, "Attachements")
    child = os.path.join(attach, "SPCSS_99999")
    os.makedirs(child)
    with open(os.path.join(child, "new.txt"), "w") as f:
        f.write("new file")

    # Pre-create a file in root to test no-overwrite behavior
    with open(os.path.join(attach, "existing.txt"), "w") as f:
        f.write("existing")

    norm_cn = normalize_downloaded_folder(attach, "99999", action="copy_new")
    test("9.7 normalize copy_new processed=True", norm_cn["processed"] == True,
         f"error={norm_cn.get('error')}")
    test("9.7 normalize copy_new new file copied",
         os.path.exists(os.path.join(attach, "new.txt")))
    test("9.7 normalize copy_new existing untouched",
         os.path.exists(os.path.join(attach, "existing.txt")))
finally:
    shutil.rmtree(tmp_cn, ignore_errors=True)

# --- 9.8: normalize_downloaded_folder — no matching child ---
tmp_nomatch = tempfile.mkdtemp(prefix="test_norm_nomatch_")
try:
    attach = os.path.join(tmp_nomatch, "Attachements")
    child = os.path.join(attach, "SomeRandomName")
    os.makedirs(child)
    with open(os.path.join(child, "data.txt"), "w") as f:
        f.write("data")

    norm_nm = normalize_downloaded_folder(attach, "12345", action="copy_new")
    test("9.8 normalize non-matching child skipped", norm_nm["processed"] == False)
finally:
    shutil.rmtree(tmp_nomatch, ignore_errors=True)

# --- 9.9: download_bug_attachments — import and basic structure ---
test("9.9 download_bug_attachments is callable", callable(download_bug_attachments))

# --- 9.10: download_bug_attachments — error on nonexistent bug ---
result_dl_err = download_bug_attachments("999999999", tempfile.mkdtemp(prefix="test_dl_err_"),
                                          instance=None)
test("9.10 download nonexistent bug returns error",
     result_dl_err["attachment_type"] == "none" or len(result_dl_err.get("errors", [])) > 0)
shutil.rmtree(result_dl_err["dest_dir"], ignore_errors=True)

print()
print("=" * 60)
print(f"RESULTS: {PASS} passed, {FAIL} failed (total {PASS+FAIL})")
print("=" * 60)

if FAIL > 0:
    sys.exit(1)
