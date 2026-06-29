import json
import html
import logging
import re
from groq import AsyncGroq
from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are a premium AI news editor for a high-end Telegram channel. Your goal is to analyze, score, and rewrite the provided news article as a natural, engaging tech blog post in Ukrainian, strictly in the style of the "Droider" tech channel.

The style must feel like it was written by a human tech expert (witty, expert, highly professional, direct, engaging). Avoid corporate fluff, robotic transitions, and generic introductory statements.

To ensure the post fits within Telegram's photo caption limits, the combined length of the translated_title and all paragraphs must be UNDER 850 characters. Keep the text concise, punchy, and dense with information.

You must output a JSON object containing the following keys (ensure all Ukrainian translations are natural, professional, and grammatically correct):

- "importance_score": integer from 1 to 10. Rate how interesting and critical this news is for a general AI enthusiast.
  - 10: Historic/groundbreaking (e.g. GPT-5 release, OpenAI CEO fired)
  - 7-9: Major announcements, model releases, significant breakthroughs
  - 4-6: Standard AI updates, interesting research, funding rounds
  - 1-3: Minor/niche updates, routine corporate news, generic articles
- "emoji_prefix": a single relevant emoji to introduce this news (e.g., 🔌 for hardware, 🤖 for models/agents, 🔬 for research, 🏢 for company news, ⚖️ for regulations).
- "translated_title": a catchy, short, and punchy title in Ukrainian (plain text, no HTML tags, normal capitalization).
- "lead_paragraph": a short paragraph (1-2 sentences) in Ukrainian representing the news lead.
  - It MUST naturally embed the article's source link. To do this, wrap a contextually relevant verb or key noun (e.g., "представила", "презентувала", "дослідження", "новий звіт", "опублікувала") in <a href="{link}">...</a>.
- "details_paragraph": a paragraph in Ukrainian highlighting key figures, details, or comparisons (e.g., performance increases, benchmarks, physical sizes).
- "why_needed_paragraph": a paragraph in Ukrainian explaining why this is needed, the technical background, the problem it solves, or the physical limits/constraints it bypasses. Output ONLY the explanation text. Do NOT include headers like "Навіщо це потрібно" or "Зачем это нужно".
- "beneficiaries_paragraph": a paragraph in Ukrainian explaining who will benefit from this development, who are the main beneficiaries/sectors. Output ONLY the explanation text. Do NOT include headers like "Головні бенефіціари" or "Главные бенефициары".

Input format:
Source: <source>
Title: <title>
Summary: <summary>

Your response must be a valid JSON object ONLY. Do not wrap it in markdown codeblocks.
"""

async def process_article(source: str, original_title: str, original_summary: str) -> dict:
    """
    Sends article data to Groq to translate, score, and structure as natural paragraphs.
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
            "lead_paragraph": "Новий звіт від компанії Anthropic <a href=\"{link}\">демонструє</a>, як автономні агенти на базі моделі Claude 3.5 Sonnet успішно автоматизують до 80% рутинних завдань.",
            "details_paragraph": "Це нововведення дозволяє знизити операційні витрати компаній на 45% завдяки впровадженню автономних циклів тестування коду. Claude 3.5 Sonnet лідирує з 88% успішних запусків.",
            "why_needed_paragraph": "Класичні системи вимагали постійного людського нагляду за кожним кроком, що створювало пляшки з пляшковим горлом у процесах розробки.",
            "beneficiaries_paragraph": "ІТ-компанії, відділи клієнтської підтримки та розробники ПЗ, що прагнуть оптимізувати свій робочий час."
        }
        
    return {
        "importance_score": 8,
        "emoji_prefix": "🔥",
        "translated_title": "OpenAI готує запуск GPT-5.6 Sol",
        "lead_paragraph": "На ринках прогнозів Polymarket ймовірність запуску нової моделі <a href=\"{link}\">оцінюють</a> у рекордні 83%.",
        "details_paragraph": "Очікується, що GPT-5.6 Sol отримає гігантський контекст у 1,5 млн токенів, покращену генерацію UI та виправлення помилок з попередніх версій.",
        "why_needed_paragraph": "Попередні моделі мали обмежений контекст та часто помилялися у довгих діалогах і складних завданнях програмування.",
        "beneficiaries_paragraph": "Спільнота розробників, дослідники даних та всі користувачі, які працюють із великими обсягами текстової інформації."
    }

def format_telegram_post(source: str, link: str, processed_data: dict) -> str:
    """
    Combines the structured JSON output from Groq into a premium editorial layout.
    """
    emoji_prefix = str(processed_data.get("emoji_prefix", "🤖")).strip()
    title = str(processed_data.get("translated_title", "Без назви")).strip()
    
    # Extract components
    lead = str(processed_data.get("lead_paragraph", "")).strip()
    details = str(processed_data.get("details_paragraph", "")).strip()
    why_needed = str(processed_data.get("why_needed_paragraph", "")).strip()
    beneficiaries = str(processed_data.get("beneficiaries_paragraph", "")).strip()
    
    # HTML escape the link
    escaped_link = html.escape(link)
    
    # Process link in the lead paragraph
    if lead:
        # Replace {link} placeholder if present
        lead = lead.replace('{link}', link)
        # Force any <a> tag in lead to point to the correct link
        lead = re.sub(r'<a(?:\s+[^>]*)?>', f'<a href="{escaped_link}">', lead)
        
    # Assemble header
    post_text = f"{emoji_prefix} <b>{html.escape(title, quote=False)}</b>\n\n"
    
    # Assemble body paragraphs
    paragraphs = []
    if lead:
        paragraphs.append(lead)
    if details:
        paragraphs.append(details)
    if why_needed:
        paragraphs.append(f"<b>Навіщо це потрібно.</b> {why_needed}")
    if beneficiaries:
        paragraphs.append(f"<b>Головні бенефіціари —</b> {beneficiaries}")
        
    post_text += "\n\n".join(paragraphs)
    post_text += "\n\n"
    
    # Add channel sign-off
    post_text += "@raumainews"
    
    return post_text.strip()
