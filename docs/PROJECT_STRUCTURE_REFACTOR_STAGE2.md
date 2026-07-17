# OrbitAI 项目结构重构阶段 2 执行记录

状态：**阶段 2 已完成。** 阶段 2-A 行为等价拆分和经用户确认的阶段 2-B 行为切换均已落地。

日期：2026-07-17

对应计划：`docs/PROJECT_STRUCTURE_REFACTOR_PLAN.md`

阶段 1 检查点：`3222e67a77b17fdb8d29a8536d08a8332fa2f4a2`

阶段 2-A 检查点：`83598df09bcbfa2039f90b93c969cbe5784af4fb`

## 1. 本阶段目标

把根 `app.py`、单层模板目录和单体静态资源拆成清晰的 Web 职责边界，先保持行为等价，再经用户确认切换默认入口和旧 URL。产业目录继续是 V4.1-C 工程验证页，本阶段没有进行最终 V4 视觉重设计。

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

当前保留全部 17 条重构前业务路由，并增加四个模块化页面地址。规范页面地址为：

- `/materials`
- `/materials/featured`
- `/materials/daily`
- `/admin/status`

用户于 2026-07-17 明确确认阶段 2-B 后，以下地址已改为 HTTP 307 临时重定向：

- `/` -> `/industries/artificial-intelligence`
- `/index.html` -> `/materials`
- `/featured`、`/featured.html` -> `/materials/featured`
- `/daily`、`/daily.html` -> `/materials/daily`
- `/status` -> `/admin/status`

模板导航已经全部改用规范地址。旧路由仍然存在，只改变响应为可回退的临时重定向；API 与三个管理 POST 路由保持不变。

## 5. 自动化保护

新增 `tests/test_web_structure.py`，覆盖：

- 17 条旧业务路由与 4 条新页面路由的完整集合。
- 三个规范材料地址继续返回页面，并加载共享与材料资源。
- `/admin/status` 加载管理端资源。
- `/` 与六个旧页面地址返回精确的 307 状态码和目标地址。
- 六个分层 CSS/JavaScript 资源可访问，原单体资源地址不再存在。

`tests/test_catalog_page.py` 的测试桩已迁到新的 dossier 路由模块，并增加产业页资源边界断言；四大分组、26 个赛道、首批名册与通用“已建设/待建设”判断继续由原有聚焦测试保护。

## 6. 阶段边界

本阶段没有：

- 改动 SQLite 路径、表结构或业务数据。
- 迁移材料与目录业务模块到目标包。
- 改写 RSS、AI、评分、目录查询或 API 数据逻辑。
- 删除静态快照生成链路、兼容路由或旧模块包装。
- 把当前产业目录工程验证页重做成最终产品界面。

阶段 2-B 只获得了 Web 行为切换授权，不包含阶段 4 的正式数据库路径切换授权。阶段 2 完成后，下一步按正式计划进入阶段 3 的材料与目录模块归位。

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

结果：31 项测试全部通过，其中阶段 2 包含 5 项 Web 结构测试。仍有一条 FastAPI TestClient 所依赖的 Starlette/httpx 第三方弃用警告，不影响测试结果。

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

- 阶段 2 完成后正式数据库 SHA-256 仍为 `a47e57cd8d76b549b3c3499301421e781d6170145ffecc4e90f04c1aaf77c013`，与阶段 0、阶段 1 基线一致。
- 本阶段没有执行迁移升级、名册写入或数据库路径切换。
