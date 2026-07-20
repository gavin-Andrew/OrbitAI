# OrbitAI 项目结构重构阶段 3 执行记录

类别：结构重构决策记录

状态：**阶段 3 已完成。**

日期：2026-07-17

对应计划：`docs/decisions/PROJECT_STRUCTURE_REFACTOR_PLAN.md`

阶段 2-B 检查点：`818b3d7624012ba178e9e8fdf3fd50cc0a8172d1`

## 1. 本阶段目标

把材料与产业目录的活动实现迁入按职责命名的包，停止让应用内部依赖旧扁平模块；同时把动态页面展示字段从静态 HTML 生成器中拆出。迁移只改变代码所有权和导入路径，不改 SQL、RSS 行为、AI 提示词、评分公式、目录状态规则或业务数据。

## 2. 材料模块归位

活动实现现在位于：

```text
orbitai/materials/
├─ fields.py          # 活动文章字段构造与兼容规范化
├─ repository.py      # articles 仓储与状态查询
├─ rss.py             # RSS 来源读取、重试与抓取
├─ ai_client.py       # AI 服务客户端
├─ ai_processor.py    # AI 处理与错误状态
├─ scoring.py         # 评分、排序与精选规则
└─ legacy_json.py     # 临时保留、等待阶段 5 清退的旧 JSON 读写
```

`main.py` 和 Web 路由已经直接导入这些活动模块。`load_existing_data()`、`save_data()` 与旧 JSON 链接去重函数没有活动调用方，现被隔离在 `legacy_json.py`，但本阶段没有越过清退确认删除它们。

## 3. 目录模块归位

活动实现现在位于：

```text
orbitai/catalog/
├─ repository.py       # 名册读写、目录查询和冲突保护
├─ service.py          # 产业目录页面数据组装
└─ import_service.py   # 种子校验、预览、显式事务写入与 CLI
```

应用路由和目录测试已经使用新路径。`python -m orbitai.catalog_import` 继续由兼容包装转发到新实现；`python -m orbitai.catalog.import_service` 也可直接运行。

## 4. 展示与静态生成解耦

- `orbitai/web/view_helpers.py` 现在拥有标题、摘要、分类、日期解析、今日筛选和动态模板上下文等展示辅助函数。
- `orbitai/web/static_snapshots.py` 只承载仍待退役的 `index.html`、`featured.html`、`daily.html` 静态快照生成。
- 动态 Web 路由只依赖 `view_helpers.py`，不再通过旧 `html_generator.py` 间接依赖静态生成代码。
- `main.py` 的静态兼容流程直接调用 `static_snapshots.py`，行为保持不变。

## 5. 兼容包装

以下旧模块只保留导入转发或 CLI 转发，不再承载活动实现：

- `orbitai/repository.py`
- `orbitai/rss_fetcher.py`
- `orbitai/ai_client.py`
- `orbitai/ai_processor.py`
- `orbitai/scoring.py`
- `orbitai/data_utils.py`
- `orbitai/catalog_repository.py`
- `orbitai/catalog_service.py`
- `orbitai/catalog_import.py`
- `orbitai/html_generator.py`

兼容包装的删除仍属于阶段 5，必须先完成调用方检查并取得清退确认。

## 6. 自动化保护

新增测试现位于 `tests/acceptance/test_module_boundaries.py`，覆盖：

- 材料旧路径与新活动实现导出同一对象。
- 目录旧路径与新活动实现导出同一对象。
- 动态展示辅助函数和静态快照生成函数具有不同的明确所有者。
- `main.py`、`materials`、`catalog`、`web` 活动代码没有导入旧扁平实现路径。
- 旧名册 CLI 与新活动 CLI 均可从项目外目录完成只读预览，且不会写入正式数据库。

现有目录测试已经改为直接导入 `orbitai.catalog` 活动实现；兼容行为由新的边界测试单独保护。

## 7. 阶段边界

本阶段没有：

- 修改数据库路径、表结构、迁移或业务数据。
- 修改 RSS 网络行为、AI 供应商配置、提示词或评分公式。
- 修改四大分组、26 个赛道和通用“已建设/待建设”规则。
- 删除旧 JSON 读写、静态快照生成、旧导入包装或管理端重新生成入口。
- 创建 V4.2 事件业务包或扩展单赛道试点范围。
- 重设计当前产业目录工程验证页。

下一阶段按正式计划进入运行数据和配置文件归位；正式数据库路径切换仍需单独获得用户授权。

## 8. 验证结果

### 8.1 语法与全部测试

```powershell
python -m compileall app.py main.py orbitai
python -m unittest discover -s tests -v
```

结果：36 项测试全部通过，其中阶段 3 新增 5 项模块边界测试。仍有一条 FastAPI TestClient 所依赖的 Starlette/httpx 第三方弃用警告，不影响测试结果。

### 8.2 迁移与名册预览

```powershell
python -m orbitai.migrations status
python -m orbitai.catalog_import preview --summary-only
python -m orbitai.catalog.import_service preview --summary-only
```

结果：迁移 `0001` 至 `0005` 状态正常；两个名册预览入口均为校验错误 0、已知警告 2、124 条 `unchanged`、阻塞项 0、`applied=false`。

### 8.3 正式数据库保护

正式数据库 SHA-256 仍为 `a47e57cd8d76b549b3c3499301421e781d6170145ffecc4e90f04c1aaf77c013`，与阶段 0 至阶段 2 基线一致。本阶段没有执行迁移升级、名册写入或数据库路径切换。
