# OrbitAI 项目结构重构阶段 1 执行记录

类别：结构重构决策记录

状态：**阶段 1 已完成。** 提交本记录的 Git 提交是阶段 1 检查点。

日期：2026-07-17

对应计划：`docs/decisions/PROJECT_STRUCTURE_REFACTOR_PLAN.md`

阶段 0 检查点：`53701fcae7e70fa4a092435ad047692d6ab40b41`

## 1. 本阶段目标

建立按职责组织的 Python 包边界，把配置、数据库和迁移实现归入 `orbitai/core/`，并让所有当前项目路径基于项目根目录解析。同时保留旧导入路径与迁移 CLI，不改变路由、页面、数据位置或业务逻辑。

## 2. 已完成的结构

```text
orbitai/
├─ core/
│  ├─ __init__.py
│  ├─ config.py
│  ├─ database.py
│  └─ migrations.py
├─ materials/
│  └─ __init__.py
├─ catalog/
│  └─ __init__.py
├─ web/
│  ├─ __init__.py
│  └─ routes/
│     └─ __init__.py
├─ config.py             # 兼容包装
├─ database.py           # 兼容包装
└─ migrations.py         # 兼容包装和旧 CLI
```

`orbitai/events/` 没有创建。它仍属于 V4.2，只有事件实现规格确认并开始开发时才建立。

`materials`、`catalog` 和 `web/routes` 本阶段只建立包边界；现有材料、目录和路由业务实现尚未迁入，不能把包骨架解释为后续阶段已经完成。

## 3. 集中路径配置

`orbitai/core/config.py` 现在集中定义：

- `PROJECT_ROOT`
- `ENV_FILE`
- `DATA_DIR` 与当前 `CATALOG_DATA_DIR`
- `TEMPLATES_DIR` 与 `STATIC_DIR`
- `DATA_FILE`
- `DATABASE_FILE`
- `SNAPSHOT_DIR` 及三个静态输出文件
- `SOURCES_FILE`
- `SOURCE_REGISTRY_FILE`
- `CATALOG_SEED_FILE`

所有路径均由 `Path(__file__).resolve()` 推导项目根目录，不依赖进程启动时的当前工作目录。`.env` 也明确从项目根目录读取。

阶段 1 只集中路径，当前实际位置仍然是：

- 数据库：根目录 `orbitai.db`
- 旧 JSON：根目录 `data.json`
- 快照：根目录 `snapshots/`
- RSS 来源：根目录 `sources.json`
- V4 来源注册表：根目录 `sources.v4.json`
- V4.1 名册种子：`data/catalog/foundation_models.v4.1.json`
- 模板：根目录 `templates/`
- 静态资源：根目录 `static/`

运行数据迁移到 `var/` 和配置文件迁移到新 `data/` 子目录仍属于阶段 4。

## 4. 活动实现与兼容入口

活动实现：

- `orbitai/core/config.py`
- `orbitai/core/database.py`
- `orbitai/core/migrations.py`

兼容入口：

- `orbitai/config.py` 转发到 `orbitai.core.config`。
- `orbitai/database.py` 转发到 `orbitai.core.database`。
- `orbitai/migrations.py` 转发迁移公共 API，并继续支持 `python -m orbitai.migrations`。

新活动代码已经改为直接导入 `orbitai.core`。现有测试继续通过旧模块导入数据库和迁移 API，用来持续证明兼容包装仍然有效。

目录导入 CLI 的三个默认路径已经改为引用集中配置：

- `DEFAULT_DATABASE_FILE`
- `DEFAULT_SEED_FILE`
- `DEFAULT_SOURCE_REGISTRY_FILE`

根 `app.py` 仍保留全部路由，只将 `StaticFiles` 和 `Jinja2Templates` 改为使用集中定义的绝对目录。

## 5. 新增测试

新增测试现位于 `tests/acceptance/test_core_paths.py`，包含 5 项测试：

1. 当前项目路径全部为绝对路径并与实际位置一致。
2. 旧模块导出与 `core` 活动实现是同一对象。
3. 名册 CLI 默认文件来自集中配置。
4. 从项目外的当前工作目录导入 `app` 仍能找到模板、静态资源和数据库路径。
5. `orbitai.migrations` 与 `orbitai.core.migrations` 两个 CLI 都能从其他工作目录运行。

## 6. 验证结果

### 6.1 语法与导入

```powershell
python -m compileall app.py main.py orbitai
```

结果：通过。

### 6.2 全部测试

```powershell
python -m unittest discover -s tests -v
```

结果：26 项测试全部通过，包含阶段 0 的 21 项测试和阶段 1 新增的 5 项测试。

仍有一条 FastAPI TestClient 所依赖的 Starlette/httpx 第三方弃用警告，不影响结果。

### 6.3 迁移 CLI

以下两个命令输出一致，均显示迁移 `0001` 至 `0005`：

```powershell
python -m orbitai.migrations status
python -m orbitai.core.migrations status
```

### 6.4 名册只读预览

```powershell
python -m orbitai.catalog_import preview --summary-only
```

结果：

- 校验错误 0。
- 已知警告 2。
- 124 条操作全部为 `unchanged`。
- 阻塞项 0。
- `applied=false`。

### 6.5 路由行为

- 阶段 0 记录的 17 条业务路由全部存在。
- 没有缺失路由，没有新增意外路由。
- `/`：200。
- `/industries/artificial-intelligence`：200。
- 未知产业：404。
- `/status`：200。
- `/api/status`：200。
- `/health`：200。

### 6.6 正式数据库保护

- 阶段 1 前后正式数据库 SHA-256 均为 `a47e57cd8d76b549b3c3499301421e781d6170145ffecc4e90f04c1aaf77c013`。
- 本阶段没有移动、写入或切换正式数据库。
- 阶段 0 备份继续保存在 `var/backups/` 并受 Git 忽略规则保护。

## 7. 文档同步

- `AGENTS.md` 已更新当前 core 活动实现、兼容包装、目标包边界和聚焦验证命令。
- `README.md` 已更新阶段 1 核心目录树和路径兼容测试命令。
- 重构行动计划已标记阶段 1 完成。

## 8. 阶段边界

本阶段没有执行以下工作：

- 没有拆分 `app.py` 路由。
- 没有移动模板和静态资源。
- 没有把目录业务实现迁入 `orbitai/catalog/`。
- 没有把材料业务实现迁入 `orbitai/materials/`。
- 没有移动数据库、快照、来源配置或名册种子。
- 没有切换默认首页。
- 没有删除任何兼容模块或旧功能。

下一阶段按正式计划进入 Web 路由、模板和静态资源边界拆分；默认首页切换仍须遵守单独的行为切换确认门槛。
