OrbitAI

OrbitAI 是一个本地优先的个人 AI 信息雷达（Personal AI Information Radar）。

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

项目结构（核心部分）
OrbitAI/
├─ app.py                     # FastAPI 本地服务入口
├─ main.py                    # RSS + AI + SQLite 流程调度
├─ orbitai/                   # 功能模块
│  ├─ config.py
│  ├─ data_utils.py
│  ├─ rss_fetcher.py
│  ├─ ai_client.py
│  ├─ ai_processor.py
│  ├─ scoring.py
│  ├─ html_generator.py
│  └─ text_utils.py
├─ templates/                 # Jinja2 页面模板
├─ static/                    # 样式和前端逻辑
├─ data.json                  # 历史备份
├─ orbitai.db                 # SQLite 数据库
├─ sources.json               # RSS 配置
└─ README.md
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