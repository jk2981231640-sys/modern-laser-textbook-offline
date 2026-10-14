# 贡献指南

感谢你愿意改进这个离线归档项目。本仓库的定位是"**让合法使用者能离线、可检索地读这本书**"，
因此欢迎的贡献集中在**保真、可用、可复现**三件事上。

## 一、欢迎的贡献

| 类型 | 说明 |
| --- | --- |
| 勘误 | 离线版与平台在线版不一致（漏字、丢图、公式渲染错、章节顺序错） |
| 补齐缺失素材 | README「已知问题」里列的 404 图片，找到同图源替换 |
| 脚本改进 | `scripts/` 下的下载/重排/重建 PDF 脚本的健壮性、跨平台支持 |
| 文档改进 | README / DISCLAIMER 的表述、可复现步骤、平台 API 变化的更新 |
| 视频方案 | 在不违反 DISCLAIMER 的前提下，把视频转成小体积的预览/索引方案 |

## 二、不接受的贡献

- 任何破解、绕过登录/付费/权限控制的代码或教程；
- 把本仓库内容再分发出去的"镜像""合集""打包下载"；
- 商业用途相关的改造（付费讲义、培训教材等）；
- 去掉版权信息、把 PDF 换成自己署名的版本。

## 三、提交方式

1. Fork 本仓库，新建分支：`git checkout -b fix/xxx`；
2. 只改必要文件，**不要提交整个 780 MB 的 `Material/`**（除非你确实在补缺失素材，
   且请在 PR 描述里说明新增的具体文件与来源）；
3. 大文件（>50 MB）一律走 **Git LFS** 或提 Release，不要直接 `git add`；
4. 提交信息用 `feat: / fix: / docs: / chore:` 前缀，中文英文都可以；
5. 发起 Pull Request，描述里写清楚：**改了什么、怎么验证的**。

## 四、必须遵守的技术约定（都是踩过的坑）

这些是本项目在真实抓取过程中验证过的规则，改脚本时请保持：

1. **只支持 TLS 1.2**：Python 的 `requests`/`urllib` 在该站点上可能直接
   `ssl.SSLV3_ALERT_HANDSHAKE_FAILURE` 握手失败；默认走系统 `curl`
   （`curl.exe -sSL --fail --retry 3`），必要时给 `ssl` 上下文显式锁到 `TLSv1_2`。
2. **中文路径必须做百分号编码**：章节 HTML 的文件名是中文
   （`第1章_绪论-99879526-....html`），拼 URL 前用 `urllib.parse.quote()`。
3. **不要试图一次打印整本书**：完整的 `index.html` 约 66 万像素高（≈858 页 A4），
   一次性 `printToPDF` 会把浏览器内存顶到 8 GB 以上且长时间不返回。
   正确做法是**逐章打印再合并**（每章 1.7–12 秒），`scripts/rebuild_pdf.py` 已经是这么做的。
4. **临时脚本不要用标准库同名**：曾把脚本存成 `struct.py` 导致
   `ImportError: cannot import name 'iter_unpack' from 'struct'`。
   临时文件统一放仓库外的 `_scripts/` 之类的目录。
5. **控制台编码**：Windows 控制台默认 GBK，Python 脚本开头加
   `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`，
   写文件用**无 BOM 的 UTF-8**（`newline="\n"`）。
6. **请求要克制**：出版社服务器不是 CDN，并发别超过 3–4，失败要有退避与续传。

## 五、合并前的验收清单

维护者合并 PR 前会跑一遍以下检查（也请你在 PR 里贴出自己的结果）：

```bash
# 1. 正文完整性：这几个词必须能命中（它们是用户实际看到的那一页）
grep -c "悬镜中的光力学" index.html      # ≥ 1
grep -c "腔光力学"       index.html      # ≥ 3
grep -c "Cavityoptomechanics" index.html # ≥ 1

# 2. 素材是否断链（应输出 0 或只输出「已知问题」里列出的那几个）
python scripts/check_assets.py          # 若有
```

PDF 另行抽查末尾若干页（`悬镜中的光力学` 位于第 9 章，对应 PDF 后段）。

## 六、行为准则

友善、就事论事。不要在本仓库讨论如何获取未购买的内容。
