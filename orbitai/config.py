import os
from pathlib import Path

from dotenv import load_dotenv

DATA_FILE = Path("data.json")
DATABASE_FILE = Path("orbitai.db")
HTML_FILE = Path("index.html")
FEATURED_FILE = Path("featured.html")
DAILY_FILE = Path("daily.html")
SOURCES_FILE = Path("sources.json")

load_dotenv()

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