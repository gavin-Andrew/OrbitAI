# Agent 工作指南

这份文件是 Codex 和其他编程代理在本仓库中的工作指南。开始任何代码修改前，先阅读本文件。

`PROJECT_GOALS.md` 是产品愿景和战略背景，不是日常编码指南。常规代码修改不需要每次重读它；当任务涉及产品方向、V4 范围、路线取舍，或本指南不足以做判断时，再查阅 `PROJECT_GOALS.md`。

## 项目方向

OrbitAI 是一个本地优先的个人 AI 与硬科技产业研究系统。项目正在从“AI 信息雷达”转向“个人产业认知系统”。

工作时始终记住：

- 从收集信息，走向组织事实、观点、证据和验证结果。
- 帮助用户形成更好的判断，而不是让 AI 替代用户判断。
- 保留原始来源、不确定性、证据和后续验证空间。
- 优先长期可维护性，不为了展示效果堆砌信息流功能。

## 当前技术基线

当前应用是一个本地 Python Web App：

- `app.py`：FastAPI 兼容启动入口，只从 `orbitai.web.app` 导出 `app` 与应用工厂。
- `main.py`：RSS、AI 处理、SQLite 和静态生成流程调度。
- `orbitai/core/config.py`：集中定义项目根目录、当前运行文件路径和环境配置；路径不再依赖启动时的工作目录。
- `orbitai/core/database.py`：SQLite 连接与初始化。
- `orbitai/core/migrations.py`：SQLite 版本迁移、状态检查和受保护回滚。
- `orbitai/config.py`、`orbitai/database.py`、`orbitai/migrations.py`：旧导入和 CLI 的薄兼容包装；新活动代码应直接使用 `orbitai.core`。
- `orbitai/materials/`：文章字段、SQLite 文章仓储、RSS、AI 客户端与处理、评分等材料能力的活动实现；`legacy_json.py` 只临时保留待对账清退的旧 `data.json` 读写。
- `orbitai/catalog/repository.py`：V4.1 名册集中读写与目录查询的活动实现。
- `orbitai/catalog/service.py`：把产业、四大分组、赛道和参与者整理成页面数据。
- `orbitai/catalog/import_service.py`：名册校验、只读预览与显式事务写入实现。
- `orbitai/web/app.py`：FastAPI 应用组装与静态目录挂载。
- `orbitai/web/routes/`：按 `dossier`、`materials`、`admin`、`api` 拆分的活动 Web 路由。
- `orbitai/web/view_helpers.py`：动态页面使用的展示字段、日期筛选与模板上下文辅助函数。
- `orbitai/web/static_snapshots.py`：等待后续清退的静态 HTML 快照生成实现；动态 Web 页面不得新增对它的依赖。
- 当前规范页面地址为 `/industries/{industry_slug}`、`/materials`、`/materials/featured`、`/materials/daily` 和 `/admin/status`；`/` 使用 HTTP 307 临时重定向到 AI 产业目录，旧材料页与状态页地址也使用 307 重定向到对应规范地址。
- `orbitai/repository.py`、`rss_fetcher.py`、`ai_client.py`、`ai_processor.py`、`scoring.py`、`data_utils.py`、`catalog_repository.py`、`catalog_service.py`、`catalog_import.py`、`html_generator.py`：旧导入或 CLI 的薄兼容包装；新活动代码禁止继续引用这些旧路径。
- `orbitai/`：除薄兼容包装外，活动实现按 `core`、`materials`、`catalog`、`web` 职责组织。
- `tests/`：当前聚焦测试，优先覆盖数据库迁移和 V4 核心数据约束。
- `templates/dossier/`、`templates/materials/`、`templates/admin/`：按页面职责拆分的 Jinja2 模板。
- `static/shared/`、`static/dossier/`、`static/materials/`、`static/admin/`：共享基础样式和各页面边界的前端资源。
- `var/orbitai.db`：当前唯一活动的本地 SQLite 数据库；根 `orbitai.db` 只作为阶段 4 前副本保留，不再由应用读写。
- `var/backups/`：经 SQLite Backup API 创建并校验的本地数据库备份。
- `var/snapshots/`：静态 HTML 快照兼容输出目录，包含 `index.html`、`featured.html`、`daily.html`。
- `data/registries/`：RSS 来源配置和 V4 来源注册表。
- `data/seeds/catalog/`：可审核的 V4.1 名册种子。
- `data/archive/data.json`：已完成字段级对账的旧 JSON 历史备份；它保留 SQLite 中没有的逐维评分与处理时间，当前不得删除。

除非用户明确要求更大的存储改造，否则继续把 SQLite 作为 MVP 数据库。PostgreSQL、向量数据库和全文搜索引擎都是未来选项，不是默认选择。

## 工作规则

- 保持改动小、聚焦、可验证。
- 编辑前检查当前仓库状态，不覆盖无关的用户改动。
- 面向项目的文档默认使用简体中文，除非现有文件约定或外部工具要求英文。
- 代理起草的产品、战略、路线或范围文档，在用户阅读并明确确认前，必须标注为草案，不能称为项目共识或已确定方案。
- 优先沿用现有模块、风格和数据访问模式，不轻易引入新抽象。
- 较大功能应先明确目标、范围和不做什么，并写入项目文档或实现说明。
- 维护清晰的数据模型和可测试的代码路径。
- 新增研究功能时，尽量在数据模型中区分事实、观点、证据、预测和验证状态。
- AI 生成摘要、分类、观点卡片或分析字段时，必须保留原始来源。
- 不用流畅的 AI 文案掩盖证据不足或数据不确定。
- 明确区分本地动态 Web App 和 GitHub 静态部署快照。
- 不提交密钥或 `.env` 值。
- 数据库结构变更必须新增版本迁移，不再把新的临时 `ALTER TABLE` 直接堆进 `init_db()`。

## V4 产品优先级

V4 当前名称和主线是“可追溯的 AI 动态产业档案”。总体路径见 `docs/ORBITAI_ROADMAP.md`；该路线图已经用户审核确认，是 OrbitAI 长期阶段划分和 V4 方向的正式依据。各阶段开始前仍应另写实现规格，不要把远期概念模型一次性塞入当前版本。

V4 首先解决“怎样把 AI 产业讲清楚”，不立即建设完整产业分析引擎。核心组织路径是：

```text
产业 -> 细分赛道 -> 企业/机构/人物 -> 关键事件
     -> 原始来源 -> 可核查主张/观点/反馈
```

V4 全阶段采用单赛道纵向试点：第一个且当前唯一的深度试点是“通用基础模型（含大语言模型）”。在该赛道依次跑通 V4.1 的产业与参与者目录、V4.2 的事件台账与时间线、V4.3 的事件档案与证据、V4.4 的动态产业档案以及 V4.5 的整理工作流与质量闭环，并达到 V4 退出标准前，不横向建设其他赛道的参与者、事件、来源证据和档案内容。可以保留已经确认的 AI 产业目录骨架和空白入口，但必须明确标记尚未建设，不能用生成内容填充空白。

单赛道只限制当前内容范围，不限制系统模型。数据库、仓储、路由和页面能力应保持赛道通用，不能把“通用基础模型”硬编码成唯一业务对象；完整闭环验证通过后，再按同一套能力逐步补充其他赛道。

V4.1 首批名册范围已经确认采用 6 个组织和 6 位人物；具体对象、身份边界、核查状态和种子字段以 `docs/V4_1_CATALOG_SPEC.md` 与 `data/seeds/catalog/foundation_models.v4.1.json` 为准。未经用户再次确认，不在 V4.1 横向扩充参与者名单；种子中的草案字段不能因为写入文件就被视为已确认事实。

2026-07-16，V4.1 首批名册已经完成中文逐项审核、显式授权和首次事务写入；正式审核记录见 `docs/V4_1_CATALOG_REVIEW_CHECKLIST.md`。后续修改种子或数据库名册时，仍必须先生成预览，不得把首次授权解释为对未来修改的永久授权。

V4.1-C 的首个产业目录页面已经实现，动态地址为 `/industries/artificial-intelligence`。页面按固定顺序显示四大分组和全部 26 个赛道，并根据赛道当前关联的组织、人物数量判断“已建设”或“待建设”；该判断保持赛道通用，不得改成对试点 ID 的硬编码。当前页面底部只提供首批名册摘要，独立赛道、组织、人物详情页和来源映射页仍待后续开发。

当前 V4.1-C 页面只是在沿用既有 Jinja2 和 CSS 基础上建立的工程验证页，不代表最终面向用户的产品界面。用户已经明确最终 V4 页面方向：默认入口直接呈现完整的 AI 产业结构，上方使用“产业结构、企业档案、人物档案”三个一级选项；点击赛道后进入独立赛道页，赛道页上部介绍赛道及其可追溯的发展历程，下部按企业展示发展时间线，后续把已确认事件挂到时间线上并允许继续进入事件档案。四大分组之间的产业关系留到后续产业分析阶段，其他顶层产业也属于远期范围。完整方向见 `docs/V4_PRODUCT_PAGE_VISION.md`。在通用基础模型试点完整跑通前，不为了接近最终视觉而大规模重写现有 Jinja2 和 CSS；试点完成后再统一进行用户界面重设计。

V4.1 首个页面必须按“人工智能产业 -> 四大目录分组 -> 26 个赛道”组织内容。核心能力、基础设施、产品与应用、外部环境四大分组都是不可省略的正式层级；当前只有“通用基础模型”允许进入深度内容，其他赛道显示待建设，但四大类和空白入口仍须完整可见。

V4 应把事件作为连接产业、参与者、时间和材料的核心对象。企业发展历史和人物观点演变是重要叙事入口；一个事件可以关联多个参与者和赛道。

AI 产业不能只表达为单一分类树。第一版目录已经确认采用核心能力、基础设施、产品与应用、外部环境四大分组；数据模型应允许表达支持、依赖、供应、采用、竞争、合作和监管等少量受控关系，但继续使用 SQLite 和普通关联表，不急于建设知识图谱。

主张是来自具体文档、可以被支持或反驳的可核查陈述；观点是人物或机构的解释、评价、预测或建议。两者必须保留原始文档和实际表达者，材料发布者不自动等于主张者或观点表达者；AI 提取在人工确认前只形成候选。

V4 早期优先建设：

- 产业和细分赛道目录，以及必要的赛道关系。
- 企业、机构和人物档案，包括别名和带时间的任职关系。
- 关键事件台账、事件参与者关系和企业/人物/赛道时间线。
- 事件档案，并为事件保留多个原始来源。
- 区分来源、原始文档、可核查主张、人物观点和用户反馈。
- 将现有信息源注册表和文章库映射到参与者与事件。
- 支持人工创建、修改、合并和确认事件；自动提取先产生候选，不直接成为确认事实。
- 建立从产业页逐层追溯到原始材料的最小浏览路径。

此前规划的信息源注册表和观点卡片仍然有效，但角色已经改变：信息源注册表是材料入口，观点卡片是事件档案和后续分析中的观点层，不再是 V4 唯一的产品中心。

目的驱动的影响因素评估、因果链、分析版本和持续验证属于 V5 及后续阶段。V4 可以为这些能力预留清晰边界，但不要提前实现完整分析系统。

## 默认不做

除非用户明确提出，并且范围已经说清楚，否则不要默认加入：

- 投资建议或股票买卖判断。
- 对产业未来的自动化确定性预测。
- V4 阶段自动计算影响因素的精确权重或自动推断完整因果链。
- 第一阶段就建设复杂知识图谱。
- 覆盖所有产业或所有社交媒体来源。
- 完全自动化、无人干预的分析系统。
- 在观点、事件和验证样本不足时进行人物人格模拟或模型蒸馏。
- 在 SQLite 明显不够用之前替换数据库。
- 不能改善研究工作流的装饰性 UI。

## 验证

根据改动风险选择验证方式。

Python 语法和导入安全检查：

```powershell
python -m compileall app.py main.py orbitai
```

聚焦测试：

```powershell
python -m unittest discover -s tests -v
```

数据库迁移状态与升级：

```powershell
python -m orbitai.migrations status
python -m orbitai.migrations up
```

V4.1 名册种子校验与只读导入预览：

```powershell
python -m orbitai.catalog_import preview --summary-only
```

V4.1 名册真实写入必须先审核完整预览，并显式确认种子 ID：

```powershell
python -m orbitai.catalog_import apply --confirm-seed-id v4_1_foundation_models_roster --summary-only
```

V4.1-C 产业目录页面聚焦测试：

```powershell
python -m unittest tests.test_catalog_page -v
```

Web 路由与页面资源边界聚焦测试：

```powershell
python -m unittest tests.test_web_structure -v
```

项目根路径、旧导入和迁移 CLI 兼容测试：

```powershell
python -m unittest tests.test_core_paths -v
```

运行数据路径、配置文件归位和数据库防错测试：

```powershell
python -m unittest tests.test_runtime_paths -v
```

材料、目录、展示和静态生成模块边界测试：

```powershell
python -m unittest tests.test_module_boundaries -v
```

不要把 `preview` 和 `apply` 视为等价操作；前者只读，后者会应用待执行迁移并写入业务数据。

本地应用行为检查：

```powershell
uvicorn app:app --reload
```

依赖安装：

```powershell
pip install -r requirements.txt
```

目前还没有完整测试套件，但已经有数据库迁移的聚焦测试。新增有风险的路由、数据库或 AI 处理逻辑时，应继续补小而聚焦的测试，或记录清楚手动验证路径。
