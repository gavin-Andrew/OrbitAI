# OrbitAI 项目结构重构阶段 5 执行记录

类别：结构重构决策记录

状态：**阶段 5 的代码清退已完成；实物与 URL 清退项继续等待分别确认。**

日期：2026-07-17

对应计划：`docs/decisions/PROJECT_STRUCTURE_REFACTOR_PLAN.md`

阶段 4 检查点：`a9fe9a8f`

## 1. 本阶段目标与授权边界

本阶段退役没有活动调用方的静态 HTML 生成、旧 `data.json` 读写和临时导入包装，让动态 Web App 与 SQLite 成为唯一活动展示和数据路径。

用户明确同意进入阶段 5。正式计划同时要求根数据库、旧快照实物和兼容 URL 路由分别再次确认，因此本阶段没有删除这些对象；阶段 4 对账后必须保留的 `data/archive/data.json` 也没有删除。

## 2. 已退役的静态链路

- `python main.py` 现在只执行 RSS 抓取、SQLite 写入和 AI 处理，不再生成静态 HTML。
- `run_full_pipeline()` 的返回值不再包含 `regenerate`。
- `/admin/regenerate` 路由和管理页“重新生成静态 HTML”按钮已经删除。
- `orbitai/web/static_snapshots.py` 与旧入口 `orbitai/html_generator.py` 已删除。
- `orbitai/core/config.py` 不再暴露 `SNAPSHOT_DIR`、`HTML_FILE`、`FEATURED_FILE` 或 `DAILY_FILE` 等已退役输出常量。
- 动态材料页继续从 SQLite 读取并使用 Jinja2 渲染，规范 URL 未改变。

`main.py` 的控制台日志同时去除了会在 Windows GBK 终端触发 `UnicodeEncodeError` 的 emoji；抓取、AI、评分和数据库逻辑没有改变。

## 3. 已退役的旧 JSON 与兼容模块

删除了只剩兼容测试调用的：

- `orbitai/materials/legacy_json.py`
- `load_existing_data()`、`save_data()` 与旧 JSON `get_existing_links()`
- `orbitai/data_utils.py`

删除了已经没有仓库内调用方的旧扁平包装：

- `orbitai/config.py`
- `orbitai/database.py`
- `orbitai/repository.py`
- `orbitai/rss_fetcher.py`
- `orbitai/ai_client.py`
- `orbitai/ai_processor.py`
- `orbitai/scoring.py`
- `orbitai/catalog_repository.py`
- `orbitai/catalog_service.py`

空的 `orbitai/models.py` 也已删除。活动实现继续位于 `orbitai/core/`、`orbitai/materials/`、`orbitai/catalog/` 和 `orbitai/web/`。

## 4. 仍保留的稳定入口与历史实物

以下两个包装仍被 README、AGENTS 和操作指南用作正式命令入口，因此不是无调用方兼容代码：

- `python -m orbitai.migrations ...`
- `python -m orbitai.catalog_import ...`

它们只转发到活动实现，不承载业务逻辑，并有自动测试保护。

以下对象未获各自删除确认，继续保留：

- 根目录只读 `orbitai.db`。
- `data/archive/data.json` 历史对账归档。
- `var/snapshots/index.html`、`featured.html`、`daily.html` 三个历史文件。
- `/index.html`、`/featured`、`/featured.html`、`/daily`、`/daily.html`、`/status` 兼容 URL 路由。

三个快照文件已经没有读取或生成调用方；保留不代表仍受活动产品支持。

## 5. 自动化保护

- 新增 `tests/materials/test_main_pipeline.py`，确认完整材料流程只调用抓取和 AI 处理，并且不再返回静态生成结果。
- `tests/acceptance/test_module_boundaries.py` 改为确认 14 个退役模块不存在，活动实现不再导入旧路径，并保护两个稳定 CLI 包装。
- `tests/acceptance/test_web_structure.py` 确认 `/admin/regenerate` 不再暴露、管理页不再显示静态生成按钮，同时继续保护尚未清退的兼容 URL。
- 目录、迁移和核心路径测试改为直接导入活动实现。

## 6. 文档同步

README、`AGENTS.md`、路线图、项目目标与 V4.1 相关指南已经更新为当前模块路径和动态 Web 语义。历史阶段执行记录继续保留当时事实，没有回写成当前结构。

## 7. 验证结果

```powershell
python -m compileall app.py main.py orbitai
python -m unittest discover -s tests -v
python -m orbitai.migrations status
python -m orbitai.catalog_import preview --summary-only
```

结果：

- Python 编译检查通过。
- 41 项测试全部通过；仅有既存 Starlette/httpx 第三方弃用警告。
- 迁移 `0001` 至 `0005` 状态正常。
- 名册预览为校验错误 0、已知警告 2、124 条 `unchanged`、阻塞项 0、`applied=false`。
- 活动数据库 `PRAGMA integrity_check` 为 `ok`，`articles` 仍为 156。
- `/admin/regenerate` 不存在；六个材料/状态兼容 URL 仍存在。
- `var/snapshots/` 中三个历史 HTML 文件仍在，验证过程没有重写它们。
- 当前代码与非历史文档均没有指向已删除实现的活动引用。

## 8. 阶段边界

本阶段没有：

- 删除根数据库、旧 JSON 归档、历史快照文件或兼容 URL 路由。
- 修改数据库结构、迁移历史或业务数据。
- 执行 RSS 网络抓取、AI 调用或名册 apply。
- 修改评分公式、AI 提示词、目录查询规则或 V4 单赛道范围。
- 重设计当前产业目录工程验证页。
- 提前执行阶段 6 的测试目录与文档目录归位。

后续如要删除任何保留对象，应先逐项确认，并在操作前再次验证调用方与可恢复性。
