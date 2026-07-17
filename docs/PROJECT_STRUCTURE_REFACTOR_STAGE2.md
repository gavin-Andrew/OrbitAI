# OrbitAI 项目结构重构阶段 2 执行记录

状态：**阶段 2-A 行为等价拆分已完成；阶段 2-B 行为切换待用户确认。**

日期：2026-07-17

对应计划：`docs/PROJECT_STRUCTURE_REFACTOR_PLAN.md`

阶段 1 检查点：`3222e67a77b17fdb8d29a8536d08a8332fa2f4a2`

## 1. 本阶段目标

把根 `app.py`、单层模板目录和单体静态资源拆成清晰的 Web 职责边界，同时保持当前页面内容、旧 URL、API 和管理操作契约。产业目录继续是 V4.1-C 工程验证页，本阶段没有进行最终 V4 视觉重设计。

## 2. 已完成的 Web 边界

```text
app.py                              # 薄兼容启动入口
orbitai/web/
├─ app.py                           # FastAPI 应用组装
├─ templating.py                    # 集中模板环境
├─ view_helpers.py                  # 动态页面展示辅助函数
└─ routes/
   ├─ dossier.py                    # 产业档案阅读端
   ├─ materials.py                  # 信息材料页
   ├─ admin.py                      # 状态页与本地操作
   └─ api.py                        # JSON API 与健康检查
templates/
├─ dossier/
├─ materials/
└─ admin/
static/
├─ shared/
├─ dossier/
├─ materials/
└─ admin/
```

根 `app.py` 只从 `orbitai.web.app` 导出 `app` 和 `create_app`，因此 `uvicorn app:app --reload` 的启动契约保持不变。

## 3. 模板与静态资源拆分

- 材料页使用 `templates/materials/`、`static/materials/` 和共享基础样式。
- 产业目录使用独立的 `templates/dossier/base.html` 与 `static/dossier/style.css`，不再继承材料页模板，也不再依赖承载全部页面职责的单体 CSS。
- 状态与管理操作页使用 `templates/admin/`、`static/admin/style.css` 和独立管理脚本。
- 原 `static/app.js` 已按材料交互和管理操作拆开。
- 原 `static/style.css` 已按共享基础、材料、产业档案和管理边界机械拆分；没有借机调整视觉方向。

## 4. 当前路由状态

当前保留全部 17 条重构前业务路由，并增加四个模块化页面地址：

- `/materials`
- `/materials/featured`
- `/materials/daily`
- `/admin/status`

现阶段新旧地址都直接渲染同一页面逻辑。`/` 仍是原信息流首页；`/index.html`、`/featured`、`/featured.html`、`/daily`、`/daily.html` 和 `/status` 尚未改为重定向。

以下行为属于阶段 2-B，必须取得行为切换确认后执行：

- `/` 临时重定向到 `/industries/artificial-intelligence`。
- 旧材料和状态地址重定向到新的 `/materials/*` 与 `/admin/status` 规范地址。

## 5. 自动化保护

新增 `tests/test_web_structure.py`，覆盖：

- 17 条旧业务路由与 4 条新页面路由的完整集合。
- 新旧材料地址继续返回页面，并加载共享与材料资源。
- `/status` 与 `/admin/status` 都加载管理端资源。
- 六个分层 CSS/JavaScript 资源可访问，原单体资源地址不再存在。

`tests/test_catalog_page.py` 的测试桩已迁到新的 dossier 路由模块，并增加产业页资源边界断言；四大分组、26 个赛道、首批名册与通用“已建设/待建设”判断继续由原有聚焦测试保护。

## 6. 阶段边界

本阶段没有：

- 切换默认首页或启用旧 URL 重定向。
- 改动 SQLite 路径、表结构或业务数据。
- 迁移材料与目录业务模块到目标包。
- 改写 RSS、AI、评分、目录查询或 API 数据逻辑。
- 删除静态快照生成链路、兼容路由或旧模块包装。
- 把当前产业目录工程验证页重做成最终产品界面。

完成验证并形成阶段 2-A Git 检查点后，下一步是由用户决定是否执行阶段 2-B 的产品可见行为切换。

## 7. 验证结果

### 7.1 语法与导入

```powershell
python -m compileall app.py main.py orbitai
```

结果：通过。

### 7.2 全部测试

```powershell
python -m unittest discover -s tests -v
```

结果：30 项测试全部通过，其中阶段 2 新增 4 项 Web 结构测试。仍有一条 FastAPI TestClient 所依赖的 Starlette/httpx 第三方弃用警告，不影响测试结果。

### 7.3 迁移与名册预览

```powershell
python -m orbitai.migrations status
python -m orbitai.catalog_import preview --summary-only
```

结果：

- 迁移 `0001` 至 `0005` 状态正常。
- 名册校验错误 0、已知警告 2。
- 124 条预览操作全部为 `unchanged`，阻塞项 0，`applied=false`。

### 7.4 正式数据库保护

- 阶段 2-A 后正式数据库 SHA-256 仍为 `a47e57cd8d76b549b3c3499301421e781d6170145ffecc4e90f04c1aaf77c013`，与阶段 0、阶段 1 基线一致。
- 本阶段没有执行迁移升级、名册写入或数据库路径切换。
