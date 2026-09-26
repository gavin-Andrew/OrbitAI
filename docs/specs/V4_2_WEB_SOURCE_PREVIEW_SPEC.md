# OrbitAI V4.2 官方网页来源只读试抓规格

类别：实现规格

状态：官网只读试抓已实现。下文保留 2026-07 的授权与试验边界；2026-09-16 按用户完成 V4.2 的要求，新增独立 `materials/intake.py` 承接三家官网按需预览保存，见 [完整交付范围](V4_2_COMPLETION_SPEC.md)。本文件所述 `website_preview` 命令继续只读，SpaceXAI 正式采集仍搁置。

实现日期：2026-07-27；SpaceXAI Crawl 修订：2026-07-28

关联文件：

- `../../orbitai/materials/web_sources.py`
- `../../orbitai/website_preview.py`
- `../../tests/materials/test_web_sources.py`
- `../decisions/V4_2_SOURCE_COVERAGE_REVIEW.md`

## 1. 目标

为没有公司级官方 RSS 的四家试点组织建立可审计的官网读取能力：

- Anthropic
- Meta AI
- DeepSeek
- SpaceXAI

本阶段只回答三个问题：

1. 能否从官方列表页发现真正的文章链接。
2. 能否从详情页获得标题、发布日期和可供计算机处理的正文。
3. 哪些网站在本地直接请求下失败，需要进入后备抓取方案评估。

## 2. 本轮不做

- 不把网页材料写入 `var/orbitai.db`。
- 不调用 AI，不分类、不摘要、不评分。
- 不创建事件或事件候选。
- 不使用第三方镜像冒充官方来源。
- 不绕过登录、付费墙或明确的访问限制。
- 不把 DeepSeek 更新日志的每个小版本自动当作独立文章。
- Firecrawl 只允许读取 `x.ai/news` 及其白名单文章路径，不作为任意网址抓取器。

## 3. 代码边界

活动实现位于 `orbitai/materials/web_sources.py`，稳定 CLI 包装为 `orbitai/website_preview.py`。

该模块不得导入：

- `orbitai.core.database`
- `orbitai.materials.repository`
- `orbitai.materials.ai_processor`

只读边界由验收测试固定，避免后续在“预览”命令中意外加入数据库或 AI 副作用。

## 4. 四家公司独立规则

| 来源 ID | 列表入口 | 允许域名 | 文章路径 | 正文规则 |
|---|---|---|---|---|
| `anthropic` | `https://www.anthropic.com/news` | `www.anthropic.com`、`anthropic.com` | `/news/{slug}` | 优先 `article`，其次 `main` |
| `meta_ai` | `https://ai.meta.com/blog/` | `ai.meta.com` | `/blog/{slug}` | 优先 `article/main`，再使用标题所在正文容器，最后才回退 `body` |
| `deepseek` | `https://api-docs.deepseek.com/zh-cn/news/` | `api-docs.deepseek.com` | `/news/{slug}` 或 `/zh-cn/news/{slug}` | 优先 Docusaurus `article` 与 `.theme-doc-markdown` |
| `spacexai` | `https://x.ai/news` | `x.ai`、`www.x.ai` | `/news/{slug}` | 优先 `article`，其次 `main` |

发现阶段只接受 HTTPS、白名单域名和白名单文章路径。查询参数与 URL 片段会被移除，防止同一文章产生多个身份。

## 5. 质量门槛

每篇详情页输出以下状态：

- `ready`：标题、日期和最低长度正文均存在。
- `needs_review`：正文和标题可用，但日期等必要字段缺失。
- `failed`：请求失败、标题缺失或正文长度不足。

只有未来经过用户确认进入正式管线后，`ready` 才有资格进入材料候选。`needs_review` 和 `failed` 不得交给 AI。

正文抽取会移除脚本、样式、导航、页头、页脚、表单、按钮、画布和 iframe，并保留段落、标题、列表与引用。第三方服务即使后续作为后备抓取器，也不能替换原始官网 URL 和来源身份。

SpaceXAI 使用“短超时直连一次，失败后调用 Firecrawl”的受限后备路径：

1. `/news` 列表页使用 Firecrawl Scrape 发现白名单详情链接。
2. 每个详情页都以已经发现的精确 URL 单独创建 Crawl 任务；请求固定 `limit=1`、`maxDiscoveryDepth=0`、`sitemap=skip`、`maxConcurrency=1`。这里不再添加 `includePaths`：官方说明该正则也会检查起始 URL，而深度 0 与跳过 sitemap 已经把发现范围限制在精确起始页，重复限定只会增加误排目标页的风险。
3. Crawl 任务采用有限轮询和 60 秒默认总时限。任务完成后，必须且只能返回一个文档，并且元数据中所有出现的 `sourceURL`、`url` 都须与请求 URL 一致；目录页、其他详情页、错误页和无正文结果都失败关闭，不进入解析成功状态。
4. 不假设一次整站 Crawl 每次都会同时返回目录页和目标详情页，也不从返回顺序猜测目标页。

Firecrawl API 密钥只从项目根 `.env` 的 `FIRECRAWL_API_KEY` 读取，
不得出现在代码、日志、命令参数或 JSON 预览中。可通过
`FIRECRAWL_CRAWL_POLL_SECONDS` 与 `FIRECRAWL_CRAWL_TIMEOUT_SECONDS`
调整轮询间隔和总时限。后备请求只获取 HTML、Markdown 与页面链接，
不启用 Firecrawl 的 LLM 清理或结构化提取能力。

## 6. 只读命令

全部四家公司、每家最多两篇：

```powershell
python -m orbitai.website_preview
```

只检查一家：

```powershell
python -m orbitai.website_preview --source anthropic --limit 1
```

机器可读输出：

```powershell
python -m orbitai.website_preview --limit 1 --json
```

只有显式传入 `--include-content` 时，JSON 才包含完整正文；默认只输出正文长度和 240 字预览。

## 7. 真实官网验收

2026-07-26 至 2026-07-28 使用本地 Python `urllib` 与受限 Firecrawl 实测：

| 来源 | 发现结果 | 详情结果 | 当前判断 |
|---|---:|---|---|
| Anthropic | 13 个白名单文章链接 | 最近一篇标题、日期、正文完整，`ready` | 可使用本地直接抓取 |
| Meta AI | 10 个白名单文章链接 | 最近一篇标题、日期、正文完整，`ready` | 可使用本地直接抓取 |
| DeepSeek | 当前入口发现 1 个官方 News 链接 | 标题、日期、正文完整，`ready` | 可使用本地直接抓取；继续排除 `/updates` |
| SpaceXAI | 本地直连返回 HTTP 403；Firecrawl 列表页发现 66 个白名单链接 | 早期 Scrape 详情调用只得到 xAI 错误页；用户提供的 Crawl 结果包含完整详情正文。2026-07-28 改为精确 URL、`limit=1` 的程序化 Crawl 后，`grok-4-5` 返回标题、日期和 7,258 字正文，状态为 `ready` | Firecrawl Crawl 可作为受限只读详情后备；单次成功不代表长期稳定，失败时必须关闭并转人工 |

发现数量只是验收时快照，不是长期数量承诺。
Firecrawl Search 可以命中同一官方详情页的标题、URL 和短描述，但不返回正文，
因此不能用搜索摘要冒充原始文章。错误页会被显式拒绝，不得因为长度达到门槛
而标记为 `ready` 或 `needs_review`。

Firecrawl Map 可以作为未来的候选 URL 补充发现手段，但不返回正文；Map 的
`search` 只用于按 URL 相关性排序，不能代替本地 `/news/{slug}` 白名单过滤。
正式主路径不依赖 Playground 的 Search 查询或结果排序，当前仍以固定 `/news`
列表 Scrape 为发现入口。

用户提供的两份 Firecrawl Crawl 样本分别包含 x.ai News 目录和完整的
“Grok Imagine API”详情正文，证明 Crawl 与此前的详情 Scrape 不是同一种结果。
由于 Playground 的一次运行可能返回不同页面组合，活动实现没有照搬“整站 Crawl
后取某一页”的方式，而是先发现 URL，再对该精确 URL 启动单页 Crawl，并校验返回
文档数量与元数据中的原始 URL。

## 8. 后续处理（2026-09-16 更新）

三家官网的独立按需材料入口已实现，保存前展示标题、实际来源、原始链接、发布日期与正文。失败转手工摘录，不自动调用 AI。来源新增登记仍保留完整预览等待统一审核；SpaceXAI 正式路径和定时采集未启用。新的实施范围与实测结果以完整交付规格、统一验收说明为准，不重复要求用户决定常规字段映射。
