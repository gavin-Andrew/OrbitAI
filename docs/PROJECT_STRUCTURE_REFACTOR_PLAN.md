# OrbitAI 项目结构重构行动计划

状态：**用户已于 2026-07-17 审核确认，作为本轮项目结构重构的正式行动依据。** 默认首页、正式数据库路径和旧链路清退仍须遵守本文约定的后续确认门槛。

版本：2026-07-17

## 1. 目的

本轮重构不是重写 OrbitAI，也不是删除 V3 的全部成果，而是把现有代码重新组织成长期可维护的职责边界：

- 把 RSS、文章库、AI 处理和评分转正为 V4 的“材料采集与处理系统”。
- 把产业、赛道、组织和人物能力集中为“产业目录系统”。
- 为后续事件台账和事件档案预留清晰位置，但本轮不提前开发 V4.2。
- 把阅读端、材料端、管理端和 API 路由从根 `app.py` 中拆开。
- 让根 `app.py` 与 `main.py` 保持为稳定、很薄的启动入口。
- 逐步退役旧信息流产品外壳和静态快照链路，同时保留原始材料、数据库和迁移历史。

本轮完成后，V4 不再是附着在 V3 页面上的新增功能，而是 OrbitAI 的主产品结构；V3 中仍有价值的采集和处理能力成为材料层。

## 2. 已核实的当前基线

以下记录是 2026-07-17 的重构前审计快照，不应被当作永久不变的项目说明：

- 当前正式数据库为根目录 `orbitai.db`。
- `articles` 表有 156 条记录。
- 根目录 `data.json` 有 56 个唯一链接，这 56 个链接全部已经存在于 SQLite；SQLite 另有 100 个不在旧 JSON 中的链接。
- `documents.article_id` 已经可以追溯到 `articles.id`。
- 当前测试套件共有 21 项测试并全部通过；存在一条 Starlette/httpx 第三方弃用警告，但不影响当前测试结果。
- 当前工作区包含尚未提交的 V4.1 代码、文档、模板和测试改动，禁止在建立检查点前批量移动文件。
- `data.json`、`orbitai.db` 和 `snapshots/` 当前均被 Git 忽略。
- `load_existing_data()` 与 `save_data()` 目前只剩定义，没有活动调用方；删除前仍需用引用检查和数据对账再次确认。

## 3. 本轮范围

### 3.1 本轮要做

- 建立重构前 Git 检查点和 SQLite 可恢复备份。
- 建立 `core`、`materials`、`catalog`、`web` 的代码边界。
- 拆分根 `app.py` 中的阅读端、材料端、管理端和 API 路由。
- 拆分 `dossier`、`materials`、`admin` 三套模板和静态资源边界。
- 将文章仓储、RSS、AI 处理、评分和文章字段工具归入 `materials`。
- 将产业目录的导入、仓储和服务归入 `catalog`。
- 集中管理项目根路径、运行数据路径、来源配置路径和模板路径。
- 在验证通过后，将运行数据库、备份和静态快照收拢到 `var/`。
- 将可审核种子和来源注册表收拢到 `data/`。
- 在独立阶段整理项目文档目录并修复全部内部链接。
- 更新 README、`AGENTS.md`、验证命令和项目结构说明。

### 3.2 本轮明确不做

- 不进行最终 V4 视觉重设计，不制作思维导图式最终首页。
- 不改变“通用基础模型（含大语言模型）”是当前唯一纵向试点的产品范围。
- 不横向扩充参与者、事件、来源证据或其他赛道内容。
- 不开发 V4.2 事件台账、时间线或事件档案业务能力。
- 不修改现有数据库业务模型，不为了整理目录新增业务迁移。
- 不替换 SQLite，不引入 PostgreSQL、向量数据库或搜索引擎。
- 不同时重写采集、AI、评分或目录查询逻辑。
- 不把结构重构解释为旧页面已经完成最终产品设计。
- 不在同一个步骤内同时移动代码、切换数据库路径和删除兼容链路。

## 4. 重构期间必须保持的约束

1. `uvicorn app:app --reload` 始终是有效的本地启动命令。
2. `python main.py` 在静态快照正式退役前保持可运行；其语义变化必须单独确认和记录。
3. 完整保留 SQLite 迁移历史，包括 `0001`。
4. 不覆盖当前用户改动，不把未审查的工作区内容混入重构提交。
5. 每个阶段独立验证、独立形成 Git 检查点，可以单独回退。
6. 文件移动优先保持行为等价，业务逻辑调整另开阶段。
7. 新包建立后允许短期保留兼容导入，但兼容层必须有明确清退条件。
8. 数据库只允许一个活动写入位置，不进行根目录与 `var/` 双写。
9. 备份必须可打开、通过 `PRAGMA integrity_check`，并核对关键表数量后才算有效。
10. 未经用户确认，不删除根数据库、旧 JSON、静态快照入口或兼容路由。

## 5. 目标目录

目标结构表示重构完成后的职责边界，不要求一次性创建所有空目录：

```text
OrbitAI/
├─ app.py                         # 很薄的 FastAPI 启动入口，继续暴露 app
├─ main.py                        # 很薄的命令行入口
├─ orbitai/
│  ├─ core/
│  │  ├─ config.py                # 配置、项目路径与运行路径
│  │  ├─ database.py              # SQLite 连接
│  │  └─ migrations.py            # 迁移实现
│  ├─ materials/
│  │  ├─ repository.py            # articles 仓储与状态查询
│  │  ├─ fields.py                # 文章字段构造与兼容规范化
│  │  ├─ rss.py                   # RSS 来源读取与抓取
│  │  ├─ ai_client.py
│  │  ├─ ai_processor.py
│  │  └─ scoring.py
│  ├─ catalog/
│  │  ├─ import_service.py         # 名册校验、预览与写入实现
│  │  ├─ repository.py
│  │  └─ service.py
│  └─ web/
│     ├─ app.py                    # FastAPI 组装
│     ├─ view_helpers.py           # 通用展示字段，不含静态生成
│     └─ routes/
│        ├─ dossier.py             # 产业档案阅读端
│        ├─ materials.py           # 材料收件箱
│        ├─ admin.py               # 状态与操作入口
│        └─ api.py                 # JSON API 与健康检查
├─ templates/
│  ├─ dossier/
│  ├─ materials/
│  └─ admin/
├─ static/
│  ├─ dossier/
│  ├─ materials/
│  └─ admin/
├─ data/
│  ├─ seeds/
│  │  └─ catalog/
│  ├─ registries/
│  └─ archive/
├─ var/                            # Git 忽略的本地运行数据
│  ├─ orbitai.db
│  ├─ backups/
│  └─ snapshots/
├─ docs/
│  ├─ product/
│  ├─ specs/
│  ├─ guides/
│  ├─ decisions/
│  └─ archive/
└─ tests/
   ├─ materials/
   ├─ catalog/
   ├─ migrations/
   └─ acceptance/
```

### 5.1 暂不创建的占位包

`orbitai/events/` 属于 V4.2。只有事件实现规格获得确认并开始开发时才创建，不为了目录看起来完整而加入空业务包。

### 5.2 需要保留的根级入口与兼容模块

以下文件名属于现有运行契约，即使实现移入子包也继续保留：

- `app.py`：继续支持 `uvicorn app:app --reload`。
- `main.py`：继续作为本地命令行入口。
- `orbitai/migrations.py`：在迁移实现移入 `core` 后，短期作为 CLI 兼容包装，继续支持 `python -m orbitai.migrations`。
- `orbitai/catalog_import.py`：在导入实现移入 `catalog` 后，短期作为 CLI 兼容包装，继续支持 `python -m orbitai.catalog_import`。

兼容包装只允许转发导入和 `main()`，不能继续承载业务实现。

## 6. 建议的文件迁移映射

| 当前文件 | 目标文件 | 迁移要求 |
| --- | --- | --- |
| `orbitai/config.py` | `orbitai/core/config.py` | 集中路径；旧文件短期转发 |
| `orbitai/database.py` | `orbitai/core/database.py` | 保持可传入临时数据库路径 |
| `orbitai/migrations.py` | `orbitai/core/migrations.py` | 根模块保留 CLI 包装 |
| `orbitai/repository.py` | `orbitai/materials/repository.py` | 不在移动时重写 SQL |
| `orbitai/rss_fetcher.py` | `orbitai/materials/rss.py` | 保持来源格式和重试行为 |
| `orbitai/ai_client.py` | `orbitai/materials/ai_client.py` | 不改变供应商配置 |
| `orbitai/ai_processor.py` | `orbitai/materials/ai_processor.py` | 不改变提示词和写回字段 |
| `orbitai/scoring.py` | `orbitai/materials/scoring.py` | 不调整评分公式 |
| `orbitai/data_utils.py` | `orbitai/materials/fields.py` | 只迁移活动字段函数；旧 JSON 函数待对账后清退 |
| `orbitai/catalog_repository.py` | `orbitai/catalog/repository.py` | 保持通用赛道查询规则 |
| `orbitai/catalog_service.py` | `orbitai/catalog/service.py` | 不硬编码试点赛道 ID |
| `orbitai/catalog_import.py` | `orbitai/catalog/import_service.py` | 根模块保留 CLI 包装 |
| `orbitai/html_generator.py` | `orbitai/web/view_helpers.py` + 临时静态生成模块 | 先分离展示函数，再退役生成器 |
| `app.py` | 根入口 + `orbitai/web/app.py` + `routes/*` | 先移动路由，后切换首页 |
| `templates/industry_catalog.html` | `templates/dossier/industry_catalog.html` | 保持当前工程验证页外观 |
| `templates/feed.html`、`daily.html` | `templates/materials/` | 保持信息流行为 |
| `templates/status.html` | `templates/admin/status.html` | 管理操作进入管理端 |
| `static/style.css` | 三个职责目录中的样式 | 先机械拆分，不做视觉重设计 |
| `static/app.js` | `static/materials/` 与 `static/admin/` | 按页面实际使用拆分 |
| `data/catalog/*.json` | `data/seeds/catalog/` | 更新导入默认路径和文档 |
| `sources.json`、`sources.v4.json` | `data/registries/` | 分别保留抓取配置和研究来源注册表语义 |
| `orbitai.db` | `var/orbitai.db` | 通过备份、校验、切换完成，不直接移动活动文件 |
| `snapshots/` | `var/snapshots/` | 在退役前只改变输出位置 |
| `data.json` | `data/archive/data.json` | 对账后归档，继续保持 Git 忽略 |

`orbitai/models.py` 当前为空。确认没有导入方后删除，不迁移成新的空模块。

## 7. 路由契约草案

路由切换属于产品可见行为，需要在执行对应阶段前由用户确认。

### 7.1 推荐的新主入口

- `/`：推荐使用 HTTP 307 临时重定向进入 `/industries/artificial-intelligence`，让产业目录成为默认入口，同时保持产业页面只有一个规范地址。
- `/industries/{industry_slug}`：保持不变。
- `/materials`：原“全部信息”页面，重新定位为材料收件箱。
- `/materials/featured`：原精选信息页。
- `/materials/daily`：原每日简报页。
- `/admin/status`：原状态页和后台操作面板。

当前产业目录仍是工程验证页。把它设为默认入口不代表执行最终 V4 视觉设计。

### 7.2 第一轮保持不变的接口

- `POST /admin/fetch`
- `POST /admin/process-ai`
- `POST /admin/regenerate`，仅保留到静态快照退役阶段
- `GET /api/items`
- `GET /api/featured`
- `GET /api/daily`
- `GET /api/status`
- `GET /api/top`
- `GET /health`

### 7.3 临时兼容路由

- `/index.html` -> `/materials`
- `/featured`、`/featured.html` -> `/materials/featured`
- `/daily`、`/daily.html` -> `/materials/daily`
- `/status` -> `/admin/status`

兼容路由至少保留到仓库内模板、测试、README 和指南全部更新，并完成一次完整验收。删除兼容路由必须另经用户确认。

## 8. 分阶段行动

### 阶段 0：保护现场与冻结基线

#### 目标

在任何批量移动前，让当前 V4.1 成果可恢复、数据库可恢复、行为可比较。

#### 操作

1. 审查当前全部已跟踪和未跟踪改动，确认它们确实属于待保留的 V4.1 成果。
2. 运行当前测试、迁移状态和名册只读预览。
3. 记录当前路由列表、关键页面状态码和关键数据库表数量。
4. 经用户明确同意后，从当前 `main` 创建并切换到 `codex/project-structure-refactor` 分支；工作区改动必须完整保留。
5. 在重构分支审查并提交当前 V4.1 状态，形成重构前 Git 检查点，不把检查点提交直接落在 `main`。
6. 使用 SQLite Backup API 生成带时间戳的备份，不使用普通文件复制替代活动数据库备份。
7. 对备份运行 `PRAGMA integrity_check`，核对迁移版本和关键表行数。

#### 验证

```powershell
python -m unittest discover -s tests -v
python -m orbitai.migrations status
python -m orbitai.catalog_import preview --summary-only
```

补充记录：

- `articles`、`documents`、`events`、`industries`、`segments`、`organizations`、`people` 行数。
- 当前 FastAPI 路由集合。
- `/`、`/industries/artificial-intelligence`、`/status`、`/api/status`、`/health` 的状态码。

#### 退出标准

- 当前代码已有可识别的 Git 检查点。
- SQLite 备份已通过完整性和行数校验。
- 基线报告足以比较重构后的行为。

#### 回滚

本阶段不改业务代码。若备份或检查点未验证成功，停止重构。

### 阶段 1：建立包骨架与集中路径

执行状态：**已于 2026-07-17 完成。** `core` 活动实现、旧模块兼容包装、职责包骨架、绝对项目路径和聚焦测试均已落地；数据库、种子、页面资源与路由没有移动或切换。执行证据见 `docs/PROJECT_STRUCTURE_REFACTOR_STAGE1.md`。

#### 目标

建立新职责目录，但暂不改变路由、页面、数据库位置和业务行为。

#### 操作

1. 创建 `orbitai/core/`、`materials/`、`catalog/`、`web/routes/` 包。
2. 先将配置和项目路径解析集中到 `orbitai/core/config.py`。
3. 所有路径基于项目根目录解析，不能依赖启动命令的当前工作目录。
4. 保留现有根模块兼容转发，使当前导入和 CLI 暂时继续工作。
5. 为新旧导入路径增加聚焦测试。

#### 验证

- 从项目根目录运行全部测试。
- 从另一个当前工作目录导入配置，确认仍解析到同一项目路径。
- `python -m orbitai.migrations status` 和名册预览继续可用。
- `uvicorn app:app` 的导入检查通过。

#### 退出标准

- 新包可导入。
- 旧入口仍可导入。
- 没有数据文件移动，没有路由变化。

#### 回滚

回退本阶段提交即可；没有数据回滚。

### 阶段 2：拆分 Web 路由、模板和静态资源

#### 目标

解除产业目录对旧信息流 `base.html` 和单体 `style.css` 的结构依赖，同时保持当前视觉和业务行为。

#### 操作

1. 将 FastAPI 组装迁入 `orbitai/web/app.py`，根 `app.py` 只导出 `app`。
2. 按 `dossier`、`materials`、`admin`、`api` 拆分路由。
3. 建立三套模板边界；允许复制少量现有样式作为过渡，但禁止顺便重设计。
4. 按页面实际使用拆分 CSS 和 JavaScript。
5. 先保持现有 URL 和输出，再为新 URL 增加路由测试。
6. 用户确认后再切换 `/`，并启用临时兼容重定向。

#### 验证

- 路由契约测试覆盖新旧 URL、状态码和重定向目标。
- 产业目录继续显示四大分组、26 个赛道和通用的“已建设/待建设”判断。
- 材料页的筛选、排序、详情展开和管理操作仍可用。
- API JSON 的关键字段和排序不变。
- 全部测试通过。

#### 退出标准

- 根 `app.py` 只负责启动和导出。
- 三类页面不再共享一个承担全部职责的模板外壳。
- 新旧路由行为有自动化测试保护。

#### 回滚

恢复旧 `app.py` 组装和旧模板引用；数据库不受影响。

### 阶段 3：材料与目录模块归位

#### 目标

把活动业务代码迁入按职责命名的包，停止以 V3/V4 区分活动模块。

#### 操作

1. 迁移文章仓储、RSS、AI、评分和活动文章字段函数到 `materials/`。
2. 迁移目录导入、仓储和服务到 `catalog/`。
3. 将展示字段函数从静态 HTML 生成器中拆到 `web/view_helpers.py`。
4. 保留旧模块的薄兼容包装，并记录每个包装的调用方。
5. 更新应用内部导入，禁止新增代码继续引用旧实现路径。
6. 不在移动过程中改 SQL、提示词、评分公式或目录状态判断。

#### 验证

- 全部现有测试通过。
- 新增材料仓储、配置路径和导入兼容测试。
- 搜索确认活动实现只存在一份。
- RSS 只读来源加载可用；涉及网络抓取和 AI 调用时不在测试中产生外部副作用。
- 名册预览输出和写入保护逻辑不变。

#### 退出标准

- 活动代码已经从旧扁平模块迁入职责包。
- 旧路径只剩可枚举的薄包装。
- `app.py` 和 `main.py` 不直接拼装底层业务细节。

#### 回滚

旧包装仍在，因此可恢复旧内部导入；数据库不受影响。

### 阶段 4：运行数据和配置文件归位

#### 目标

把版本控制资产与本地运行资产分开，并确保路径切换不会创建错误的空数据库。

#### 操作

1. 将名册种子移动到 `data/seeds/catalog/`。
2. 将 `sources.json` 与 `sources.v4.json` 移动到 `data/registries/`。
3. 更新统一路径配置、CLI 默认值、测试和文档。
4. 再次对根 `orbitai.db` 使用 SQLite Backup API，生成 `var/backups/` 备份。
5. 通过 SQLite Backup API 创建并校验 `var/orbitai.db`。
6. 校验通过后一次性切换活动数据库路径；不双写。
7. 根数据库暂时只读保留，直到完整验收和用户确认删除。
8. 对 `data.json` 执行字段级对账，生成对账报告后归档到 `data/archive/data.json`。
9. 静态快照尚未退役时，将输出位置切换到 `var/snapshots/`。
10. 在 `.gitignore` 中显式忽略 `var/`，并保持归档 JSON 和数据库不被误提交。

#### 数据库切换校验

- `PRAGMA integrity_check` 返回 `ok`。
- `schema_migrations` 版本集合一致。
- 关键表行数一致。
- 56 个旧 JSON 链接仍全部可在新数据库中找到。
- 名册预览结果与切换前一致。
- 应用访问产业目录和材料页时使用 `var/orbitai.db`。

#### 防错要求

- 如果新数据库不存在，普通页面访问不能静默创建一个空数据库并掩盖路径错误。
- 只有迁移或显式初始化命令可以创建新的正式数据库。
- 测试继续使用显式临时数据库，不能碰正式 `var/orbitai.db`。

#### 退出标准

- 运行数据位于 `var/`，版本控制资产位于 `data/`。
- 所有默认路径只有一个集中定义。
- 根数据库和旧 JSON 尚未删除，但不再被活动代码写入。

#### 回滚

停止应用，将配置切回根数据库；根数据库在本阶段结束前不得删除或修改。

### 阶段 5：退役静态快照与旧兼容实现

#### 目标

删除已经没有调用方的静态生成、旧 JSON 读写和重复兼容代码。

#### 前置条件

- 阶段 0 至 4 全部验收通过。
- 已确认没有部署或人工流程依赖 `snapshots/*.html`。
- 仓库内没有活动引用指向 `/admin/regenerate`、静态生成函数、旧 JSON 读写函数或待删除模块。
- 用户明确同意执行清退。

#### 操作

1. 从 `python main.py` 完整流程中移除静态生成步骤，并更新其输出说明。
2. 删除 `/admin/regenerate` 和管理页对应按钮。
3. 删除静态 HTML 生成实现，只保留仍被动态页面使用的展示函数。
4. 删除未引用的 `load_existing_data()`、`save_data()` 和旧 JSON 兼容函数。
5. 删除空的 `orbitai/models.py`。
6. 在确认所有内部导入更新后，删除不再需要的旧模块包装。
7. 是否删除根数据库、旧快照和兼容路由分别再次取得用户确认。

#### 验证

- `python main.py` 的新语义有测试或明确的手动验证记录。
- 页面和 API 不再导入静态生成模块。
- 全仓库引用检查没有指向已删除符号和路径。
- 全部测试通过。
- 本地应用关键路径手动验收通过。

#### 退出标准

- 活动代码中没有 data.json 读写和静态 HTML 生成链路。
- 旧信息流已明确成为材料收件箱，不再是默认产品首页。
- 兼容层只保留仍经确认需要的部分。

#### 回滚

恢复本阶段提交；如需恢复静态输出，可从 Git 检查点恢复代码并从数据库重新生成。

### 阶段 6：测试、文档和指南归位

#### 目标

让代码结构、测试结构和项目说明保持一致，避免重构完成后指南继续描述旧路径。

#### 操作

1. 按 `materials`、`catalog`、`migrations`、`acceptance` 整理测试。
2. 文档移动单独执行，不与代码模块移动混在同一提交。
3. 暂定文档归类：
   - `docs/product/`：产品目标、路线图、页面长期方向、信息战略。
   - `docs/specs/`：V4.1 名册、产业档案、来源注册表等实现规格。
   - `docs/guides/`：导入、页面和运行操作指南。
   - `docs/decisions/`：审核记录、经确认的结构决策和退出记录。
   - `docs/archive/`：已失效但仍有历史价值的说明。
4. 修复 README、`AGENTS.md`、所有文档中的路径和命令链接。
5. 将本行动草案的状态更新为实际结果：已确认部分进入决策记录，未执行部分继续标记为草案。
6. 记录兼容层清单和剩余技术债。

#### 验证

```powershell
python -m compileall app.py main.py orbitai
python -m unittest discover -s tests -v
python -m orbitai.migrations status
python -m orbitai.catalog_import preview --summary-only
```

还需检查：

- README 中的目录树和启动方式准确。
- `AGENTS.md` 中的技术基线、验证命令、数据路径和模块说明准确。
- 文档内部没有指向已移动文件的失效链接。
- Git 状态中没有误提交数据库、备份、快照、`.env` 或缓存。

#### 退出标准

- 文档和代码描述一致。
- 所有自动验证通过。
- 已记录一次本地应用行为验收。
- 用户确认本轮项目结构重构完成。

## 9. 提交与检查点策略

建议每个阶段至少形成一个独立提交，避免一次提交混合大量移动、逻辑修改和数据路径切换。推荐顺序：

1. `checkpoint: preserve confirmed V4.1 baseline`
2. `refactor: add responsibility-based package boundaries`
3. `refactor: split web routes and presentation assets`
4. `refactor: move materials and catalog implementations`
5. `refactor: centralize runtime data paths`
6. `refactor: retire static snapshot compatibility`
7. `docs: align project guides with the new structure`

这些只是提交范围建议，不代表已经获得提交、建分支或删除文件的授权。每个涉及用户现有改动或破坏性清退的步骤都要单独确认。

## 10. 全局完成标准

只有同时满足以下条件，本轮重构才算完成：

- `app.py` 和 `main.py` 已成为薄入口。
- `core`、`materials`、`catalog`、`web` 的职责边界清晰，活动实现没有重复副本。
- 产业目录成为默认产品入口，材料收件箱和管理端有独立入口。
- V4 工程验证页没有被误改成未经确认的最终视觉方案。
- SQLite、名册种子、来源注册表、备份和归档路径清晰且可恢复。
- 迁移历史和 `documents -> articles` 追溯关系保持完整。
- 静态快照和旧 JSON 链路仅在满足清退条件后删除。
- 全部自动测试、迁移状态、名册预览和本地关键路径验收通过。
- README、`AGENTS.md` 和相关文档准确反映新结构。
- Git 中没有密钥、正式数据库、备份或生成快照。

## 11. 用户确认门槛

本计划设置四次明确确认：

1. **计划确认（已完成，2026-07-17）**：用户已确认本文件成为本轮重构的正式行动依据。
2. **检查点确认（已完成，2026-07-17）**：用户已授权；`codex/project-structure-refactor` 分支、重构前 Git 检查点和经验证的 SQLite Backup API 备份已经建立。
3. **行为切换确认**：授权切换默认首页和正式数据库路径。
4. **清退确认**：授权删除旧静态链路、兼容包装、根数据库副本和旧路由。

在第 1 次确认前不开始移动代码；在后续确认前，可以完成对应门槛之前的只读审查和非破坏性准备，但不能越过门槛执行破坏性操作。
