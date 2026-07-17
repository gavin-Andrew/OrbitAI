# OrbitAI 项目结构重构阶段 4 执行记录

类别：结构重构决策记录

状态：**阶段 4 已完成。**

日期：2026-07-17

对应计划：`docs/decisions/PROJECT_STRUCTURE_REFACTOR_PLAN.md`

阶段 3 检查点：`5c5ac0a6215695da92f6cb192f448799d68e3988`

## 1. 本阶段目标

把版本控制配置与本地运行数据分开，通过可验证、可回滚的一次性切换让 `var/orbitai.db` 成为唯一活动数据库，并防止路径错误时普通页面静默创建空库。

用户在被明确告知阶段 4 包含正式数据库路径切换、但不包含删除根数据库后，同意进入本阶段。

## 2. 当前路径

```text
data/
├─ seeds/catalog/foundation_models.v4.1.json
├─ registries/sources.json
├─ registries/sources.v4.json
└─ archive/data.json                    # Git 忽略
var/                                    # 整体 Git 忽略
├─ orbitai.db                           # 唯一活动数据库
├─ backups/
│  ├─ orbitai-phase0-20260717-120708.db
│  └─ orbitai-phase4-20260717-144719.db
└─ snapshots/
   ├─ index.html
   ├─ featured.html
   └─ daily.html
```

根 `orbitai.db` 没有删除，已设置为只读保留副本。应用、CLI 默认值和静态快照输出均不再使用旧根路径。

## 3. SQLite Backup API 切换

阶段 4 没有直接移动活动数据库文件，而是从只读打开的根数据库分别通过 `sqlite3.Connection.backup()` 创建：

- 阶段备份：`var/backups/orbitai-phase4-20260717-144719.db`
- 候选活动库：`var/orbitai.db`

三个数据库的逻辑校验结果完全一致：

- `PRAGMA integrity_check`：`ok`
- 迁移版本：`0001` 至 `0005`
- 文件长度：552960 字节
- `articles`：156
- `industries`：1
- `segments`：26
- `organizations`：6
- `people`：6
- `sources`：13
- 其余表行数也逐表一致

文件哈希：

- 根只读副本：`a47e57cd8d76b549b3c3499301421e781d6170145ffecc4e90f04c1aaf77c013`
- 阶段 4 备份：`b30633f451ba59e07ed2101663984db89fb9e73973c61c2f120c14b59d197f09`
- 当前活动库：`b30633f451ba59e07ed2101663984db89fb9e73973c61c2f120c14b59d197f09`

Backup API 生成文件的物理哈希可以不同于源文件；完整性、迁移集合和逐表行数才是切换一致性依据。

## 4. 旧 JSON 与快照归位

旧 JSON 已完成链接和 1008 个字段值的对账，详见 `docs/decisions/PROJECT_STRUCTURE_REFACTOR_STAGE4_DATA_RECONCILIATION.md`。它保留 SQLite 中没有的逐维评分和处理时间，因此只是从根目录移动到 `data/archive/data.json`，没有删除。

三个现有静态快照移动前后哈希一致：

- `var/snapshots/index.html`：`ea65609ce65ad023a8111b366310b82c589c35b88c7845f953ac7045c6c4b367`
- `var/snapshots/featured.html`：`97677556d1e65d65464d6145a7efbd83a1b54c8f511917919d36c4d3891eeea6`
- `var/snapshots/daily.html`：`8a550ce7529325a657dff7f7030fd9318db511400ac8a1e1de49ea5435883cd5`

静态生成实现仍然保留，但后续输出只写入 `var/snapshots/`。

## 5. 防错与忽略规则

- `orbitai/core/config.py` 集中定义 `data/` 和 `var/` 全部活动路径。
- `get_connection()` 默认拒绝连接不存在的数据库，避免 SQLite 隐式创建空文件。
- 材料仓储和产业目录页面使用 `allow_create=False`，路径错误时明确失败。
- 只有显式 `init_db()`、迁移命令或名册 apply 流程可以创建数据库。
- `.gitignore` 显式忽略 `var/` 与 `data/archive/data.json`，并继续兼容忽略旧根位置。

## 6. 自动化保护

新增测试现位于 `tests/acceptance/test_runtime_paths.py`，覆盖：

- 运行数据与版本控制配置的集中路径。
- 普通连接拒绝创建缺失数据库。
- 显式初始化仍可在临时目录创建数据库并应用全部迁移。
- 材料仓储在活动数据库缺失时拒绝创建空库。
- 三份移动后的版本控制 JSON 可以正常读取。

原有目录、迁移、Web 和模块边界测试继续通过，测试数据库均使用显式临时路径。

## 7. 阶段边界

本阶段没有：

- 删除或覆盖根 `orbitai.db`。
- 删除 `data/archive/data.json` 或旧静态快照内容。
- 修改数据库业务模型、RSS、AI、评分或目录查询逻辑。
- 执行名册 apply、网络抓取、AI 调用或静态重新生成。
- 删除旧导入包装、静态生成器、兼容路由或管理入口。
- 改变 V4 单赛道范围或重设计产业目录工程验证页。

## 8. 验证结果

```powershell
python -m compileall app.py main.py orbitai
python -m unittest discover -s tests -v
python -m orbitai.migrations status
python -m orbitai.catalog_import preview --summary-only
```

结果：

- 41 项测试全部通过，其中阶段 4 新增 5 项运行路径测试。
- 迁移 `0001` 至 `0005` 状态正常。
- 名册预览为校验错误 0、已知警告 2、124 条 `unchanged`、阻塞项 0、`applied=false`。
- `/`、产业目录、材料页、管理页、API 和健康检查契约保持通过。
- 正式活动数据库在全部验证前后均为 `var/orbitai.db`，根数据库哈希和只读属性保持不变。

下一阶段是需要清退确认的阶段 5。阶段 4 的授权不包含删除旧静态链路、兼容包装、根数据库副本、旧路由或旧 JSON 归档。
