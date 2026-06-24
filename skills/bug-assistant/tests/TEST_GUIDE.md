# Bug 智能助手 测试指南

> 版本: v2.0 | 日期: 2026-06-05
> 目标读者: 测试工程师
> 前置知识: 无需了解 Python 或内部实现，按步骤操作即可
>
> **🔴 更新说明**: bug-assistant 已拆分为 3 个独立 Skill（bug-core / bug-logs / bug-workspace），测试文件相应分为 3 套独立测试。

---

## 一、测试环境准备

### 1.1 硬件/网络要求

| 条件 | 要求 | 说明 |
|------|------|------|
| 操作系统 | **Windows 10/11** | 必须！UNC 目录列表功能依赖 Windows API |
| Python | Python 3.10+ | 测试脚本运行环境 |
| 内网连接 | 办公网（可访问 unisoc Bugzilla） | GROUP 2/4/5/6/8 部分测试需要 |
| 共享目录 | `\\shnas02\TestLogs` 可访问 | GROUP 8.2 测试需要 |

### 1.2 安装依赖

打开 **命令提示符 (cmd)** 或 **PowerShell**，执行：

```batch
pip install httpx requests
```

> **说明**: `httpx` 用于 HTTP API 调用，`requests` 用于 REST 评论查询。已在办公网开发机上预装。

### 1.3 运行测试

测试分为 **3 套独立测试文件**，分别对应 3 个 Skill：

```batch
:: bug-core — Bug 查询核心 (GROUP 1-4, 6-7, 共 63 用例)
cd skills\bug-core
python tests\test_core.py

:: bug-workspace — 工作区管理 (GROUP 5 + GROUP 9, 共 57 用例)
cd skills\bug-workspace
python tests\test_workspace.py

:: bug-logs — 日志目录与附件下载 (GROUP 8 + GROUP 9, 共 51 用例)
cd skills\bug-logs
python tests\test_logs.py
```

**预期结果**: 3 套测试全部通过，总计 **136 passed, 0 failed**。

---

## 二、测试分组说明

### 2.1 bug-core 测试 (test_core.py) — 63 用例

| 分组 | 名称 | 用例数 | 需要网络 | 说明 |
|:---:|------|:---:|:---:|------|
| 1 | 配置完整性 | 12 | ❌ | 验证配置文件结构和 5 个 Bugzilla 实例 |
| 2 | REST API — 5个实例 | 12 | ✅ | 验证所有 Bugzilla 实例可达 |
| 3 | MCP Server API Key | 7 | ❌ | 验证 API key 匹配/不匹配逻辑 |
| 4 | MCP 直接API调用 | 8 | ✅ | 模拟 MCP 工具调用 |
| 6 | CLI 端到端 | 14 | ✅ | 验证命令行工具各参数（--help/--json/--offline/--list） |
| 7 | 错误处理 | 10 | ✅ | 验证 401/403/404/无效实例/离线不存在等 |

### 2.2 bug-workspace 测试 (test_workspace.py) — 57 用例

| 分组 | 名称 | 用例数 | 需要网络 | 说明 |
|:---:|------|:---:|:---:|------|
| 5 | 工作区功能 | 30 | ✅ | 文件夹命名/rayfile命令(修正-o/-d/-s)/快捷方式/摘要/独立创建 |
| 9 | 工作区增强 | 27 | ❌ | Bug Z模板复制/URL快捷方式/路径历史/快速打开/编排下载 |

### 2.3 bug-logs 测试 (test_logs.py) — 51 用例 ⭐

| 分组 | 名称 | 用例数 | 需要网络 | 说明 |
|:---:|------|:---:|:---:|------|
| 8 | 日志目录 & 结构化解析 | 32 | ✅ | 结构化评论解析/UNC目录/FTP fallback/组合查询/MCP工具 |
| 9 | 附件下载 🔴 | 19 | ✅/❌ | 附件类型检测/UNC下载/normalize/端到端下载 |

---

## 三、GROUP 8 详细测试用例（新增功能）

> **测试目标**: 验证 unisoc Bug 的日志目录列表功能和结构化评论解析功能。

### 3.1 结构化评论解析 (8.1)

**功能说明**: unisoc Bugzilla 的 Comment #0 使用固定的 19 字段模板格式（如 `[14.Logpath]:`），该功能自动提取 LogPath、LogType、VersionPath 等关键字段。

| 用例编号 | 断言内容 | 预期结果 | 验证方法 |
|:---:|------|------|------|
| 8.1-1 | 结构化格式已识别 | `True` | 解析 comment_0.txt 后 `has_structured_format` 为 True |
| 8.1-2 | log_path 非空 | 长度 > 20 字符 | 提取的路径至少包含完整 UNC 路径 |
| 8.1-3 | log_path 是 UNC 路径 | 以 `\\` 开头 | 路径格式为 `\\server\share\...` |
| 8.1-4 | log_servers 含 external | external 值非空 | 外部日志服务器路径已提取 |
| 8.1-5 | log_servers 含 internal | internal 值非空 | 内部日志服务器路径已提取 |
| 8.1-6 | log_servers 含 ftp | 包含 `ftp://` | FTP 下载地址已提取 |
| 8.1-7 | log_type 正确 | 值为 `Default` | Logtype 字段值为 Default |
| 8.1-8 | version_path 含 SPRDROID | 包含关键字 | 版本路径正确提取 |
| 8.1-9 | header 含 severity | 包含 `Major` | 严重级别正确提取 |
| 8.1-10 | 所有 19 字段已提取 | fields 字典有 19 项 | 所有编号字段完整解析 |
| 8.1-11 | log_name 空 | 空字符串 | 原始 LogName 字段无值时不编造 |

**手动验证方法**:
```batch
cd skills\bug-logs
python -c "from bug_logs import parse_unisoc_structured_fields; import json; text=open('comment_0.txt','r',encoding='utf-8').read(); r=parse_unisoc_structured_fields(text); print(json.dumps(r, ensure_ascii=False, indent=2))"
```

### 3.2 UNC 目录列表 — 可访问路径 (8.2)

**功能说明**: 在 Windows 办公网环境下，直接通过 `\\server\share` 路径列出日志目录内容。

| 用例编号 | 断言内容 | 预期结果 | 验证方法 |
|:---:|------|------|------|
| 8.2-1 | UNC TestLogs 可访问 | `accessible` 为 `True` | 访问 `\\shnas02\TestLogs` 成功 |
| 8.2-2 | UNC method 正确 | method 值为 `"unc"` | 使用 UNC 方式访问 |
| 8.2-3 | UNC 有 entries | entries 数组非空 | 至少列出 1 个条目 |
| 8.2-4 | UNC 有 subdirs | subdirs 数组非空 | 至少含 1 个子目录 |
| 8.2-5 | UNC 含 PSST 子目录 | subdirs 包含 `"PSST"` | 已知存在的子目录 |
| 8.2-6 | files 是列表 | `isinstance(list)` | 返回正确的数据结构 |
| 8.2-7 | subdirs 是列表 | `isinstance(list)` | 返回正确的数据结构 |
| 8.2-8 | entries 含 name/type/size | 前 3 项均含 3 个字段 | 每个条目结构完整 |

**手动验证方法**:
```batch
cd skills\bug-logs
python -c "from bug_logs import list_log_directory; import json; r=list_log_directory('\\\\shnas02\\TestLogs'); print(json.dumps(r, ensure_ascii=False, indent=2))"
```

### 3.3 不存在路径 — 优雅降级 (8.3)

**功能说明**: 访问不存在的 UNC 路径时，不会崩溃，而是返回明确的错误信息。

| 用例编号 | 断言内容 | 预期结果 | 验证方法 |
|:---:|------|------|------|
| 8.3-1 | 不存在路径不可访问 | `accessible` 为 `False` | 访问失败正确标记 |
| 8.3-2 | 不存在路径含 error | error 字段非空 | 包含具体错误描述 |

### 3.4 FTP Fallback — 不崩溃 (8.4)

**功能说明**: 当 UNC 路径无法访问时，尝试 FTP fallback。即使 FTP 也无法连接（如路径不存在），程序不会崩溃。

| 用例编号 | 断言内容 | 预期结果 | 验证方法 |
|:---:|------|------|------|
| 8.4-1 | FTP fallback 不崩溃 | 返回 dict 类型 | 无异常抛出 |
| 8.4-2 | FTP fallback inaccessible | `accessible` 为 `False` | 不存在路径正确标记 |

### 3.5 非结构化文本 — 无副作用 (8.5)

| 用例编号 | 断言内容 | 预期结果 | 验证方法 |
|:---:|------|------|------|
| 8.5-1 | kernel 文本无结构化格式 | `has_structured_format` 为 `False` | 不误报 |
| 8.5-2 | kernel 文本 log_path 空 | `log_path` 为空字符串 | 不编造数据 |

### 3.6 fetch_bug_with_logs 端到端 (8.6)

| 用例编号 | 断言内容 | 预期结果 |
|:---:|------|------|
| 8.6-1 | advanced fetch 成功 | 无 error 字段 |
| 8.6-2 | 含 structured_fields | 结构化解析已执行 |
| 8.6-3 | 含 log_directory | 目录列表已执行 |

### 3.7 MCP bug_logs 工具 (8.7)

| 用例编号 | 断言内容 | 预期结果 |
|:---:|------|------|
| 8.7-1 | bug_info 结构正确 | 含 id/summary/status/product/component/url |
| 8.7-2 | structured_fields 含 log_path | 结构化解析完整 |
| 8.7-3 | log_directory 含 entries 或 error | 目录列表正常执行 |

---

## ⭐ GROUP 9 详细测试用例（v2.0 下载重构新增）

> **测试目标**: 验证 bug-logs 的附件下载能力、bug-workspace 的工作区编排增强功能。

### bug-logs GROUP 9: 附件下载 (19 用例)

#### 9.1 detect_attachment_type — 附件类型检测

| 用例编号 | 断言内容 | 预期结果 | 验证方法 |
|:---:|------|------|------|
| 9.1-1 | detect_attachment_type 可调用 | callable | 函数存在且可调用 |
| 9.1-2 | unisoc Bug 返回 unc 类型 | type 为 `"unc"` | unisoc Bug 含 [14.Logpath] UNC 路径 |
| 9.1-3 | 返回含 source_path | source_path 非空 | UNC 路径已提取 |
| 9.1-4 | 返回含 bug_info | bug_info 为 dict | Bug 信息完整 |

#### 9.2 copy_missing — 递归复制

| 用例编号 | 断言内容 | 预期结果 |
|:---:|------|------|
| 9.2-1 | 文件正确复制 | 目标文件存在 |
| 9.2-2 | 子目录文件复制 | 子目录下文件也复制 |
| 9.2-3 | 已存在文件不覆盖 | 原有内容不变 |

#### 9.3 download_from_unc_path — 可访问路径

| 用例编号 | 断言内容 | 预期结果 |
|:---:|------|------|
| 9.3-1 | UNC 下载成功 | success 为 True |
| 9.3-2 | 3 个文件被复制 | copied >= 3 |
| 9.3-3 | 子目录不复制 | 仅文件复制 |

#### 9.4 download_from_unc_path — 不可访问路径

| 用例编号 | 断言内容 | 预期结果 |
|:---:|------|------|
| 9.4-1 | 不存在路径返回错误 | success 为 False |
| 9.4-2 | 含 error 信息 | error 非空 |

#### 9.5 normalize_downloaded_folder — "off" 模式

| 用例编号 | 断言内容 | 预期结果 |
|:---:|------|------|
| 9.5-1 | off 模式不做任何处理 | 文件保持在原子目录中 |

#### 9.6 normalize_downloaded_folder — "move" 模式

| 用例编号 | 断言内容 | 预期结果 |
|:---:|------|------|
| 9.6-1 | 文件上移一层 | 根目录直接可见文件 |
| 9.6-2 | 原子目录已删除 | 子目录不存在 |

#### 9.7 normalize_downloaded_folder — "copy_new" 模式

| 用例编号 | 断言内容 | 预期结果 |
|:---:|------|------|
| 9.7-1 | 新文件被复制 | 新文件出现在根目录 |
| 9.7-2 | 已存在文件不变 | 原文件内容保留 |

#### 9.8 normalize_downloaded_folder — 非匹配子目录

| 用例编号 | 断言内容 | 预期结果 |
|:---:|------|------|
| 9.8-1 | 非匹配子目录跳过 | 不做 normalize |

#### 9.9-9.10 download_bug_attachments — 端到端

| 用例编号 | 断言内容 | 预期结果 |
|:---:|------|------|
| 9.9-1 | download_bug_attachments 可调用 | callable |
| 9.10-1 | 不存在 Bug 返回错误 | success 为 False |

---

### bug-workspace GROUP 9: 工作区增强 (27 用例)

#### 9.1 copy_bug_z_template — 存在模板

| 用例编号 | 断言内容 | 预期结果 |
|:---:|------|------|
| 9.1-1 | Bug Z 模板复制成功 | 返回 True |
| 9.1-2 | 根目录文件存在 | template.txt 已复制 |
| 9.1-3 | 子目录文件存在 | SubFolder/data.txt 已复制 |

#### 9.2 copy_bug_z_template — 不存在模板

| 用例编号 | 断言内容 | 预期结果 |
|:---:|------|------|
| 9.2-1 | 模板不存在返回 False | 返回 False |

#### 9.3 create_url_shortcut — 正常路径

| 用例编号 | 断言内容 | 预期结果 |
|:---:|------|------|
| 9.3-1 | 快捷方式已创建 | .url 文件存在 |
| 9.3-2 | 格式正确 | 含 [InternetShortcut] |
| 9.3-3 | URL 正确 | 含完整 URL |

#### 9.4 create_url_shortcut — 超长路径

| 用例编号 | 断言内容 | 预期结果 |
|:---:|------|------|
| 9.4-1 | 超长路径已创建 | 文件存在 |
| 9.4-2 | 自动简化为 Bug.url | 文件名简化 |

#### 9.5 load_workspace_paths

| 用例编号 | 断言内容 | 预期结果 |
|:---:|------|------|
| 9.5-1 | 返回 list | isinstance(list) |
| 9.5-2 | 非空 | 含 15 个默认路径 |
| 9.5-3 | 含 E:\08_Bug | 已知默认路径存在 |
| 9.5-4 | 含 F:\PD认证 | 已知默认路径存在 |

#### 9.6 save_workspace_paths

| 用例编号 | 断言内容 | 预期结果 |
|:---:|------|------|
| 9.6-1 | 保存成功 | 返回 True |
| 9.6-2 | 文件已创建 | paths.json 存在 |
| 9.6-3 | 加载匹配 | 读回与写入一致 |
| 9.6-4 | 路径去重 | 重复路径被合并 |

#### 9.7 open_workspace_path

| 用例编号 | 断言内容 | 预期结果 |
|:---:|------|------|
| 9.7-1 | 存在目录返回 True | os.startfile 成功 |
| 9.7-2 | 不存在路径返回 False | 空路径处理 |
| 9.7-3 | 空路径返回 False | 防御性处理 |

#### 9.8 generate_workspace_with_download — 端到端编排

| 用例编号 | 断言内容 | 预期结果 |
|:---:|------|------|
| 9.8-1 | 编排成功 | success 为 True |
| 9.8-2 | 文件夹已创建 | folder_path 存在 |
| 9.8-3 | 快捷方式已创建 | shortcut_file 存在 |
| 9.8-4 | 摘要已生成 | summary_file 存在 |
| 9.8-5 | 无 Bug Z 时不复制 | bug_z_copied 为 False |
| 9.8-6 | 无下载时 download 为空 | download == {} |

---

## 四、其他测试组简要说明

<details>
<summary><b>GROUP 1: 配置完整性 (12 用例) — 展开查看</b></summary>

验证 5 个 Bugzilla 实例配置（kernel/mozilla/gnome/unisoc/local）、api_key、ftp 凭证、default_instance、get_instance_config。
</details>

<details>
<summary><b>GROUP 2: REST API (12 用例) — 展开查看</b></summary>

验证 kernel/mozilla/gnome/unisoc/local 所有实例的 Bug 查询（summary/status/ftp_urls/comments）。
</details>

<details>
<summary><b>GROUP 3: MCP API Key (7 用例) — 展开查看</b></summary>

验证 `_get_api_key_for_url()` 对 5 个已知 URL 和 1 个未知 URL 的匹配/不匹配。
</details>

<details>
<summary><b>GROUP 4: MCP 直接API调用 (8 用例) — 展开查看</b></summary>

模拟 MCP 工具调用 Kernel/Mozilla/GNOME/Unisoc 的 Bug 信息和评论 API。验证 FTP URL 和 UNC 路径提取。
</details>

<details>
<summary><b>GROUP 5: 工作区功能 (30 用例) — 展开查看</b></summary>

验证文件夹命名/rayfile 命令（含 -o download -d -s -space_id -gr）/快捷方式（含 URL+ID）/Bug 摘要（无 emoji）/独立模式（无 API）。跨 Skill 导入验证（bug-workspace → bug_core）。
</details>

<details>
<summary><b>GROUP 6: CLI 端到端 (14 用例) — 展开查看</b></summary>

验证 bug-core 命令行工具：--help（不含 --workspace）/ kernel/mozilla/gnome/unisoc 查询 / --json 输出 / --offline 模式 / --list 列表。
</details>

<details>
<summary><b>GROUP 7: 错误处理 (10 用例) — 展开查看</b></summary>

验证 401/403/404、离线不存在 Bug、无效实例等错误场景。
</details>

---

## 五、跨 Skill 导入验证

拆分后 bug-logs 和 bug-workspace 依赖 bug-core，验证交叉导入：

```batch
:: 验证 bug-logs 可以导入 bug_core
cd skills\bug-logs
python -c "from bug_logs import fetch_bug_with_logs; print('bug-logs OK')"

:: 验证 bug-workspace 可以导入 bug_core
cd skills\bug-workspace
python -c "from bug_workspace import generate_workspace; print('bug-workspace OK')"

:: 验证 MCP Server 可以从 3 个模块导入
cd skills\bug-core\mcp-server
python -c "import server; print('MCP Server OK')"
```

---

## 六、常见问题排查

### Q1: 提示 "No module named 'httpx'"

**解决**: 在命令提示符中执行 `pip install httpx requests`。

### Q2: GROUP 2/4/8 测试失败，提示 "Connection timed out" 或 "403"

**原因**: 不在办公网环境，无法访问 unisoc Bugzilla。
**解决**: 切换到办公网环境再测试。Kernel/Mozilla 测试在外网也可通过。

### Q3: GROUP 8.2 测试失败，提示 "UNC listing only supported on Windows"

**原因**: 在非 Windows 系统运行。
**解决**: 此功能为 Windows 专属，需在 Windows 10/11 办公网环境运行。

### Q4: GROUP 8.1 测试失败，提示 "comment_0.txt" not found

**原因**: 测试参考文件缺失。
**解决**: 确保 `bug-logs/comment_0.txt` 文件存在。

### Q5: 交叉导入失败，提示 "No module named 'bug_core'"

**原因**: PYTHONPATH 未配置或未从正确目录运行。
**解决**: 按上述命令从对应 skill 目录运行，测试脚本会自动配置 sys.path。

---

## 七、测试报告模板

```markdown
## Bug 智能助手 测试报告

| 项目 | 内容 |
|------|------|
| 测试日期 | YYYY-MM-DD |
| 测试人员 | xxx |
| 测试环境 | Windows 10/11, 办公网 |
| Python 版本 | Python 3.x.x |

### 测试结果

| 测试文件 | Skill | 用例数 | 通过 | 失败 | 备注 |
|---------|------|:---:|:---:|:---:|------|
| test_core.py | bug-core | 63 | ___ | ___ | |
| test_workspace.py | bug-workspace | 57 | ___ | ___ | |
| test_logs.py | bug-logs | 51 | ___ | ___ | |
| **合计** | | **136** | ___ | ___ | |

### 失败用例详情

| 编号 | 错误信息 | 分析 |
|------|---------|------|

### 结论

□ 全部通过，可以发布
□ 部分失败，需修复后重试（附失败详情）
```

---

> 版本: v2.0 | 作者: OWLMYCLAW Team | 日期: 2026-06-05
