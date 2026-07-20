# OrbitAI 文档索引

本目录按文档职责组织。新增文档时先判断它是在说明“为什么做”“准备怎样做”“如何操作”“已经确认了什么”，还是仅保留失效历史，再选择对应目录。

## 产品方向 `product/`

- `product/PROJECT_GOALS.md`：产品愿景与战略背景。
- `product/ORBITAI_ROADMAP.md`：已确认的总体路线图和阶段依赖。
- `product/V4_INFORMATION_STRATEGY.md`：V4 材料、来源、事件与观点的角色关系。
- `product/V4_PRODUCT_PAGE_VISION.md`：V4 用户页面长期方向。

## 实现规格 `specs/`

- `specs/V4_INDUSTRY_DOSSIER_SPEC.md`：动态产业档案分阶段实现规格。
- `specs/V4_1_CATALOG_SPEC.md`：V4.1 产业与参与者名册规格。
- `specs/V4_SOURCE_REGISTRY.md`：信息源注册表模型与规则。

规格文件可以同时包含“已确认”和“仍为草案”的部分；以文件自身状态说明为准，不能仅因位于 `specs/` 就视为全部已确认。

## 操作指南 `guides/`

- `guides/V4_1_CATALOG_IMPORT_GUIDE.md`：名册预览、审核和显式写入流程。
- `guides/V4_1_CATALOG_PAGE_GUIDE.md`：首个产业目录工程验证页说明。
- `guides/V4_DOSSIER_READER_SHELL_GUIDE.md`：三个固定入口、赛道下钻与阅读端模板骨架说明。
- `guides/V4_1_CATALOG_ADMIN_GUIDE.md`：最小名册管理、冲突检测、事务保存和修改记录说明。

## 审核与决策 `decisions/`

- `decisions/V4_1_CATALOG_REVIEW_CHECKLIST.md`：首批名册中文审核与授权记录。
- `decisions/PROJECT_STRUCTURE_REFACTOR_PLAN.md`：本轮项目结构重构的正式行动依据和实际状态。
- `decisions/PROJECT_STRUCTURE_REFACTOR_BASELINE.md`：阶段 0 基线。
- `decisions/PROJECT_STRUCTURE_REFACTOR_STAGE1.md` 至 `decisions/PROJECT_STRUCTURE_REFACTOR_STAGE6.md`：各阶段执行与退出记录。
- `decisions/PROJECT_STRUCTURE_REFACTOR_STAGE4_DATA_RECONCILIATION.md`：旧 JSON 与 SQLite 字段级对账。

决策记录保留发生时的背景和边界；路径引用会维护为当前可访问位置，但不把历史状态改写成当时已经完成。

## 历史归档 `archive/`

归档准入规则见 `archive/README.md`。当前没有被判定为“已经失效但仍有历史价值”的业务文档；较早但仍具决策证据价值的文件继续留在 `decisions/`。

## 维护规则

- 面向项目的文档默认使用简体中文。
- 产品方向、实现规格和路线范围发生持久变化时，同步检查根 `AGENTS.md`。
- 移动或重命名文档后，必须修复 README、AGENTS、代码注释和全部 Markdown 引用。
- 代理起草但尚未经用户确认的范围或产品方案，必须继续标记为草案。
