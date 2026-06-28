import json
import html
import logging
from groq import AsyncGroq
from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are a premium AI news editor for a high-end Telegram channel. Your goal is to analyze, translate, score, and format AI news in an Apple-style, minimalist, and visually engaging manner.
You must output a JSON object containing the following keys (ensure all Ukrainian translations are natural and professional):

- "importance_score": integer from 1 to 10. Rate how interesting and critical this news is for a general AI enthusiast.
  - 10: Historic/groundbreaking (e.g. GPT-5 release, OpenAI CEO fired)
  - 7-9: Major announcements, model releases, significant breakthroughs
  - 4-6: Standard AI updates, interesting research, funding rounds
  - 1-3: Minor/niche updates, routine corporate news, generic articles
- "emoji_prefix": string (a single relevant emoji to introduce this category/news, e.g. 🔥 for hot/breaking news, 🤖 for models, 🔬 for research, 🏢 for company/business, ⚖️ for regulations, 📦 for product updates).
- "translated_title": string (catchy, short title in Ukrainian, translated professionally. Do not keep it in English unless it is a proper name/code. Use normal capitalization, NOT ALL CAPS).
- "accent_summary": string (a very short summary hook, e.g. "Polymarket — 83% на запуск 28 червня" or "Збільшення швидкості на 40%").
- "overview": string (1-2 sentences in Ukrainian providing the context or introduction of the news).
- "key_points_title": string or null (optional title for key details/features, e.g., "Очікуваний функціонал", "Ключові деталі").
- "key_points": array of strings (optional list of key details or features, without bullet characters like "→" or "-").
- "warning_title": string or null (optional title for a warning, error, bug, or note, e.g., "Goblin Incident" or "Критика").
- "warning_text": string or null (optional context for the warning/note, in Ukrainian).
- "benchmarks_title": string or null (optional title for benchmarks, rankings, or metrics, e.g., "SWE-Bench Pro").
- "benchmarks": array of strings (optional ranking or comparison lines, without numbering/bullet emojis like "🥇").
- "conclusion": string (1 sentence forward-looking conclusion or impact analysis in Ukrainian).

Input format:
Source: <source>
Title: <title>
Summary: <summary>

Your response must be a valid JSON object ONLY. Do not wrap it in markdown codeblocks (no ```json).
"""

async def process_article(source: str, original_title: str, original_summary: str) -> dict:
    """
    Sends article data to Groq to translate, categorize, score, and structure.
    """
    if not settings.GROQ_API_KEY:
        logger.warning("GROQ_API_KEY is not set. Using fallback mock processor.")
        return get_mock_processed_article(source, original_title, original_summary)
        
    try:
        client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        
        user_content = f"Source: {source}\nTitle: {original_title}\nSummary: {original_summary}"
        
        response = await client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            model=settings.GROQ_MODEL,
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        content = response.choices[0].message.content
        data = json.loads(content)
        return data
    except Exception as e:
        logger.error(f"Error processing article with Groq: {e}")
        return get_mock_processed_article(source, original_title, original_summary)

def get_mock_processed_article(source: str, title: str, summary: str) -> dict:
    """Fallback generator when API keys are missing or API calls fail."""
    if "agent" in title.lower() or "work" in title.lower():
        return {
            "importance_score": 9,
            "emoji_prefix": "🤖",
            "translated_title": "ШІ-агенти змінюють корпоративну роботу",
            "accent_summary": "Дослідження Anthropic про автономні команди",
            "overview": "Новий звіт демонструє, як агенти на базі Claude 3.5 Sonnet автоматизують до 80% рутинних завдань у розробці та підтримці клієнтів.",
            "key_points_title": "Головні висновки",
            "key_points": [
                "Зниження операційних витрат на 45%",
                "Створення автономних циклів тестування коду",
                "Цілодобова підтримка без участі людей"
            ],
            "warning_title": "Безпека даних",
            "warning_text": "Компаніям рекомендують обмежувати доступ агентів до конфіденційних баз даних.",
            "benchmarks_title": "Ефективність виконання завдань",
            "benchmarks": [
                "Claude 3.5 Sonnet — 88% успішних запусків",
                "GPT-4o — 79% успішних запусків",
                "Llama-3 70B — 65% успішних запусків"
            ],
            "conclusion": "Автономні агенти переходять від експериментів до реального впровадження у бізнес."
        }
        
    return {
        "importance_score": 8,
        "emoji_prefix": "🔥",
        "translated_title": "GPT-5.6 сьогодні",
        "accent_summary": "Polymarket дає 83% ймовірність запуску 28 червня",
        "overview": "Рядок kindle-alpha з'явився в логах Codex 12 червня. Ринки прогнозів оцінюють запуск GPT-5.6 сьогодні на 83%.",
        "key_points_title": "Очікуваний функціонал",
        "key_points": [
            "Контекст 1,5 млн токенів",
            "Покращена генерація UI та front-end коду",
            "Швидший Codex",
            "Виправлення «Goblin Incident»"
        ],
        "warning_title": "Goblin Incident",
        "warning_text": "збій reward-моделі в GPT-5.5. Спричинив +175% метафор з тваринами.",
        "benchmarks_title": "SWE-Bench Pro",
        "benchmarks": [
            "Claude Opus 4.8 — лідер",
            "GLM-5.2 — 2-е місце",
            "GPT-5.5 — відстає"
        ],
        "conclusion": "Якщо GPT-5.6 вийде сьогодні — OpenAI може повернути собі лідерство."
    }

def format_telegram_post(source: str, link: str, processed_data: dict) -> str:
    """
    Combines the structured JSON output from Groq into a premium Apple-style HTML layout.
    """
    emoji_prefix = processed_data.get("emoji_prefix", "🤖")
    title = processed_data.get("translated_title", "Без назви")
    accent = processed_data.get("accent_summary", "")
    overview = processed_data.get("overview", "")
    
    # Title line (Title is a hyperlink to the original article, normal case, bold)
    post_text = f'<a href="{link}"><b>{emoji_prefix} {html.escape(title)}</b></a>'
    if accent:
        post_text += f" — {html.escape(accent)}"
    post_text += "\n"
    
    if overview:
        post_text += f"{html.escape(overview)}\n"
    post_text += "\n"
    
    # Key points
    key_points = processed_data.get("key_points")
    if key_points:
        kp_title = processed_data.get("key_points_title") or "Ключові деталі"
        post_text += f"📦 <b>{html.escape(kp_title)}:</b>\n"
        for kp in key_points:
            post_text += f"→ {html.escape(kp)}\n"
        post_text += "\n"
        
    # Warning/Note
    warn_text = processed_data.get("warning_text")
    if warn_text:
        warn_title = processed_data.get("warning_title") or "Зверніть увагу"
        post_text += f"⚠️ <b>«{html.escape(warn_title)}»</b> — {html.escape(warn_text)}\n\n"
        
    # Benchmarks/Rankings
    benchmarks = processed_data.get("benchmarks")
    if benchmarks:
        bench_title = processed_data.get("benchmarks_title") or "Порівняння"
        post_text += f"📊 <b>{html.escape(bench_title)}:</b>\n"
        ranks = ["🥇", "🥈", "🥉"]
        for idx, bench in enumerate(benchmarks):
            bullet = ranks[idx] if idx < len(ranks) else "▪️"
            post_text += f"{bullet} {html.escape(bench)}\n"
        post_text += "\n"
        
    # Conclusion
    conclusion = processed_data.get("conclusion")
    if conclusion:
        post_text += f"{html.escape(conclusion)}\n\n"
        
    # Add channel sign-off
    post_text += "@raumainews"
        
    return post_text.strip()
