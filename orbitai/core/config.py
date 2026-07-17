import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
DATA_DIR = PROJECT_ROOT / "data"
SEEDS_DIR = DATA_DIR / "seeds"
CATALOG_DATA_DIR = SEEDS_DIR / "catalog"
REGISTRIES_DIR = DATA_DIR / "registries"
ARCHIVE_DIR = DATA_DIR / "archive"
VAR_DIR = PROJECT_ROOT / "var"
BACKUP_DIR = VAR_DIR / "backups"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"

# 版本控制资产位于 data/，本地运行资产位于 var/。
DATA_FILE = ARCHIVE_DIR / "data.json"
DATABASE_FILE = VAR_DIR / "orbitai.db"
SNAPSHOT_DIR = VAR_DIR / "snapshots"
HTML_FILE = SNAPSHOT_DIR / "index.html"
FEATURED_FILE = SNAPSHOT_DIR / "featured.html"
DAILY_FILE = SNAPSHOT_DIR / "daily.html"
SOURCES_FILE = REGISTRIES_DIR / "sources.json"
SOURCE_REGISTRY_FILE = REGISTRIES_DIR / "sources.v4.json"
CATALOG_SEED_FILE = CATALOG_DATA_DIR / "foundation_models.v4.1.json"

load_dotenv(dotenv_path=ENV_FILE)

# RSS 抓取配置
RSS_MAX_ITEMS_PER_SOURCE = int(os.getenv("RSS_MAX_ITEMS_PER_SOURCE", "5"))
RSS_RETRY_TIMES = int(os.getenv("RSS_RETRY_TIMES", "3"))
RSS_RETRY_DELAY_SECONDS = int(os.getenv("RSS_RETRY_DELAY_SECONDS", "2"))
RSS_TIMEOUT_SECONDS = int(os.getenv("RSS_TIMEOUT_SECONDS", "20"))

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
    "ARCHIVE_DIR",
    "VAR_DIR",
    "BACKUP_DIR",
    "TEMPLATES_DIR",
    "STATIC_DIR",
    "DATA_FILE",
    "DATABASE_FILE",
    "SNAPSHOT_DIR",
    "HTML_FILE",
    "FEATURED_FILE",
    "DAILY_FILE",
    "SOURCES_FILE",
    "SOURCE_REGISTRY_FILE",
    "CATALOG_SEED_FILE",
    "RSS_MAX_ITEMS_PER_SOURCE",
    "RSS_RETRY_TIMES",
    "RSS_RETRY_DELAY_SECONDS",
    "RSS_TIMEOUT_SECONDS",
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
