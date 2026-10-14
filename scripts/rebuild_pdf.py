#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 index.html 重新生成《现代激光原理与技术.pdf》（约 858 页 / 413 MB / 58 条章节书签）。

为什么要"逐章打印再合并"，而不是一次打印整本书
------------------------------------------------
完整的 index.html 拼起来约 66 万像素高（≈858 页 A4）。一次性交给浏览器打印时，
Chromium/Edge 会试图把整篇光栅化，内存从几百 MB 窜到 8 GB 以上并长时间无响应
（实测：Edge 44 个进程 8.0 GB 内存、CPU 只有 2.9%、5 分钟不返回）。
逐章打印则每章只需 1.7–12 秒，还能顺便拿到 58 条章节书签。

依赖
----
- 本地无头浏览器：Microsoft Edge 或 Google Chrome（脚本会自动找常见安装路径）
- pypdf（>= 3）：
      python -m pip install pypdf
  国内网络可加代理：python -m pip install --proxy http://127.0.0.1:7890 pypdf

用法
----
    python scripts/rebuild_pdf.py                     # 生成到仓库根目录
    python scripts/rebuild_pdf.py --out book.pdf      # 指定输出
    python scripts/rebuild_pdf.py --keep-temp         # 保留 _cNN.html 中间文件
    python scripts/rebuild_pdf.py --only 1-5          # 只做前 5 章（调试用）
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
INDEX = os.path.join(ROOT, "index.html")
DEFAULT_OUT = os.path.join(ROOT, "现代激光原理与技术.pdf")

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/microsoft-edge",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
]

PRINT_CSS = """
<style id="rebuild-pdf-style">
  /* 刻意不覆盖 index.html 自带的 @page{size:A4; margin:16mm 14mm}，
     以保持与出版社网页版一致的版心与分页；这里只补几条排版规则。 */
  @media print {
    .toolbar, .float-btn { display: none !important; }
    section.chapter { break-before: page; page-break-before: always; }
    h1, h2, h3 { break-after: avoid; page-break-after: avoid; }
    img, svg, table, figure { break-inside: avoid; page-break-inside: avoid; }
  }
</style>
"""


def log(*a):
    print(*a, flush=True)


def find_browser(explicit=None):
    if explicit:
        if os.path.exists(explicit):
            return explicit
        raise SystemExit("指定的浏览器不存在：%s" % explicit)
    for p in BROWSERS:
        if os.path.exists(p):
            return p
    for name in ("msedge", "google-chrome", "chromium", "chrome"):
        p = shutil.which(name)
        if p:
            return p
    raise SystemExit("没找到 Edge/Chrome，请用 --browser 指定可执行文件路径")


def load_index():
    if not os.path.exists(INDEX):
        raise SystemExit("找不到 %s" % INDEX)
    with open(INDEX, encoding="utf-8") as f:
        return f.read()


def split_chapters(html):
    """按 <section class="chapter" id="chNN" ...> 切成 [(id, 完整片段), ...]"""
    marks = list(re.finditer(r'<section class="chapter" id="(ch\d+)"[^>]*>', html))
    if not marks:
        raise SystemExit("index.html 里没找到 <section class=\"chapter\">，格式变了吗？")
    head_end = html.find("</head>")
    head = html[:head_end + len("</head>")].replace("</head>", PRINT_CSS + "</head>")
    if "<style id=\"rebuild-pdf-style\">" not in head:      # 头部没有 </head> 时兜底
        head = PRINT_CSS + html[:head_end]
    chapters = []
    for i, m in enumerate(marks):
        start = m.start()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(html)
        block = html[start:end]
        # 最后一块可能拖着 </main></body></html>，去掉
        block = re.sub(r"</main>\s*</body>\s*</html>\s*$", "", block)
        chapters.append((m.group(1), block))
    return head, chapters


def chapter_titles(html):
    """从侧边栏导航取章节标题： <a href="#ch12"><span class="tno">12</span> 标题</a>"""
    titles = {}
    for m in re.finditer(r'<a href="#(ch\d+)">\s*<span class="tno">\s*\d+\s*</span>\s*([^<]*)</a>', html):
        t = re.sub(r"\s+", " ", m.group(2)).strip()
        if t:
            titles[m.group(1)] = t
    return titles


def print_one(browser, src_html, out_pdf, timeout=180):
    """用无头浏览器把一个 HTML 打印成 PDF。"""
    profile = tempfile.mkdtemp(prefix="pdfprof_")
    url = "file:///" + src_html.replace("\\", "/").replace(" ", "%20")
    args = [browser, "--headless=new", "--disable-gpu", "--no-first-run",
            "--no-default-browser-check", "--disable-sync", "--disable-extensions",
            "--disable-features=Translate", "--no-pdf-header-footer",
            "--run-all-compositor-stages-before-draw", "--virtual-time-budget=30000",
            "--user-data-dir=%s" % profile,
            "--print-to-pdf=%s" % out_pdf, url]
    t0 = time.time()
    try:
        proc = subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout)
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    dt = time.time() - t0
    if not os.path.exists(out_pdf) or os.path.getsize(out_pdf) == 0:
        raise SystemExit("打印失败（%s），退出码 %s" % (out_pdf, getattr(proc, "returncode", "?")))
    return dt, os.path.getsize(out_pdf)


def main():
    ap = argparse.ArgumentParser(description="从 index.html 重新生成完整 PDF")
    ap.add_argument("--index", default=INDEX)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--browser", default=None, help="Edge/Chrome 可执行文件路径")
    ap.add_argument("--only", default=None, help="只打印某几章，如 1-5 或 1,2,3")
    ap.add_argument("--keep-temp", action="store_true", help="保留 _cNN.html / _cNN.pdf")
    ap.add_argument("--timeout", type=int, default=180, help="每章打印超时（秒）")
    args = ap.parse_args()

    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        raise SystemExit("缺少 pypdf：python -m pip install pypdf\n"
                         "（国内网络：python -m pip install --proxy http://127.0.0.1:7890 pypdf）")

    browser = find_browser(args.browser)
    log("[i] 浏览器：%s" % browser)
    html = load_index()
    head, chapters = split_chapters(html)
    titles = chapter_titles(html)
    log("[i] index.html %.1f MB，切出 %d 章" % (len(html) / 1048576.0, len(chapters)))

    todo = chapters
    if args.only:
        want = set()
        for part in args.only.split(","):
            if "-" in part:
                a, b = part.split("-")
                want.update(range(int(a), int(b) + 1))
            else:
                want.add(int(part))
        todo = [c for i, c in enumerate(chapters, 1) if i in want]
        log("[i] --only 生效：只做 %d 章" % len(todo))

    writer = PdfWriter()
    done, failures = [], []
    for idx, (cid, block) in enumerate(todo, 1):
        num = int(re.sub(r"\D", "", cid) or 0)
        cpath = os.path.join(ROOT, "_%s.html" % cid)
        ppath = os.path.join(ROOT, "_%s.pdf" % cid)
        with open(cpath, "w", encoding="utf-8", newline="\n") as f:
            f.write(head + "\n<body>\n" + block + "\n</body>\n</html>\n")
        try:
            dt, size = print_one(browser, cpath, ppath, timeout=args.timeout)
        except SystemExit as exc:
            failures.append((cid, str(exc)))
            log("    ✗ %s 失败：%s" % (cid, exc))
            continue
        reader = PdfReader(ppath)
        n = len(reader.pages)
        title = titles.get(cid, "第 %d 节" % num)
        writer.add_outline_item("%02d %s" % (num, title), len(writer.pages))
        writer.append(ppath)
        done.append((cid, n, size))
        log("[%2d/%d] %s  %3d 页  %5.1f MB  %4.1fs  %s"
            % (idx, len(todo), cid, n, size / 1048576.0, dt, title))

    if not done:
        raise SystemExit("没有任何一章打印成功")
    out = args.out if os.path.isabs(args.out) else os.path.join(ROOT, args.out)
    with open(out, "wb") as f:
        writer.write(f)

    if not args.keep_temp:
        for cid, _, _ in done:
            for ext in (".html", ".pdf"):
                p = os.path.join(ROOT, "_%s%s" % (cid, ext))
                if os.path.exists(p):
                    os.remove(p)

    total = sum(n for _, n, _ in done)
    log("\n[✓] %s" % out)
    log("    章节 %d 篇 / %d 页 / %.1f MB / %d 条书签"
        % (len(done), total, os.path.getsize(out) / 1048576.0, len(writer.outline)))
    if failures:
        log("[!] 失败 %d 章：%s" % (len(failures), ", ".join(c for c, _ in failures)))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
