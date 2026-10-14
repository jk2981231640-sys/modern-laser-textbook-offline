#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下载《现代激光原理与技术》数字教材中的视频（本仓库未收录的 191 个 mp4，约 5.1 GB）。

原理
----
数字教材（Keledge DCD 富内容教材）的全部资源元素都记录在内容清单接口返回的 JSON 里：

    GET https://www.bhpressshuzi.cn:50012/bhcbs/Content/Detail?Id=1547155808880427008

其中 `Data.TextBook.BookResourceInfos` 是数组（共 2467 条），筛出
`PrefaceType == "video"`（或 `Type == 1`）即得 191 条视频记录，每条含：

    FileName     人类可读文件名，如 "清模器.mp4"
    FileUrl      直接可下载的静态地址，如
                 https://www.bhpressshuzi.cn/bhcbs/files/Resource/f3003836-2c78-a048-63f1-4ff6cff7b068/Material/video/<guid>.mp4
    Cover        封面图 png
    SectionTitle / Order   它在书中的位置

这些 FileUrl 是**免登录的静态文件**（实测 HTTP 200、Content-Type: video/mp4、Accept-Ranges: bytes），
普通 HTTP 客户端即可下载，不需要登录，也不需要解析播放器。

注意
----
该站点只支持 **TLS 1.2**。部分环境下 Python 的 requests/urllib 直连会
`ssl.SSLV3_ALERT_HANDSHAKE_FAILURE` 握手失败，因此本脚本默认调用系统 `curl`
（Windows 自带 curl.exe），也可以用 `--client python` 走 urllib + 显式 TLS1.2 上下文。

用法
----
    python scripts/download_videos.py                  # 下载到 ./Material/video/
    python scripts/download_videos.py --jobs 4         # 并发 4
    python scripts/download_videos.py --dry-run        # 只列出，不下载
    python scripts/download_videos.py --out D:\videos  # 自定义目录

结束后会生成 video_manifest.csv（章节 / 原始文件名 / URL / 本地路径 / 大小），
按它就能把视频对回书里（章节 HTML 中引用的是 Material/video/<guid>.mp4）。
"""

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_DETAIL = os.path.join(ROOT, "metadata", "detail.json")
DEFAULT_OUT = os.path.join(ROOT, "Material", "video")
CONTENT_DETAIL_API = (
    "https://www.bhpressshuzi.cn:50012/bhcbs/Content/Detail?Id=1547155808880427008"
)

LOCK = threading.Lock()


def find_curl():
    for name in ("curl.exe", "curl"):
        p = shutil.which(name)
        if p:
            return p
    return None


CURL = find_curl()


def log(*a):
    with LOCK:
        print(*a, flush=True)


def run_curl(args, timeout=3600):
    if not CURL:
        raise RuntimeError("未找到 curl，请安装 curl 或改用 --client python")
    return subprocess.run([CURL, "-sSL", "--fail", "--retry", "3", "--retry-delay", "2"] + args,
                          capture_output=True, text=True, timeout=timeout)


def load_detail(path, allow_download=True):
    """读取 metadata/detail.json；没有就用 curl 现场拉一份。"""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    if not allow_download:
        raise SystemExit("缺少 %s，请先下载内容清单接口的 JSON" % path)
    log("[i] 本地没有 detail.json，正在从内容清单接口获取……")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    r = run_curl(["-o", path, CONTENT_DETAIL_API])
    if r.returncode != 0:
        raise SystemExit("下载内容清单失败：%s" % r.stderr[:300])
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def pick_videos(detail):
    infos = detail["Data"]["TextBook"]["BookResourceInfos"]
    vids = [x for x in infos
            if (x.get("PrefaceType") == "video" or x.get("Type") == 1) and x.get("FileUrl")]
    vids.sort(key=lambda x: (x.get("Order") or 0))
    return vids


def curl_size(url):
    """HEAD 拿 Content-Length（拿不到返回 -1）。"""
    r = subprocess.run([CURL, "-sSIL", "--max-time", "30", url],
                       capture_output=True, text=True)
    size = -1
    for line in r.stdout.splitlines():
        if line.lower().startswith("content-length:"):
            try:
                size = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
    return size


def download_one(item, outdir, client, index, total):
    url = item["FileUrl"]
    name = os.path.basename(url.split("?")[0])
    title = (item.get("FileName") or name).strip()
    final = os.path.join(outdir, name)
    tmp = final + ".part"
    want = None

    if os.path.exists(final) and os.path.getsize(final) > 0:
        if client == "curl":
            want = curl_size(url)
        if want > 0 and os.path.getsize(final) == want:
            log("[%3d/%d] 跳过（已存在） %s" % (index, total, title))
            return {"ok": True, "skipped": True, "path": final, "size": os.path.getsize(final)}
        if want <= 0 and os.path.getsize(final) > 0:
            log("[%3d/%d] 跳过（已存在） %s" % (index, total, title))
            return {"ok": True, "skipped": True, "path": final, "size": os.path.getsize(final)}

    log("[%3d/%d] 下载 %s" % (index, total, title))
    try:
        if client == "curl":
            r = run_curl(["-C", "-", "-o", tmp, url])          # 支持断点续传
            if r.returncode != 0:
                return {"ok": False, "err": r.stderr.strip()[:200], "path": final}
        else:
            import ssl
            import urllib.request
            ctx = ssl.create_default_context()
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ctx.maximum_version = ssl.TLSVersion.TLSv1_2
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            if os.path.exists(tmp):
                req.add_header("Range", "bytes=%d-" % os.path.getsize(tmp))
            with urllib.request.urlopen(req, context=ctx, timeout=120) as resp, open(tmp, "ab") as fh:
                shutil.copyfileobj(resp, fh, 1 << 20)
        os.replace(tmp, final)
        size = os.path.getsize(final)
        log("         ✓ %.1f MB  %s" % (size / 1048576.0, name))
        return {"ok": True, "skipped": False, "path": final, "size": size}
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": False, "err": str(exc)[:200], "path": final}


def main():
    ap = argparse.ArgumentParser(description="下载教材中的 191 个视频")
    ap.add_argument("--detail", default=DEFAULT_DETAIL, help="内容清单 JSON 路径")
    ap.add_argument("--out", default=DEFAULT_OUT, help="输出目录（默认 Material/video/）")
    ap.add_argument("--jobs", type=int, default=3, help="并发数（默认 3，别开太大，对方是出版社服务器）")
    ap.add_argument("--client", choices=["curl", "python"], default="curl", help="下载客户端")
    ap.add_argument("--dry-run", action="store_true", help="只列出，不下载")
    args = ap.parse_args()

    if args.client == "curl" and not CURL:
        log("[!] 没找到 curl，自动改用 python 客户端")
        args.client = "python"

    detail = load_detail(args.detail)
    vids = pick_videos(detail)
    log("[i] 共找到 %d 个视频，输出目录：%s" % (len(vids), args.out))
    if not vids:
        return 1
    if args.dry_run:
        for i, v in enumerate(vids, 1):
            log("[%3d/%d] %-40s %s" % (i, len(vids), (v.get("FileName") or "")[:38], v["FileUrl"]))
        return 0

    os.makedirs(args.out, exist_ok=True)
    from concurrent.futures import ThreadPoolExecutor, as_completed
    results = []
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futs = {pool.submit(download_one, v, args.out, args.client, i, len(vids)): v
                for i, v in enumerate(vids, 1)}
        for fut in as_completed(futs):
            results.append((futs[fut], fut.result()))

    ok = sum(1 for _, r in results if r.get("ok"))
    total_bytes = sum(r.get("size", 0) for _, r in results if r.get("ok"))
    log("\n[i] 完成：%d/%d 成功，共 %.2f GB" % (ok, len(vids), total_bytes / 1073741824.0))

    csv_path = os.path.join(ROOT, "video_manifest.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(["章节", "原始文件名", "URL", "本地文件", "字节数"])
        for item, res in sorted(results, key=lambda x: (x[0].get("Order") or 0)):
            wr.writerow([item.get("SectionTitle", ""), item.get("FileName", ""),
                         item["FileUrl"], os.path.basename(res.get("path", "")), res.get("size", "")])
    log("[i] 清单已写出：%s" % csv_path)
    bad = [v.get("FileName") for v, r in results if not r.get("ok")]
    if bad:
        log("[!] 失败 %d 个：%s" % (len(bad), ", ".join(bad[:10])))
        log("    重跑本脚本会自动续传/跳过已完成文件。")
    return 0 if ok == len(vids) else 2


if __name__ == "__main__":
    sys.exit(main())
