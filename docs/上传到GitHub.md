# 把这份离线教材上传到 GitHub：完整方案与命令

> 前提：你已经在本目录里拿到 `git init` 之后的仓库（本文所有命令在
> `现代激光原理与技术_离线版/` 目录下执行）。

---

## 0. 先认清三个硬约束

| 约束 | 数值 | 影响 |
| --- | --- | --- |
| 单个文件硬上限 | **100 MB**（超过直接拒绝推送） | 本项目的 `现代激光原理与技术.pdf` 有 **413.4 MB**，**绝对不能**直接 `git add` |
| 单次推送建议上限 | 约 2 GB / 仓库建议 < 5 GB | 全量 780 MB 推得动，但很慢，且容易被判定为超大仓库 |
| 版权风险 | GitHub 会受理 DMCA | 这是**他人享有著作权的教材**，公开仓库有被投诉下架的风险 |

因此**推荐指数**从高到低是：

1. **只推"工程部分"**（脚本 + README + 元数据 + 目录清单）：约 1 MB，最安全、最快；
2. **推文档 + 用 Release / LFS 放 PDF**；
3. **推完整 780 MB**：可行，但请把仓库设为 **Private**，并接受被投诉的可能；
4. **推 5.1 GB 视频**：不建议（见 `scripts/download_videos.py` 让使用者自己下）。

---

## 1. 建仓库

在 GitHub 网页端 **New repository**：

- Repository name：`laser-principle-textbook-offline`（或你喜欢的名字）
- Visibility：**Private**（强烈建议；确认无碍后再改 Public）
- **不要**勾选 "Add a README file"（本地已经有了，避免冲突）

---

## 2. 配置本地身份与远程

```bash
cd "现代激光原理与技术_离线版"

git config user.name  "你的名字"
git config user.email "你的邮箱@example.com"

# 中文文件名在 git status 里不要被转义成 \xxx
git config core.quotepath false
# 教材 HTML 用 LF，避免 Windows 上被改成 CRLF 造成全库 diff
git config core.autocrlf false

# 关联远程（把 <you> 换成你的 GitHub 用户名）
git remote add origin https://github.com/<you>/laser-principle-textbook-offline.git
```

首次推送需要凭据：推荐用 **Personal Access Token**（Settings → Developer settings →
Personal access tokens → Fine-grained token，勾 `Contents: Read and write`），
弹窗里用户名填 GitHub 用户名、密码填 token。也可用 CLI 登录：`gh auth login`。

---

## 3. 方案 A（推荐）：只推工程部分

仓库里已经准备好 `.gitignore`，它会**自动排除 413 MB 的 PDF**。

```bash
git status --short | head -50      # 确认 现代激光原理与技术.pdf 不在列表里
git add .
git commit -m "docs: 教材离线归档工程部分（脚本/说明/元数据/章节清单）"
git push -u origin main
```

如果连 `Material/`（343 MB）也不想推，在 `.gitignore` 里再加一行 `Material/` 即可。

---

## 4. 方案 B：用 Git LFS 托管 PDF

```bash
git lfs install
# 打开 .gitattributes 里预置的 LFS 规则（把 *.pdf 那几行的注释去掉）
git add .gitattributes
git lfs track "现代激光原理与技术.pdf"
git add "现代激光原理与技术.pdf"
git commit -m "chore: 用 LFS 托管离线版 PDF"
git push -u origin main
```

> 免费账号的 LFS 配额是 **1 GB 存储 / 1 GB 月流量**，413 MB 的 PDF 会占掉大半，
> 别人克隆几次就可能超限。真要走这条路，建议压缩 PDF（见下）。

**减小 PDF 体积的可行方向**：把 343 MB 的 PNG/JPG 素材批量转成 WebP 或降低分辨率后
重新打印；或只保留"正文 + 公式"的轻量版 PDF，图片走网页版。
（注意：矢量公式是 SVG，转档时别把它光栅化掉。）

---

## 5. 方案 C：完整推送（Private 仓库）

```bash
# 确认没有超过 100 MB 的单文件
git ls-files -z | xargs -0 -n1 du -b | awk '$1 > 100000000 {print $1/1048576 " MB  " $2}'
```

输出应为空。若有，先处理掉再提交（把该文件加进 `.gitignore` 或走 LFS）。
然后：

```bash
git add .
git commit -m "feat: 现代激光原理与技术 数字教材离线归档（58 章 + 素材 + PDF）"
git push -u origin main
```

780 MB 的首次推送通常要几分钟到十几分钟，中途断了可以直接重跑 `git push`。

**如果已经被拒过一次**（历史里留下了大文件）：

```bash
# 需要 git-filter-repo（pip install git-filter-repo）
git filter-repo --path "现代激光原理与技术.pdf" --invert-paths
git push --force-with-lease -u origin main
```

---

## 6. 用 Release 挂大文件（最省事的分享方式）

GitHub Release 的单个附件上限是 **2 GB**，比普通文件宽松得多，而且不占仓库体积：

```bash
# 用 gh CLI（推荐）
gh release create v1.0.0 \
  "现代激光原理与技术.pdf" \
  --title "现代激光原理与技术 · 离线版 v1.0.0" \
  --notes "58 章完整离线 HTML + PDF（858 页 / 413 MB）。请先阅读 DISCLAIMER.md，仅供个人学习使用。"
```

网页端也可以：仓库 → **Releases** → **Draft a new release** → 拖入 PDF。
**注意**：Release 附件同样是公开可下载的，版权风险与推仓库一样，建议 Release 与仓库保持一致的可见性。

---

## 7. 常见报错与处理

| 报错 | 原因 | 处理 |
| --- | --- | --- |
| `remote: error: File ... is 413.44 MB; this exceeds GitHub's file size limit of 100.00 MB` | 大文件被 `git add` 了 | `git rm --cached` 该文件 → 加进 `.gitignore` → `git commit --amend`；若已进历史，用 `git filter-repo` 清理 |
| `fatal: Authentication failed for 'https://github.com/...'` | 用了账号密码 | 改用 Personal Access Token，或 `gh auth login` |
| `Updates were rejected because the remote contains work that you do not have locally` | 网页端建仓时勾了 README | `git pull --rebase origin main` 后再 `git push` |
| `RPC failed; curl 92 HTTP/2 stream ...` / `fatal: the remote end hung up unexpectedly` | 单次推送太大 | `git config http.postBuffer 524288000`；或分批推（先推小文件，再单独推大文件） |
| 中文文件名显示成 `\346\226\207...` | quotepath | `git config core.quotepath false` |
| `git status` 显示所有文件都被改动 | CRLF 转换 | `git config core.autocrlf false` 后 `git checkout -- .` |

---

## 8. 强烈建议：开源前先做三件事

1. **确认你有权这样分享**——本仓库内容著作权属于出版社，
   公开托管在未经许可的情况下存在被投诉下架（DMCA）的风险；**先设 Private 最稳妥**。
2. **不要提交凭据**：仓库里不应出现任何账号、Cookie、token
   （`git grep -iE "cookie|token|passwd|secret"` 自查一遍）。
3. **README 顶部保留 `DISCLAIMER.md` 的链接**，让每个下载者都能看到使用边界。

---

## 9. 备选托管方案（如果 GitHub 在你那儿不方便）

| 方案 | 适合 | 备注 |
| --- | --- | --- |
| **GitLab** | 想自建/私有 | 免费额度更宽松，支持 LFS |
| **自建 Gitea / 局域网 Git** | 只在实验室内部共享 | 无版权外溢风险，最适合这类材料 |
| **对象存储（OSS/S3）+ 私有链接** | 只想给自己多设备用 | 成本低，可控 |
| **移动硬盘 / NAS** | 纯离线 | 零风险，最推荐用来放 780 MB 的完整副本 |
