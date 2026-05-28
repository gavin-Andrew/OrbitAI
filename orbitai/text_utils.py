import re


def clean_html(raw_text):
    """
    RSS 里的 summary 有时会带 HTML 标签。
    这里做一个简单清理，让网页展示更干净。
    """
    if not raw_text:
        return ""

    text = re.sub(r"<[^>]+>", "", raw_text)
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    return text.strip()


def truncate_text(text, max_length=220):
    """
    把过长的文本截断，避免页面卡片或 AI 输入过长。
    """
    if not text:
        return ""

    text = " ".join(text.split())

    if len(text) <= max_length:
        return text

    return text[:max_length].rstrip() + "..."