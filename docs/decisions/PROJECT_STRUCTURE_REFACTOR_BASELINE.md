# OrbitAI 项目结构重构阶段 0 基线报告

类别：结构重构决策记录

状态：**阶段 0 已完成。** 用户已明确授权，重构分支已经建立，SQLite 备份已经验证；提交本报告的 Git 提交即为重构前检查点。

记录时间：2026-07-17 11:59:26 +08:00

对应计划：`docs/decisions/PROJECT_STRUCTURE_REFACTOR_PLAN.md`

## 1. Git 基线

- 重构分支：`codex/project-structure-refactor`
- 重构前父提交：`75367fbe756ec5713d3944e046923294c0a7abc5`
- 父提交说明：`V4.0 完成范围与核心数据模型`
- 审查开始时共有 10 个已跟踪变更路径和 14 个未跟踪文件。
- 本报告是阶段 0 新增的第 15 个未跟踪文件，也应纳入重构前检查点。
- 提交本报告及其审计范围的 Git 提交是阶段 0 检查点；后续各阶段从该提交继续。

## 2. 拟纳入检查点的改动范围

### 2.1 V4.1 目录数据、迁移与后台能力

- `orbitai/migrations.py`
  - 新增迁移 `0005 catalog_lookup_indexes_v1`。
  - 为产业、赛道、组织、人物、别名、来源和反向关系查询增加索引。
- `tests/migrations/test_migrations.py`
  - 更新迁移版本预期。
  - 新增目录索引测试并保持受保护回滚测试。
- `data/catalog/foundation_models.v4.1.json`
  - 1 个产业、4 个目录分组、26 个赛道。
  - 6 个组织、6 位人物和对应任职、赛道及来源关系。
- `orbitai/catalog_import.py`
  - 名册校验、只读预览、冲突报告、显式确认和事务幂等写入。
- `orbitai/catalog_repository.py`
  - 名册写入、状态读取和产业目录查询。
- `orbitai/catalog_service.py`
  - 按四大分组组织赛道，并依据参与者关系计算“已建设/待建设”。
- `tests/catalog/test_catalog_import.py`
  - 覆盖校验、只读预览、幂等写入、冲突保护和事务回滚。
- `tests/catalog/test_catalog_page.py`
  - 覆盖 26 赛道分组、赛道通用状态判断、页面渲染和 404。

### 2.2 V4.1-C 产业目录页面

- `app.py`
  - 新增 `/industries/{industry_slug}` 动态路由。
- `templates/industry_catalog.html`
  - 新增产业目录工程验证页。
- `templates/base.html`
  - 增加产业目录导航和可替换模板区块。
- `templates/status.html`
  - 增加产业目录入口。
- `static/style.css`
  - 增加目录页布局、分组、赛道和参与者样式。

### 2.3 已确认范围、审核记录和实现说明

- `AGENTS.md`
  - 增加 V4 单赛道约束、V4.1 名册与目录页现状、页面长期方向和验证命令。
- `docs/product/ORBITAI_ROADMAP.md`
  - 将通用基础模型试点和 V4.1 起点更新为已确认状态。
- `docs/specs/V4_INDUSTRY_DOSSIER_SPEC.md`
  - 补充 V4.1—V4.5 单赛道边界和页面长期方向。
- 项目目标文档已归位至 `docs/product/PROJECT_GOALS.md`
  - 属于文档移动，同时增加已确认的单赛道约束，因此内容并非逐字节相同。
- `docs/specs/V4_1_CATALOG_SPEC.md`
- `docs/guides/V4_1_CATALOG_IMPORT_GUIDE.md`
- `docs/decisions/V4_1_CATALOG_REVIEW_CHECKLIST.md`
- `docs/guides/V4_1_CATALOG_PAGE_GUIDE.md`
- `docs/product/V4_PRODUCT_PAGE_VISION.md`

审核清单顶部已经记录“全部项目确认、无修改、无暂缓、正式写库授权是”和实际写库结果。下方未勾选的选项是特意保留的原始逐项审核模板，不代表审核尚未完成。

### 2.4 本轮项目结构重构依据

- `docs/decisions/PROJECT_STRUCTURE_REFACTOR_PLAN.md`
  - 用户已于 2026-07-17 确认其为正式行动依据。
- `docs/decisions/PROJECT_STRUCTURE_REFACTOR_BASELINE.md`
  - 本报告，记录重构前可复查基线。

## 3. 审查结论

- 上述改动形成一组连贯的 V4.1-A/B/C 交付及项目结构重构准备，没有发现明显无关改动。
- 没有发现拟纳入检查点的文件包含 API 密钥、密码、访问令牌或私钥。
- `.env`、`orbitai.db`、`data.json` 和 `snapshots/` 均未进入拟提交文件列表。
- `git diff --check` 和未跟踪文件尾随空白检查未发现内容错误。
- Git 在 Windows 上提示部分文件下次写入时可能从 LF 转成 CRLF；这是行尾提示，不是当前内容错误。后续移动文件时应避免制造纯行尾噪声。
- 当前变更符合 V4 单赛道范围，没有横向建设其他赛道内容，也没有提前实现 V4.2 事件业务。

## 4. 自动测试基线

执行命令：

```powershell
python -m unittest discover -s tests -v
```

结果：

- 运行 21 项测试。
- 21 项全部通过。
- 耗时约 3.3 秒。
- 唯一提示是 FastAPI TestClient 所依赖的 Starlette/httpx 第三方弃用警告，不影响测试结果。

## 5. 数据库与迁移基线

数据库：`D:\workplace\My Project\OrbitAI\orbitai.db`

- 文件大小：552,960 字节。
- SHA-256：`a47e57cd8d76b549b3c3499301421e781d6170145ffecc4e90f04c1aaf77c013`
- `PRAGMA integrity_check`：`ok`
- `PRAGMA foreign_key_check`：0 个错误
- 已应用迁移：`0001`、`0002`、`0003`、`0004`、`0005`

关键表行数：

| 表 | 行数 |
| --- | ---: |
| `articles` | 156 |
| `documents` | 0 |
| `events` | 0 |
| `industries` | 1 |
| `segments` | 26 |
| `organizations` | 6 |
| `people` | 6 |

当前数据库仍是根目录正式数据库；阶段 0 不切换活动数据库路径。

## 6. 名册种子与预览基线

- 种子：`data/catalog/foundation_models.v4.1.json`
- `seed_id`：`v4_1_foundation_models_roster`
- `status`：`draft`
- SHA-256：`922dfe7421b72bd03126b2508a1642c799ad40231f7873813d02b4abf2c71d4f`
- 校验错误：0
- 校验警告：2
- 预览操作：124
- `unchanged`：124
- 阻塞操作：0
- 实际写入：否

两条警告分别对应人物任职关系 R-05、R-06 仍需补充一手来源；审核记录已经明确接受它们以当前状态进入名册，不属于本次重构阻塞项。

## 7. Web 路由与行为基线

当前业务路由：

```text
GET  /
GET  /index.html
GET  /featured
GET  /featured.html
GET  /daily
GET  /daily.html
GET  /industries/{industry_slug}
GET  /status
POST /admin/fetch
POST /admin/process-ai
POST /admin/regenerate
GET  /api/items
GET  /api/featured
GET  /api/daily
GET  /api/status
GET  /api/top
GET  /health
```

只读行为检查：

| 路径 | 状态码 | 内容类型或结果 |
| --- | ---: | --- |
| `/` | 200 | `text/html` |
| `/industries/artificial-intelligence` | 200 | `text/html`，包含核心能力、基础设施、产品与应用、外部环境 |
| `/industries/not-a-real-industry` | 404 | `application/json` |
| `/status` | 200 | `text/html` |
| `/api/status` | 200 | `application/json` |
| `/health` | 200 | `application/json` |

阶段 2 改路由前，应以这份列表和状态码作为兼容对照。

## 8. SQLite 备份与阶段 0 完成记录

用户于 2026-07-17 明确授权建立重构分支、Git 检查点和 SQLite 备份。

- 重构分支：`codex/project-structure-refactor`
- 备份方式：Python `sqlite3` Backup API；源连接使用只读 URI 和 `PRAGMA query_only = ON`。
- 备份文件：`var/backups/orbitai-phase0-20260717-120708.db`
- 文件大小：552,960 字节。
- 备份 SHA-256：`b30633f451ba59e07ed2101663984db89fb9e73973c61c2f120c14b59d197f09`
- 源数据库备份前后 SHA-256：`a47e57cd8d76b549b3c3499301421e781d6170145ffecc4e90f04c1aaf77c013`，未发生变化。
- `PRAGMA integrity_check`：`ok`
- `PRAGMA foreign_key_check`：0 个错误
- 已应用迁移：`0001`、`0002`、`0003`、`0004`、`0005`
- 关键表行数与本报告第 5 节完全一致。

备份文件受现有 `*.db` 规则保护，不进入 Git 检查点。提交本报告的 Git 提交保存全部已审计代码、种子、文档、模板和测试，阶段 0 因此达到退出标准。
