#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交互式日志查看器 - Notepad++ 风格实时筛选
将原始日志转换为可交互的 HTML 页面，支持关键词高亮、实时过滤、行号导航。

用法:
    python log_viewer.py <logfile> [output_html]
    python log_viewer.py sample_pd.log pd_viewer.html
"""

import json
import sys
import html as html_mod
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OWLMYCLAW Log Viewer - {title}</title>
<style>
:root {
    --bg: #1a1a2e;
    --surface: #16213e;
    --border: #0f3460;
    --text: #e0e0e0;
    --text-dim: #8892b0;
    --accent: #64ffda;
    --error: #ff6b6b;
    --warn: #ffd93d;
    --info: #4ecdc4;
    --tx: #38bdf8;
    --rx: #a78bfa;
    --highlight: #ffd93d;
    --highlight-bg: rgba(255, 217, 61, 0.15);
    --line-hover: rgba(100, 255, 218, 0.05);
    --toolbar-bg: #0d1117;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: 'Cascadia Code', 'Fira Code', 'SF Mono', 'Consolas', monospace;
    background: var(--bg);
    color: var(--text);
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

/* Toolbar */
.toolbar {
    background: var(--toolbar-bg);
    border-bottom: 1px solid var(--border);
    padding: 8px 16px;
    display: flex;
    align-items: center;
    gap: 12px;
    flex-shrink: 0;
    flex-wrap: wrap;
}
.toolbar .title {
    font-size: 0.85rem;
    color: var(--accent);
    font-weight: 600;
    white-space: nowrap;
}
.toolbar .stats {
    font-size: 0.75rem;
    color: var(--text-dim);
    white-space: nowrap;
}
.toolbar .spacer { flex: 1; }

/* Search box */
.search-box {
    display: flex;
    align-items: center;
    gap: 6px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 4px 10px;
    min-width: 280px;
}
.search-box:focus-within {
    border-color: var(--accent);
    box-shadow: 0 0 0 2px rgba(100, 255, 218, 0.1);
}
.search-box input {
    background: none;
    border: none;
    color: var(--text);
    font-family: inherit;
    font-size: 0.85rem;
    outline: none;
    flex: 1;
    min-width: 120px;
}
.search-box input::placeholder {
    color: var(--text-dim);
    opacity: 0.5;
}
.search-box .icon {
    color: var(--text-dim);
    font-size: 0.85rem;
}
.search-box .count {
    font-size: 0.7rem;
    color: var(--text-dim);
    min-width: 40px;
    text-align: right;
}
.search-box .btn-clear {
    background: none;
    border: none;
    color: var(--text-dim);
    cursor: pointer;
    font-size: 0.9rem;
    padding: 0 4px;
    display: none;
}
.search-box .btn-clear.visible { display: block; }
.search-box .btn-clear:hover { color: var(--error); }

/* Filter chips */
.filter-chips {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
}
.chip {
    font-size: 0.7rem;
    padding: 2px 8px;
    border-radius: 10px;
    cursor: pointer;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text-dim);
    transition: all 0.15s;
    white-space: nowrap;
}
.chip:hover { border-color: var(--accent); color: var(--text); }
.chip.active { background: var(--accent); color: var(--bg); border-color: var(--accent); font-weight: 600; }
.chip.error { border-color: var(--error); color: var(--error); }
.chip.error.active { background: var(--error); color: var(--bg); }
.chip.warn { border-color: var(--warn); color: var(--warn); }
.chip.warn.active { background: var(--warn); color: var(--bg); }

/* Log container */
.log-container {
    flex: 1;
    overflow-y: auto;
    overflow-x: auto;
    font-size: 0.8rem;
    line-height: 1.6;
    counter-reset: line;
}
.log-container::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}
.log-container::-webkit-scrollbar-track { background: var(--bg); }
.log-container::-webkit-scrollbar-thumb {
    background: var(--border);
    border-radius: 4px;
}
.log-container::-webkit-scrollbar-thumb:hover { background: var(--text-dim); }

/* Log lines */
.log-line {
    display: flex;
    padding: 1px 0;
    white-space: pre;
    counter-increment: line;
    transition: background 0.1s;
}
.log-line:hover { background: var(--line-hover); }
.log-line.hidden { display: none; }
.log-line.match { background: var(--highlight-bg); }

.line-num {
    color: var(--text-dim);
    opacity: 0.4;
    min-width: 60px;
    text-align: right;
    padding-right: 12px;
    user-select: none;
    flex-shrink: 0;
    font-size: 0.75rem;
}
.line-content {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* Syntax highlighting */
.hl-error { color: var(--error); font-weight: 600; }
.hl-warn { color: var(--warn); }
.hl-info { color: var(--info); }
.hl-tx { color: var(--tx); }
.hl-rx { color: var(--rx); }
.hl-time { color: var(--text-dim); }
.hl-module { color: #c084fc; }
.hl-keyword { background: rgba(255, 217, 61, 0.2); border-radius: 2px; padding: 0 2px; }

/* Status bar */
.statusbar {
    background: var(--toolbar-bg);
    border-top: 1px solid var(--border);
    padding: 4px 16px;
    font-size: 0.7rem;
    color: var(--text-dim);
    display: flex;
    gap: 16px;
    flex-shrink: 0;
}

/* Empty state */
.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 200px;
    color: var(--text-dim);
    gap: 8px;
}
.empty-state .emoji { font-size: 2rem; }
</style>
</head>
<body>

<div class="toolbar">
    <span class="title">📋 {title}</span>
    <span class="stats" id="fileStats"></span>
    <span class="spacer"></span>
    <div class="filter-chips" id="filterChips">
        <span class="chip active" data-filter="all">全部</span>
        <span class="chip error" data-filter="ERROR">ERROR</span>
        <span class="chip warn" data-filter="WARN">WARN</span>
        <span class="chip" data-filter="INFO">INFO</span>
        <span class="chip" data-filter="TX">TX</span>
        <span class="chip" data-filter="RX">RX</span>
    </div>
    <div class="search-box">
        <span class="icon">🔍</span>
        <input type="text" id="searchInput" placeholder="输入关键词筛选（空格分隔多个关键词）..." autofocus>
        <span class="count" id="matchCount"></span>
        <button class="btn-clear" id="btnClear" title="清除">✕</button>
    </div>
</div>

<div class="log-container" id="logContainer">
    <div class="empty-state">
        <span class="emoji">📂</span>
        <span>正在加载日志...</span>
    </div>
</div>

<div class="statusbar">
    <span id="statusTotal">总行数: 0</span>
    <span id="statusVisible">可见: 0</span>
    <span id="statusFilter">筛选: 无</span>
</div>

<script>
// ===== Data =====
const LOG_LINES = {log_lines_json};

// ===== State =====
let activeFilter = 'all';
let searchTerms = [];

// ===== Init =====
function init() {{
    const container = document.getElementById('logContainer');
    container.innerHTML = '';

    if (LOG_LINES.length === 0) {{
        container.innerHTML = '<div class="empty-state"><span class="emoji">📭</span><span>日志为空</span></div>';
        return;
    }}

    LOG_LINES.forEach((line, idx) => {{
        const div = document.createElement('div');
        div.className = 'log-line';
        div.dataset.index = idx;
        div.dataset.level = line.level || '';
        div.dataset.text = line.text || '';

        // Line number
        const numSpan = document.createElement('span');
        numSpan.className = 'line-num';
        numSpan.textContent = line.num || (idx + 1);
        div.appendChild(numSpan);

        // Content with highlighting
        const contentSpan = document.createElement('span');
        contentSpan.className = 'line-content';
        contentSpan.innerHTML = highlightLine(line.text || '', line.level || '');
        div.appendChild(contentSpan);

        container.appendChild(div);
    }});

    updateStats();
    applyAllFilters();
}}

function highlightLine(text, level) {{
    // Escape HTML
    let html = escapeHtml(text);

    // Level-based coloring
    if (level === 'ERROR') {{
        html = '<span class="hl-error">' + html + '</span>';
    }} else if (level === 'WARN') {{
        html = '<span class="hl-warn">' + html + '</span>';
    }}

    // Highlight timestamps
    html = html.replace(/(\[\d{{4}}-\d{{2}}-\d{{2}}\s+\d{{2}}:\d{{2}}:\d{{2}}\.\d{{3}}\])/g,
        '<span class="hl-time">$1</span>');

    // Highlight TX/RX
    html = html.replace(/\[TX\]/g, '<span class="hl-tx">[TX]</span>');
    html = html.replace(/\[RX\]/g, '<span class="hl-rx">[RX]</span>');

    // Highlight module names
    html = html.replace(/\[(\w+)\]/g, function(match, mod) {{
        if (['TX', 'RX', 'INFO', 'WARN', 'ERROR'].includes(mod)) return match;
        return '<span class="hl-module">[' + mod + ']</span>';
    }});

    return html;
}}

function escapeHtml(text) {{
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}}

// ===== Filtering =====
function applyAllFilters() {{
    const lines = document.querySelectorAll('.log-line');
    let visibleCount = 0;

    lines.forEach(line => {{
        const level = line.dataset.level;
        const text = line.dataset.text.toLowerCase();

        // Level filter
        let levelMatch = activeFilter === 'all' || level === activeFilter;

        // Search filter
        let searchMatch = true;
        if (searchTerms.length > 0) {{
            searchMatch = searchTerms.every(term => text.includes(term.toLowerCase()));
        }}

        if (levelMatch && searchMatch) {{
            line.classList.remove('hidden');
            visibleCount++;

            // Highlight search keywords
            if (searchTerms.length > 0) {{
                line.classList.add('match');
                const contentSpan = line.querySelector('.line-content');
                let html = contentSpan.textContent;
                html = escapeHtml(html);
                searchTerms.forEach(term => {{
                    const regex = new RegExp('(' + escapeRegex(term) + ')', 'gi');
                    html = html.replace(regex, '<span class="hl-keyword">$1</span>');
                }});
                contentSpan.innerHTML = html;
            }} else {{
                line.classList.remove('match');
            }}
        }} else {{
            line.classList.add('hidden');
        }}
    }});

    updateStats(visibleCount);
}}

function escapeRegex(str) {{
    return str.replace(/[.*+?^${{}}()|[\]\\]/g, '\\$&');
}}

function updateStats(visibleCount) {{
    const total = LOG_LINES.length;
    document.getElementById('fileStats').textContent =
        '共 ' + total + ' 行';
    document.getElementById('statusTotal').textContent =
        '总行数: ' + total;
    document.getElementById('statusVisible').textContent =
        '可见: ' + (visibleCount !== undefined ? visibleCount : total);
}}

// ===== Event Handlers =====

// Filter chips
document.getElementById('filterChips').addEventListener('click', function(e) {{
    const chip = e.target.closest('.chip');
    if (!chip) return;

    document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
    activeFilter = chip.dataset.filter;

    document.getElementById('statusFilter').textContent =
        '筛选: ' + (activeFilter === 'all' ? '全部' : activeFilter);

    applyAllFilters();
}});

// Search input
const searchInput = document.getElementById('searchInput');
const btnClear = document.getElementById('btnClear');
const matchCount = document.getElementById('matchCount');

searchInput.addEventListener('input', function() {{
    const val = this.value.trim();
    searchTerms = val ? val.split(/\s+/) : [];

    if (searchTerms.length > 0) {{
        btnClear.classList.add('visible');
        matchCount.textContent = searchTerms.length + '词';
        document.getElementById('statusFilter').textContent =
            '搜索: ' + searchTerms.join(' + ');
    }} else {{
        btnClear.classList.remove('visible');
        matchCount.textContent = '';
        document.getElementById('statusFilter').textContent =
            '筛选: ' + (activeFilter === 'all' ? '全部' : activeFilter);
    }}

    applyAllFilters();
}});

btnClear.addEventListener('click', function() {{
    searchInput.value = '';
    searchTerms = [];
    btnClear.classList.remove('visible');
    matchCount.textContent = '';
    applyAllFilters();
}});

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {{
    // Ctrl+F / Cmd+F -> focus search
    if ((e.ctrlKey || e.metaKey) && e.key === 'f') {{
        e.preventDefault();
        searchInput.focus();
        searchInput.select();
    }}
    // Escape -> clear search
    if (e.key === 'Escape') {{
        searchInput.value = '';
        searchTerms = [];
        btnClear.classList.remove('visible');
        matchCount.textContent = '';
        applyAllFilters();
        searchInput.blur();
    }}
}});

// Init on load
init();
</script>
</body>
</html>"""


def parse_log_file(filepath: str) -> list:
    """解析日志文件，返回行列表"""
    lines = []
    text = Path(filepath).read_text(encoding="utf-8", errors="replace")

    for i, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue

        # 检测日志级别
        level = ""
        if "ERROR" in line or "[Ee]rror" in line:
            level = "ERROR"
        elif "WARN" in line or "WARNING" in line:
            level = "WARN"
        elif "[TX]" in line:
            level = "TX"
        elif "[RX]" in line:
            level = "RX"
        elif "INFO" in line:
            level = "INFO"

        lines.append({
            "num": i,
            "text": line,
            "level": level,
        })

    return lines


def generate_viewer(logfile: str, output_html: str) -> str:
    """生成交互式日志查看器 HTML"""
    log_lines = parse_log_file(logfile)
    title = Path(logfile).name

    html = HTML_TEMPLATE.replace("{title}", title)
    html = html.replace("{log_lines_json}", json.dumps(log_lines, ensure_ascii=False))

    Path(output_html).write_text(html, encoding="utf-8")
    return output_html


def main():
    if len(sys.argv) < 2:
        print("交互式日志查看器 - Notepad++ 风格实时筛选")
        print("用法: python log_viewer.py <logfile> [output_html]")
        print()
        print("功能:")
        print("  🔍 实时关键词搜索（空格分隔多个关键词）")
        print("  🏷️  按日志级别筛选（ERROR/WARN/INFO/TX/RX）")
        print("  🎨 语法高亮（时间戳/模块/方向/级别）")
        print("  ⌨️  快捷键: Ctrl+F 搜索, Esc 清除")
        sys.exit(1)

    logfile = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) >= 3 else f"{Path(logfile).stem}_viewer.html"

    path = generate_viewer(logfile, output)
    print(f"✅ 日志查看器已生成!")
    print(f"  输入: {logfile} ({len(parse_log_file(logfile))} 行)")
    print(f"  输出: {path}")
    print(f"")
    print(f"  🔍 在浏览器中打开即可使用:")
    print(f"     - 输入关键词实时筛选")
    print(f"     - 点击 ERROR/WARN/INFO/TX/RX 按级别过滤")
    print(f"     - Ctrl+F 聚焦搜索框, Esc 清除")


if __name__ == "__main__":
    main()
