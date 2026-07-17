OrbitAI

OrbitAI 是一个本地优先的个人 AI 与硬科技产业研究系统。

项目已经正式进入 V4“可追溯的 AI 动态产业档案”的开发阶段。V3 的 RSS、AI 处理、SQLite 文章库和本地 Web App 继续作为信息材料基础；V4 将逐步加入产业、赛道、参与者、关键事件和原始来源之间的可追溯关系。总体路径见 `docs/ORBITAI_ROADMAP.md`，当前实现规格草案见 `docs/V4_INDUSTRY_DOSSIER_SPEC.md`。

它的目标是帮助用户持续收集、整理、浏览和管理 AI 及科技相关信息，避免被信息洪流淹没，同时保持完全可控、可观察的本地环境。

OrbitAI 强调：

小步迭代，易用且低复杂度。
本地运行：数据库 + 网页访问，无公网部署，无用户系统。
模块化与可扩展性：便于长期维护和功能扩展。
信息闭环：RSS 抓取 → 数据存储 → AI 处理 → 网页展示 → 状态监控。
核心功能
信息抓取：支持从多源 RSS 获取 AI/科技信息。
数据存储：本地 SQLite 数据库为主存储，保持历史信息备份。
AI 处理：
标题和摘要翻译（中英文）。
信息分类、标签提取。
多维度评分与综合分（final_score）。
本地 Web 页面：
/：全部信息。
/featured：精选信息。
/daily：每日新增信息简报。
/status：系统运行状态与错误监控。
后台手动操作：
RSS 抓取。
AI 批量处理。
静态 HTML 再生成。
API 接口：
/api/items
/api/featured
/api/daily
/api/status
/api/top
/health
稳定性机制：
RSS 请求重试。
AI 失败记录与 retry_count 控制。
高 retry_count 条目在状态页可视化标记。
安装与运行
安装依赖：
pip install -r requirements.txt
配置 .env 文件：
AI_PROVIDER=deepseek
AI_API_KEY=你的 DeepSeek Key
AI_BASE_URL=https://api.deepseek.com
AI_MODEL=deepseek-v4-flash
AI_BATCH_LIMIT=5
AI_INPUT_SUMMARY_MAX_CHARS=1800
启动本地服务：
uvicorn app:app --reload
浏览器访问：
http://127.0.0.1:8000

访问首页、精选页、每日简报及状态页。

数据库迁移：

```powershell
python -m orbitai.migrations status
python -m orbitai.migrations up
```

运行聚焦测试：

```powershell
python -m unittest discover -s tests -v
```

项目路径与兼容入口测试：

```powershell
python -m unittest tests.test_core_paths -v
```

项目结构（核心部分）
OrbitAI/
├─ app.py                     # 薄 FastAPI 兼容启动入口
├─ main.py                    # RSS + AI + SQLite 流程调度
├─ orbitai/                   # 功能模块
│  ├─ core/                   # 配置、数据库和迁移的活动实现
│  ├─ materials/              # 字段、仓储、RSS、AI 与评分活动实现
│  ├─ catalog/                # 名册导入、仓储与目录服务活动实现
│  ├─ web/app.py              # FastAPI 应用组装
│  ├─ web/view_helpers.py     # 动态页面展示辅助函数
│  ├─ web/static_snapshots.py # 临时保留的静态快照生成实现
│  ├─ web/routes/             # dossier/materials/admin/api 活动路由
│  ├─ config.py               # 旧导入兼容包装
│  ├─ database.py             # 旧导入兼容包装
│  ├─ migrations.py           # 旧导入与 CLI 兼容包装
│  ├─ data_utils.py           # 旧文章字段/JSON 导入兼容包装
│  ├─ rss_fetcher.py          # 旧 RSS 导入兼容包装
│  ├─ ai_client.py            # 旧 AI 客户端导入兼容包装
│  ├─ ai_processor.py         # 旧 AI 处理导入兼容包装
│  ├─ scoring.py              # 旧评分导入兼容包装
│  ├─ catalog_*.py            # 旧目录导入与 CLI 兼容包装
│  ├─ html_generator.py       # 旧展示/快照导入兼容包装
│  └─ text_utils.py
├─ templates/                 # dossier/materials/admin 分层模板
├─ static/                    # shared 与三类页面的分层前端资源
├─ data/
│  ├─ seeds/catalog/          # V4.1 可审核名册种子
│  ├─ registries/             # RSS 配置与 V4 来源注册表
│  └─ archive/data.json       # Git 忽略的旧 JSON 历史备份
├─ var/                       # Git 忽略的本地运行数据
│  ├─ orbitai.db              # 当前唯一活动 SQLite 数据库
│  ├─ backups/                # SQLite Backup API 备份
│  └─ snapshots/              # 静态 HTML 兼容输出
└─ README.md

Web 规范入口为 `/industries/artificial-intelligence`、`/materials`、`/materials/featured`、`/materials/daily` 和 `/admin/status`。`/` 使用 HTTP 307 临时重定向进入 AI 产业目录；旧材料页和状态页 URL 继续保留，并以 307 重定向到对应规范地址。

活动业务代码应直接从 `orbitai.materials`、`orbitai.catalog`、`orbitai.web` 或 `orbitai.core` 导入。根 `orbitai/*.py` 中对应的旧模块只用于短期兼容，等待后续确认清退。

根目录 `orbitai.db` 目前仅作为阶段 4 前的只读保留副本，不是活动数据库。普通页面访问如果找不到 `var/orbitai.db` 会明确失败，不会静默创建空数据库。

项目演进（简要）
V1.x：本地 RSS 抓取与静态 HTML 展示。
V2.x：接入 AI 处理，生成中文标题、摘要、分类、标签和多维评分，增加精选页与每日简报。
V3.x：本地 Web App 化，逐步增加：
FastAPI 服务化。
Jinja2 模板渲染。
Web 交互增强。
SQLite 数据库化。
状态页与错误管理。
网页端手动操作与静态兼容。
V3.6：本地 Web 稳定版收官，长期使用可控、页面与后台功能完整。
开发原则
保持本地可运行闭环。
模块化、可扩展、易维护。
AI 用于理解、分类、摘要、打分。
生成内容不提交 Git。
版本完成后，测试、总结并提交 GitHub。
稳定小步迭代优先，避免一次性大改。
