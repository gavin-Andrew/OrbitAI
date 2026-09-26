# OrbitAI V4.2 六家试点组织来源覆盖复核

类别：审核记录

状态：草案；入口可用性已经在 2026-07-25 在线验证。2026-07-26 用户根据实际运行结果要求停用四家无公司级官方 RSS 组织的 GitHub Atom。2026-07-28 用户认可在只读试抓中对 SpaceXAI 使用精确目标 URL 的 Firecrawl Crawl；新增和变更来源尚未写入活动数据库，仍需复核导入预览后另行授权。

关联文件：

- `../product/V4_INFORMATION_STRATEGY.md`
- `../specs/V4_SOURCE_REGISTRY.md`
- `../../data/registries/sources.json`
- `../../data/registries/sources.v4.json`
- `../../data/seeds/catalog/foundation_models.v4.1.json`

## 1. 本轮目标

为“通用基础模型（含大语言模型）”单赛道试点中的 6 家组织建立最低可用的来源组合：

- OpenAI
- Anthropic
- Google DeepMind
- Meta AI
- DeepSeek
- SpaceXAI

优先使用公司级官方 RSS。没有官方 RSS 时，明确标记覆盖缺口，并组合官方网页、官方 GitHub Atom、Newsletter、模型卡和手动录入入口。第三方生成的公司新闻镜像 RSS 不进入本轮活动抓取清单。

## 2. 在线验证方法

验证日期：2026-07-25

验证方式：

1. 检查官方 News、Blog、Docs、Newsletter、GitHub 和 Hugging Face 页面。
2. 请求常见 RSS 地址变体并检查 HTTP 状态与内容类型。
3. 使用 OrbitAI 当前 `urllib + feedparser` 依赖解析候选 RSS/Atom。
4. 只有能够返回条目且 `feed.bozo` 为假的入口，才进入 `data/registries/sources.json`。

测试时的解析结果会随来源更新而变化，条目数只证明验证时可用，不代表长期数量承诺。

## 3. 六家组织覆盖矩阵

| 组织 | 公司级官方 RSS 结论 | 当前活动自动入口 | 官方替代入口 | 覆盖边界 |
|---|---|---|---|---|
| OpenAI | 支持 | `https://openai.com/news/rss.xml`；1050 条；无解析警告 | News、开发者文档、发布会 | RSS 可作为公司级事实主入口 |
| Anthropic | 未发现；`/rss.xml`、`/news/rss.xml`、`/feed.xml`、`/news/rss` 均为 404 | 暂无；已验证的 Claude Code Releases Atom 已停用 | `https://www.anthropic.com/news`、`https://www.anthropic.com/events` | 暂由官网或人工录入 |
| Google DeepMind | 支持 | `https://deepmind.google/blog/rss.xml`；100 条；无解析警告 | `https://deepmind.google/blog/` | RSS 可作为公司级 News 主入口；Google AI Blog 继续保持独立补充源 |
| Meta AI | 未发现；常见 Blog/Feed/RSS 地址均为 404 | 暂无；已验证的 Llama Models Releases Atom 已停用 | `https://ai.meta.com/blog/`、`https://ai.meta.com/subscribe/` | 暂由官网、Newsletter 和模型卡人工处理 |
| DeepSeek | 未发现；常见 RSS 地址返回 HTML 而不是 feed | 暂无；已验证的 R1、V3 Commits Atom 已停用 | `https://api-docs.deepseek.com/zh-cn/news/`、`https://github.com/deepseek-ai`、`https://huggingface.co/deepseek-ai` | 暂由 News、GitHub 与模型卡人工筛选 |
| SpaceXAI | 未发现；`/news/rss.xml`、`/rss.xml`、`/feed.xml` 均为 404 | 暂无；已验证的 Python SDK Releases Atom 已停用 | `https://x.ai/news`、`https://docs.x.ai/developers/release-notes` | 暂由官网与 Release Notes 人工处理 |

## 4. 配置处理决定

- `data/registries/sources.json` 保留经过验证的 RSS/Atom 及其启停状态；只有 `enabled: true` 的入口进入抓取。
- `data/registries/sources.v4.json` 同时保存自动入口和尚未自动化的官网、Newsletter、模型卡与手动入口。
- Google DeepMind 与 Google AI 继续使用两个来源身份，避免把范围更宽的 Google AI Blog 自动归属于 Google DeepMind 参与者。
- Anthropic、Meta AI、DeepSeek、SpaceXAI 的 GitHub Atom 已设为 `enabled: false`，既不继续抓取，也不让此前未处理的对应材料进入 `python main.py` 的 AI 队列。
- 无官方 RSS 不等于使用第三方镜像冒充官方入口；第三方媒体材料应以其实际发布者身份进入来源和文档层。

## 5. 数据库写入边界

本轮没有运行名册 `apply`，也没有直接修改 `var/orbitai.db`。

更新后的 V4.1 名册种子仍然是 `draft`。新增 `source_entries` 必须先通过：

```powershell
python -m orbitai.catalog_import preview --summary-only
```

用户审核完整预览并重新显式授权后，才能应用到活动数据库。2026-07-16 的首次名册写入授权不适用于本次来源入口变更。

## 6. 用户运行反馈与当前决定

- [x] 继续启用 OpenAI 与 Google DeepMind 的公司级官方 RSS。
- [x] 停用 Anthropic、Meta AI、DeepSeek、SpaceXAI 的 5 条 GitHub Atom，避免小版本和普通提交污染材料库及 AI 评分队列。
- [x] 无官方 RSS 的四家公司暂时采用官网人工策划；网页自动监测器另行设计，不把第三方 RSS 镜像设为核心源。
- [x] 在官网只读试抓中，SpaceXAI 列表使用受限 Scrape，详情使用精确 URL、`limit=1` 的定向 Crawl；找不到精确目标页时失败关闭。
- [ ] 审核名册导入完整预览后，再决定是否把新增入口写入活动数据库。

## 7. 官网只读试抓结果

2026-07-27，按用户授权实现 `python -m orbitai.website_preview`。该命令仅发现官网文章和解析详情，不连接 SQLite、不调用 AI。

- Anthropic：直接抓取通过。
- Meta AI：直接抓取通过；已使用标题所在正文容器避免导航文字污染。
- DeepSeek：直接抓取通过；兼容站点返回的 `/news/{slug}` 与登记的 `/zh-cn/news/{slug}`，并继续排除 `/updates` 小版本日志。
- SpaceXAI：独立域名和路径规则已建立，本地 Python 请求连续返回 HTTP 403。2026-07-27 的 Firecrawl Scrape 列表调用成功发现 66 个白名单链接，但 Scrape 详情调用只返回 xAI 的 “Something went wrong” 错误页，Search 也只有标题、URL 和短描述。用户随后提供的两份 Crawl 结果分别包含目录内容和 “Grok Imagine API” 的完整详情正文，说明正确的 Crawl 路径具备正文能力，但一次整站运行返回哪些页面并不稳定。
- 2026-07-28 按用户确认改为两阶段调用：先从列表发现白名单 URL，再对选中的精确详情 URL 创建 `limit=1`、深度 0、跳过 sitemap 的定向 Crawl。完成结果必须包含元数据 URL 完全一致的目标页，否则失败关闭。在线程序化验收对 `https://x.ai/news/grok-4-5` 成功取得 “Introducing Grok 4.5”、`Jul 16, 2026` 和 7,258 字正文，状态为 `ready`；列表与详情提供者分别记录为 `firecrawl_scrape` 和 `firecrawl_crawl`。

只读实现和后续决策门见 `../specs/V4_2_WEB_SOURCE_PREVIEW_SPEC.md`。本次成功只证明定向 Crawl 路径当前可用，不保证长期稳定；失败必须转人工，不能用目录、其他详情页、错误页或 Search 摘要顶替。正式写库、AI 处理和定时任务仍需另行审核。
