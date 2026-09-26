import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
DATA_DIR = PROJECT_ROOT / "data"
SEEDS_DIR = DATA_DIR / "seeds"
CATALOG_DATA_DIR = SEEDS_DIR / "catalog"
REGISTRIES_DIR = DATA_DIR / "registries"
VAR_DIR = PROJECT_ROOT / "var"
BACKUP_DIR = VAR_DIR / "backups"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"

# 版本控制资产位于 data/，本地运行资产位于 var/。
DATABASE_FILE = VAR_DIR / "orbitai.db"
SOURCES_FILE = REGISTRIES_DIR / "sources.json"
SOURCE_REGISTRY_FILE = REGISTRIES_DIR / "sources.v4.json"
CATALOG_SEED_FILE = CATALOG_DATA_DIR / "foundation_models.v4.1.json"

load_dotenv(dotenv_path=ENV_FILE)

# Explicit local review sessions may use an isolated copy, never a second active DB.
PREVIEW_DATABASE = os.getenv("ORBITAI_PREVIEW_DATABASE", "")
if PREVIEW_DATABASE:
    preview_path = Path(PREVIEW_DATABASE).resolve()
    if not preview_path.is_relative_to((VAR_DIR / "previews").resolve()) or not preview_path.is_file():
        raise ValueError("预览数据库必须是 var/previews/ 下已存在的隔离副本")
    DATABASE_FILE = preview_path

# RSS 抓取配置
RSS_MAX_ITEMS_PER_SOURCE = int(os.getenv("RSS_MAX_ITEMS_PER_SOURCE", "5"))
RSS_RETRY_TIMES = int(os.getenv("RSS_RETRY_TIMES", "3"))
RSS_RETRY_DELAY_SECONDS = int(os.getenv("RSS_RETRY_DELAY_SECONDS", "2"))
RSS_TIMEOUT_SECONDS = int(os.getenv("RSS_TIMEOUT_SECONDS", "20"))

# Firecrawl 只作为受限官网后备读取器，不进入 RSS 或 AI 供应商配置。
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")
FIRECRAWL_TIMEOUT_SECONDS = int(
    os.getenv("FIRECRAWL_TIMEOUT_SECONDS", "35")
)
FIRECRAWL_RETRY_TIMES = int(os.getenv("FIRECRAWL_RETRY_TIMES", "2"))
FIRECRAWL_RETRY_DELAY_SECONDS = int(
    os.getenv("FIRECRAWL_RETRY_DELAY_SECONDS", "2")
)
FIRECRAWL_CRAWL_POLL_SECONDS = float(
    os.getenv("FIRECRAWL_CRAWL_POLL_SECONDS", "2")
)
FIRECRAWL_CRAWL_TIMEOUT_SECONDS = int(
    os.getenv("FIRECRAWL_CRAWL_TIMEOUT_SECONDS", "60")
)

AI_PROVIDER = os.getenv("AI_PROVIDER", "deepseek")
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.deepseek.com")
AI_MODEL = os.getenv("AI_MODEL", "deepseek-v4-flash")
AI_BATCH_LIMIT = int(os.getenv("AI_BATCH_LIMIT", "1"))
AI_INPUT_SUMMARY_MAX_CHARS = int(os.getenv("AI_INPUT_SUMMARY_MAX_CHARS", "1800"))
AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "500"))

AI_CATEGORIES = [
    "模型",
    "产品",
    "论文/研究",
    "开发工具",
    "行业/商业",
    "政策/安全",
    "教程/观点",
    "其他",
]

AI_SCORE_KEYS = [
    "importance",
    "novelty",
    "practical_value",
    "learning_value",
    "source_authority",
]

FINAL_SCORE_WEIGHTS = {
    "importance": 0.30,
    "novelty": 0.20,
    "practical_value": 0.20,
    "learning_value": 0.20,
    "source_authority": 0.10,
}

FEATURED_SCORE_THRESHOLD = 75
FEATURED_MIN_ITEMS = 5
FEATURED_MAX_ITEMS = 10


__all__ = [
    "PROJECT_ROOT",
    "ENV_FILE",
    "DATA_DIR",
    "SEEDS_DIR",
    "CATALOG_DATA_DIR",
    "REGISTRIES_DIR",
    "VAR_DIR",
    "BACKUP_DIR",
    "TEMPLATES_DIR",
    "STATIC_DIR",
    "DATABASE_FILE",
    "SOURCES_FILE",
    "SOURCE_REGISTRY_FILE",
    "CATALOG_SEED_FILE",
    "RSS_MAX_ITEMS_PER_SOURCE",
    "RSS_RETRY_TIMES",
    "RSS_RETRY_DELAY_SECONDS",
    "RSS_TIMEOUT_SECONDS",
    "FIRECRAWL_API_KEY",
    "FIRECRAWL_TIMEOUT_SECONDS",
    "FIRECRAWL_RETRY_TIMES",
    "FIRECRAWL_RETRY_DELAY_SECONDS",
    "FIRECRAWL_CRAWL_POLL_SECONDS",
    "FIRECRAWL_CRAWL_TIMEOUT_SECONDS",
    "AI_PROVIDER",
    "AI_API_KEY",
    "AI_BASE_URL",
    "AI_MODEL",
    "AI_BATCH_LIMIT",
    "AI_INPUT_SUMMARY_MAX_CHARS",
    "AI_MAX_TOKENS",
    "AI_CATEGORIES",
    "AI_SCORE_KEYS",
    "FINAL_SCORE_WEIGHTS",
    "FEATURED_SCORE_THRESHOLD",
    "FEATURED_MIN_ITEMS",
    "FEATURED_MAX_ITEMS",
]
