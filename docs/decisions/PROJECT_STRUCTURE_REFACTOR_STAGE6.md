# OrbitAI 项目结构重构阶段 6 执行记录

类别：结构重构决策记录

状态：**阶段 6 实施与技术验收已完成，等待用户最终确认本轮重构闭环。**

日期：2026-07-17

对应计划：`docs/decisions/PROJECT_STRUCTURE_REFACTOR_PLAN.md`

阶段 5 检查点：`f66d924`

测试归位检查点：`a120952`

## 1. 本阶段目标

让测试、文档、README 和代理工作指南与阶段 1 至 5 已形成的职责边界保持一致，并为本轮项目结构重构建立可检查的最终说明。

本阶段只整理测试与版本控制文档，不删除根数据库、旧 JSON 归档、历史快照文件或兼容 URL，也不改变 V4 产品范围和页面外观。

## 2. 测试归位

测试目录现在按职责组织：

```text
tests/
├─ materials/
│  └─ test_main_pipeline.py
├─ catalog/
│  ├─ test_catalog_import.py
│  └─ test_catalog_page.py
├─ migrations/
│  └─ test_migrations.py
└─ acceptance/
   ├─ test_core_paths.py
   ├─ test_documentation.py
   ├─ test_module_boundaries.py
   ├─ test_runtime_paths.py
   └─ test_web_structure.py
```

各子目录包含 `__init__.py`，因此既支持完整 discovery，也支持按完整模块路径运行聚焦测试。嵌套后依赖项目根目录的测试统一使用 `Path(__file__).resolve().parents[2]`。

测试移动与文档移动没有混在同一提交；测试归位先以 `a120952 test: organize suite by responsibility` 建立了独立检查点。

## 3. 文档归位

文档现在按职责组织：

```text
docs/
├─ README.md       # 文档索引与维护规则
├─ product/        # 产品目标、路线图、信息策略和页面长期方向
├─ specs/          # 产业档案、V4.1 名册和来源注册表规格
├─ guides/         # 名册导入与产业目录页面指南
├─ decisions/      # 审核、结构决策、数据对账和阶段退出记录
└─ archive/        # 失效文档归档规则
```

现有文档中没有应被直接判定为失效的内容。较早的结构重构记录仍有决策和审计价值，因此进入 `decisions/`，而不是 `archive/`。`docs/archive/README.md` 明确了后续归档准入条件。

## 4. 指南与路径维护

- 根 README 的启动方式、规范 URL、材料更新语义、目录树和测试命令已经更新。
- `AGENTS.md` 的技术基线、文档入口、测试分类、验证命令和静态快照退役说明已经更新。
- 产品、规格、指南和历史决策记录中的文档路径与测试路径都已修复为当前位置。
- 新增 `tests/acceptance/test_documentation.py`，自动检查文档根目录分类、仓库内 Markdown/测试路径、相对 Markdown 链接和已退役扁平路径。

## 5. 当前兼容层清单

仍受支持的稳定 CLI 包装：

- `orbitai/migrations.py` -> `orbitai/core/migrations.py`
- `orbitai/catalog_import.py` -> `orbitai/catalog/import_service.py`

仍等待单独清退确认的兼容 URL：

- `/index.html` -> `/materials`
- `/featured`、`/featured.html` -> `/materials/featured`
- `/daily`、`/daily.html` -> `/materials/daily`
- `/status` -> `/admin/status`

`/` 到 `/industries/artificial-intelligence` 是当前产品入口重定向，不属于待清退的旧材料 URL。

## 6. 保留实物与剩余技术债

仍按既有边界保留：

- 根目录只读 `orbitai.db`。
- `data/archive/data.json`，其中包含 SQLite 没有的逐维评分和 AI 处理时间。
- `var/snapshots/` 中三个已经失去生成调用方的历史 HTML 文件。

剩余技术债：

- Starlette TestClient 与当前 httpx 组合会产生一条第三方弃用警告；当前不影响 45 项测试，应在依赖升级时处理。
- `main.py` 目前同时为 CLI 和管理路由提供材料更新编排，但不承载 SQL、抓取、AI 或评分实现；若以后管理工作流继续增长，再把编排提取为应用服务。
- 六个兼容 URL 和三个历史快照文件何时删除，仍需用户分别确认，不能由本轮完成状态自动推导。
- 当前产业目录仍是 V4.1 工程验证页，不是最终视觉；统一界面重设计继续遵守单赛道试点边界。

## 7. 自动验证

```powershell
python -m compileall app.py main.py orbitai
python -m unittest discover -s tests -v
python -m orbitai.migrations status
python -m orbitai.catalog_import preview --summary-only
```

结果：

- Python 编译检查通过。
- 45 项测试全部通过；仅有上述既存第三方弃用警告。
- 迁移 `0001` 至 `0005` 状态正常。
- 名册预览为校验错误 0、已知警告 2、124 条 `unchanged`、阻塞项 0、`applied=false`。
- 活动数据库完整性为 `ok`，关键数据和阶段 4 保留实物未被改写。
- `articles` 仍为 156，`documents.article_id` 指向不存在文章的记录为 0。
- 根数据库、活动数据库、旧 JSON 归档和三个历史快照的 SHA256 均与阶段 4 记录一致。
- Git 忽略范围内的数据库、备份、快照、归档 JSON、`.env` 和缓存均未进入提交。

## 8. 本地应用行为验收

使用 FastAPI TestClient 对正式活动数据库执行只读验收：

- `/` 返回 307 并指向 `/industries/artificial-intelligence`。
- 产业目录、三个材料页面、管理状态页、`/api/status` 和 `/health` 均返回 200。
- `/index.html`、`/featured`、`/daily`、`/status` 均返回 307 并指向对应规范地址。
- 验收没有执行 RSS 抓取、AI 调用、名册 apply 或任何管理写操作。

## 9. 最终状态

阶段 0 至 6 的计划内实施工作和技术验收均已完成。根据正式计划的退出标准，仍需用户阅读本记录并明确确认后，才能把“本轮项目结构重构完成”记为最终项目结论。
