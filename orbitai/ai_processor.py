import json
import re
from datetime import datetime, timezone

from orbitai.ai_client import create_ai_client, request_chat_completion
from orbitai.config import (
    AI_PROVIDER,
    AI_BASE_URL,
    AI_MODEL,
    AI_BATCH_LIMIT,
    AI_INPUT_SUMMARY_MAX_CHARS,
    AI_CATEGORIES,
    AI_SCORE_KEYS,
)
from orbitai.data_utils import create_empty_ai_fields
from orbitai.scoring import normalize_ai_scores, calculate_final_score
from orbitai.text_utils import clean_html, truncate_text


def extract_json_from_text(text):
    """
    尝试从 AI 返回文本中提取 JSON。
    即使模型在 JSON 前后加了多余文本，也尽量解析出来。
    """
    if not text:
        return None

    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        return None

    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def normalize_ai_category(category, fallback_category="其他"):
    """
    校验 AI 返回的分类。
    如果 AI 返回不在固定分类列表中，就回退到规则分类或“其他”。
    """
    category = str(category or "").strip()

    if category in AI_CATEGORIES:
        return category

    fallback_category = str(fallback_category or "其他").strip()

    if fallback_category in AI_CATEGORIES:
        return fallback_category

    # 兼容 V1/V2.1 旧规则分类里的“行业”
    if fallback_category == "行业":
        return "行业/商业"

    return "其他"


def normalize_ai_tags(tags):
    """
    校验并清洗 AI 返回的 tags。
    目标：确保 tags 一定是短字符串列表，避免 AI 返回格式漂移。
    """
    if isinstance(tags, str):
        tags = re.split(r"[,，、/|]", tags)

    if not isinstance(tags, list):
        return []

    cleaned_tags = []
    seen_tags = set()

    for tag in tags:
        tag_text = str(tag or "").strip()
        tag_text = re.sub(r"\s+", " ", tag_text)

        if not tag_text:
            continue

        if len(tag_text) > 24:
            tag_text = tag_text[:24].strip()

        tag_key = tag_text.lower()

        if tag_key in seen_tags:
            continue

        cleaned_tags.append(tag_text)
        seen_tags.add(tag_key)

        if len(cleaned_tags) >= 6:
            break

    return cleaned_tags


def item_needs_ai_processing(item):
    """
    判断一条信息是否还需要 AI 处理。
    只有 title_cn、summary、category、tags、scores、final_score 都齐全，才跳过。
    """
    ai = item.get("ai")

    if not isinstance(ai, dict):
        return True

    if not str(ai.get("title_cn", "")).strip():
        return True

    if not str(ai.get("summary", "")).strip():
        return True

    if not str(ai.get("category", "")).strip():
        return True

    tags = ai.get("tags", [])

    if not isinstance(tags, list) or len(tags) == 0:
        return True

    scores = ai.get("scores", {})

    if not isinstance(scores, dict):
        return True

    for key in AI_SCORE_KEYS:
        value = scores.get(key)

        if value is None:
            return True

        try:
            score = float(value)
        except (TypeError, ValueError):
            return True

        if score < 0 or score > 100:
            return True

    final_score = ai.get("final_score")

    if final_score is None:
        return True

    try:
        float(final_score)
    except (TypeError, ValueError):
        return True

    return False


def item_is_ai_complete(item):
    """
    判断一条信息是否已经完成当前版本所需的 AI 结构化处理。
    """
    return not item_needs_ai_processing(item)


def call_ai_for_analysis(client, item):
    """
    直接使用 DeepSeek REST API，为单条信息生成：
    - 中文标题 title_cn
    - 中文摘要 summary
    - AI 分类 category
    - 关键词 tags
    - 多维评分 scores
    """
    title = item.get("title", "")
    source = item.get("source", "")
    published = item.get("published", "")
    category_rule = item.get("category_rule", "其他")

    existing_ai = item.get("ai", {})
    existing_title_cn = ""
    existing_summary = ""

    if isinstance(existing_ai, dict):
        existing_title_cn = str(existing_ai.get("title_cn", "")).strip()
        existing_summary = str(existing_ai.get("summary", "")).strip()

    summary_original = clean_html(item.get("summary_original", ""))
    summary_for_ai = truncate_text(summary_original, AI_INPUT_SUMMARY_MAX_CHARS)

    categories_text = "、".join(AI_CATEGORIES)

    system_prompt = """
你是 OrbitAI 的中文 AI 信息整理助手。
你必须只输出合法 JSON，不要输出 Markdown，不要输出解释。
""".strip()

    user_prompt = f"""
请阅读下面这条 AI 行业信息，为它生成结构化整理结果。

要求：
1. 只输出 JSON。
2. JSON 必须包含 title_cn、summary、category、tags、scores 五个字段。
3. title_cn 是自然、准确的中文标题，不要机械直译。
4. summary 是 1 到 2 句中文摘要，要求实用、克制，不要夸张。
5. category 必须且只能从以下分类中选择一个：{categories_text}。
6. tags 必须是字符串数组，数量 3 到 6 个。
7. tags 优先使用中文；但 LLM、RAG、AI Agent、Codex、OpenAI 这类专有名词可以保留英文。
8. 不要输出“人工智能”“技术”“新闻”这类过泛标签。
9. scores 必须是对象，包含 importance、novelty、practical_value、learning_value、source_authority 五个字段。
10. 每个评分必须是 0 到 100 的数字。
11. importance 表示行业或技术重要性。
12. novelty 表示信息新颖性。
13. practical_value 表示对开发、学习、产品使用的实际价值。
14. learning_value 表示这条信息是否有助于理解 AI 技术或行业。
15. source_authority 表示信源权威度。
16. 如果原文信息不足，就基于标题和已有摘要谨慎概括。
17. 不要编造原文没有的信息。

输出 JSON 示例：
{{
  "title_cn": "中文标题",
  "summary": "中文摘要",
  "category": "开发工具",
  "tags": ["AI Agent", "代码助手", "开发者工具"],
  "scores": {{
    "importance": 80,
    "novelty": 70,
    "practical_value": 85,
    "learning_value": 75,
    "source_authority": 90
  }}
}}

信息如下：
来源：{source}
发布时间：{published}
规则分类参考：{category_rule}
原标题：{title}
已有中文标题：{existing_title_cn}
已有中文摘要：{existing_summary}
原始摘要：{summary_for_ai}
""".strip()

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]

    result_text = request_chat_completion(client, messages)
    result_json = extract_json_from_text(result_text)

    if not isinstance(result_json, dict):
        raise ValueError(f"AI 返回内容不是合法 JSON：{result_text}")

    title_cn = str(result_json.get("title_cn", "")).strip()
    summary = str(result_json.get("summary", "")).strip()
    category = normalize_ai_category(
        result_json.get("category", ""),
        fallback_category=category_rule,
    )
    tags = normalize_ai_tags(result_json.get("tags", []))
    scores = normalize_ai_scores(result_json.get("scores", {}))
    final_score = calculate_final_score(scores)

    if not title_cn:
        title_cn = existing_title_cn

    if not summary:
        summary = existing_summary

    if not title_cn or not summary:
        raise ValueError(f"AI 返回缺少 title_cn 或 summary：{result_json}")

    if not tags:
        raise ValueError(f"AI 返回缺少有效 tags：{result_json}")

    return {
        "title_cn": title_cn,
        "summary": summary,
        "category": category,
        "tags": tags,
        "scores": scores,
        "final_score": final_score,
    }


def process_ai_items(items):
    """
    批量处理未完成 AI 结构化整理的信息。
    每次最多尝试 AI_BATCH_LIMIT 条，成功或失败都计入尝试次数。
    """
    if AI_BATCH_LIMIT <= 0:
        print("\nℹ️ AI_BATCH_LIMIT <= 0，跳过 AI 处理。")
        return items

    client = create_ai_client()

    if client is None:
        print("\n⚠️ 未找到 AI_API_KEY，跳过 AI 处理。")
        print("请在 .env 文件中配置 AI_API_KEY。")
        return items

    print(f"\n🤖 AI Provider：{AI_PROVIDER}")
    print(f"🤖 AI Base URL：{AI_BASE_URL}")
    print(f"🤖 AI Model：{AI_MODEL}")
    print(f"🤖 本次最多尝试：{AI_BATCH_LIMIT} 条")

    attempted_count = 0
    processed_count = 0

    for item in items:
        ai = item.get("ai")

        if not isinstance(ai, dict):
            item["ai"] = create_empty_ai_fields()
            ai = item["ai"]

        if not item_needs_ai_processing(item):
            continue

        if attempted_count >= AI_BATCH_LIMIT:
            break

        title = item.get("title", "无标题")
        attempted_count += 1

        print(f"\n🤖 AI 结构化处理中：{title}")

        try:
            ai_result = call_ai_for_analysis(client, item)

            ai["title_cn"] = ai_result["title_cn"]
            ai["summary"] = ai_result["summary"]
            ai["category"] = ai_result["category"]
            ai["tags"] = ai_result["tags"]
            ai["scores"] = ai_result["scores"]
            ai["final_score"] = ai_result["final_score"]
            ai["processed"] = True
            ai["processed_at"] = datetime.now(timezone.utc).isoformat()
            ai["error"] = ""
            ai["error_type"] = ""
            ai["failed_at"] = ""
            ai["retry_count"] = 0

            processed_count += 1

            print(f"✅ AI 结构化完成：{ai['title_cn']}")
            print(f"   分类：{ai['category']}")
            print(f"   标签：{', '.join(ai['tags'])}")
            print(f"   综合分：{ai['final_score']}")

        except Exception as error:
            error_type = type(error).__name__
            error_message = repr(error)

            ai["error"] = error_message
            ai["error_type"] = error_type
            ai["failed_at"] = datetime.now(timezone.utc).isoformat()
            ai["retry_count"] = int(ai.get("retry_count", 0) or 0) + 1
            ai["processed"] = False

            print(f"⚠️ AI 处理失败：{title}")
            print(f"错误类型：{ai['error_type']}")
            print(f"错误信息：{ai['error']}")
            print(f"累计失败次数：{ai['retry_count']}")
            print(f"失败时间：{ai['failed_at']}")

    print(f"\n✅ 本次 AI 尝试数量：{attempted_count} 条")
    print(f"✅ 本次 AI 成功数量：{processed_count} 条")
    return items