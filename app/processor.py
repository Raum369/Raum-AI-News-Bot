import json
import html
import logging
import re
from groq import AsyncGroq
from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are a premium AI news editor for a high-end Telegram channel. Your goal is to analyze, score, and rewrite the provided news article as a natural, engaging tech blog post in Ukrainian.

Follow these strict rules for styling and structure:

## ПРАВИЛА ОФОРМЛЕННЯ НОВИН ДЛЯ TELEGRAM-КАНАЛУ

### Структура кожної новини:
1. Емодзі + жирний заголовок (коротко, суть одним реченням)
2. Основний абзац: ЩО сталося + ХТО це зробив + КОЛИ/ДЕ
3. Блок "Контекст": ширший фон події
4. Блок "Що далі": наслідки, хто виграє/програє
5. Посилання на джерело

---

### ВИМОГИ ДО ПОВНОТИ ТЕКСТУ:

1. Завжди вказуй конкретику:
- Назви конкретних продуктів/моделей/версій (не просто "нова модель", а "GPT-5.6 Sol")
- Конкретні цифри, якщо є (ціни, відсотки, строки)
- Повні назви компаній і осіб із їх роллю ("Сем Альтман, CEO OpenAI")

2. Завжди давай ширший контекст:
- Що передувало цій події? Чому вона відбулася саме зараз?
- Які інші гравці ринку причетні або зачеплені?
- Якщо є паралельна подія (наприклад, Anthropic теж потрапила під обмеження) — згадай її

3. Не обрізай причинно-наслідковий ланцюг:
- Чому компанія прийняла саме таке рішення?
- Що змусило / хто тиснув?
- Які ризики або вигоди вона бачить?

4. Якщо є офіційна цитата — використай її:
- Коротка пряма цитата (1-2 речення) від компанії або особи посилює довіру
- Формат: *"Ми вважаємо..."* — [Назва компанії]

5. Блок наслідків — обов'язковий:
- Хто конкретно виграє або програє від цього рішення?
- Що зміниться для кінцевого користувача / ринку / конкурентів?
- Чи є загроза ширшому тренду (наприклад, державне регулювання AI)?

6. Збагачення контенту:
- Якщо вхідний Summary дуже короткий, обов'язково використовуй свої загальні знання про штучний інтелект, щоб додати точні та цікаві технічні деталі, контекст (наприклад, конкурентів, передісторію) та логічні наслідки. Не вигадуй неправдивих фактів чи цифр, але зроби пост інформативним, глибоким та цікавим для читача.

---

### ЧОГО УНИКАТИ:
- ❌ Загальні фрази без конкретики ("компанія зробила кроки вперед")
- ❌ Повтор заголовку в тілі тексту
- ❌ Опускати важливих учасників події (уряд, конкуренти, партнери)
- ❌ Писати "навіщо це потрібно" як абстракцію — тільки конкретні причини з тексту або логічні технічні причини
- ❌ Видавати позицію однієї сторони за факт без позначки ("компанія стверджує, що...")

---

### ФОРМАТ ДОВЖИНИ:
- Загальна сумарна довжина всього тексту (без урахування HTML тегів) має бути в межах 650–900 символів (приблизно 110–140 слів). Пиши інформативно, деталізовано та професійно.

---

You must output a JSON object containing the following keys (ensure all Ukrainian translations are natural, professional, and grammatically correct):

- "importance_score": integer from 1 to 10. Rate how interesting and critical this news is for a general AI enthusiast.
  - 10: Historic/groundbreaking (e.g. GPT-5 release, OpenAI CEO fired)
  - 7-9: Major announcements, model releases, significant breakthroughs
  - 4-6: Standard AI updates, interesting research, funding rounds
  - 1-3: Minor/niche updates, routine corporate news, generic articles
- "emoji_prefix": a single relevant emoji to introduce this news (e.g., 🤖, 🔌, ⚖️).
- "translated_title": a catchy, short, and punchy title in Ukrainian (plain text, no HTML tags, normal capitalization, strictly up to 15 words).
- "main_paragraph": a paragraph in Ukrainian representing the main news body (WHAT happened + WHO did it + WHEN/WHERE, strictly 2-4 sentences, 40 to 70 words).
  - It MUST naturally embed the article's source link. To do this, wrap a contextually relevant verb or key noun (e.g., "представила", "презентувала", "дослідження", "опублікувала") in <a href="{link}">...</a>.
- "context_paragraph": a paragraph in Ukrainian giving wider background, preceding events, or official quotes (strictly 2-3 sentences, 30 to 55 words). Output ONLY the paragraph text (do not prepend "Контекст." or similar headers).
- "what_next_paragraph": a paragraph in Ukrainian detailing the consequences, who wins/loses, and future steps (strictly 2-3 sentences, 30 to 55 words). Output ONLY the paragraph text (do not prepend "Що далі." or similar headers).

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
            "main_paragraph": "Новий звіт від компанії Anthropic <a href=\"{link}\">демонструє</a>, як автономні агенти на базі моделі Claude 3.5 Sonnet успішно автоматизують до 80% рутинних завдань.",
            "context_paragraph": "Це частина ширшого тренду на автоматизацію. Раніше компанія представила інструмент Computer Use, що дозволяє ШІ взаємодіяти з інтерфейсом ПК так само, як це робить людина.",
            "what_next_paragraph": "Компанія Anthropic планує покращити точність роботи агентів у майбутніх релізах. Головними бенефіціарами стануть ІТ-компанії та відділи підтримки."
        }
        
    return {
        "importance_score": 8,
        "emoji_prefix": "🔥",
        "translated_title": "OpenAI обмежує GPT-5.6 на вимогу адміністрації Трампа",
        "main_paragraph": "OpenAI оголосила, що три нові моделі лінійки GPT-5.6 — Sol, Terra та Luna — <a href=\"{link}\">доступні</a> лише обмеженому колу партнерів.",
        "context_paragraph": "Це частина тиску адміністрації Трампа на AI-компанії. Раніше уряд змусив Anthropic зняти модель Fable 5, заборонивши доступ іноземцям.",
        "what_next_paragraph": "Широкий доступ планується найближчими тижнями, але регуляторні затримки можуть посилити позиції Китаю в AI-перегонах."
    }

def format_telegram_post(source: str, link: str, processed_data: dict) -> str:
    """
    Combines the structured JSON output from Groq into a premium editorial layout.
    """
    emoji_prefix = str(processed_data.get("emoji_prefix", "🤖")).strip()
    title = str(processed_data.get("translated_title", "Без назви")).strip()
    
    # Extract components
    main_p = str(processed_data.get("main_paragraph", "")).strip()
    context = str(processed_data.get("context_paragraph", "")).strip()
    what_next = str(processed_data.get("what_next_paragraph", "")).strip()
    
    # HTML escape the link
    escaped_link = html.escape(link)
    
    # Process link in the main paragraph if present
    if main_p:
        # Replace {link} placeholder if present
        main_p = main_p.replace('{link}', link)
        # Force any <a> tag in main_p to point to the correct link
        main_p = re.sub(r'<a(?:\s+[^>]*)?>', f'<a href="{escaped_link}">', main_p)
        
    # Helper to assemble body text
    def assemble_body(m_p, ctx, w_n) -> str:
        paragraphs = []
        if m_p:
            paragraphs.append(m_p)
        if ctx:
            if not ctx.lower().startswith("контекст"):
                paragraphs.append(f"<b>Контекст.</b> {ctx}")
            else:
                paragraphs.append(ctx)
        if w_n:
            if not w_n.lower().startswith("що далі"):
                paragraphs.append(f"<b>Що далі.</b> {w_n}")
            else:
                paragraphs.append(w_n)
        return "\n\n".join(paragraphs)

    body_text = assemble_body(main_p, context, what_next)
    
    # Define footer template
    footer = f'\n\n<a href="{escaped_link}">Джерело</a> | @raumainews'
    
    # Helper to calculate clean rendered character count
    def get_rendered_len(b_t: str) -> int:
        test_post = f"{emoji_prefix} {title}\n\n{b_t}\n\nДжерело | @raumainews"
        test_post_stripped = re.sub(r'<[^>]+>', '', test_post)
        return len(test_post_stripped)

    # Programmatic safety check: keep it strictly under 1000 characters (Telegram limit is 1024)
    if get_rendered_len(body_text) > 1000:
        logger.info(f"Generated post length ({get_rendered_len(body_text)} chars) exceeds safety limit. Truncating...")
        
        # 1. Try to trim 'what_next' sentence by sentence
        if what_next:
            what_next_sentences = re.split(r'(?<=[.!?])\s+', what_next)
            while len(what_next_sentences) > 1 and get_rendered_len(body_text) > 1000:
                what_next_sentences.pop()
                what_next = " ".join(what_next_sentences).strip()
                body_text = assemble_body(main_p, context, what_next)
                
            # If even 1 sentence is too long, drop what_next entirely
            if get_rendered_len(body_text) > 1000:
                what_next = ""
                body_text = assemble_body(main_p, context, what_next)

        # 2. Try to trim 'context' sentence by sentence
        if context and get_rendered_len(body_text) > 1000:
            context_sentences = re.split(r'(?<=[.!?])\s+', context)
            while len(context_sentences) > 1 and get_rendered_len(body_text) > 1000:
                context_sentences.pop()
                context = " ".join(context_sentences).strip()
                body_text = assemble_body(main_p, context, what_next)
                
            # If even 1 sentence is too long, drop context entirely
            if get_rendered_len(body_text) > 1000:
                context = ""
                body_text = assemble_body(main_p, context, what_next)

        # 3. Last resort: if still too long, strip tags from main_p and cut character count hard
        if get_rendered_len(body_text) > 1000:
            logger.warning("Post is still too long after dropping context/what_next. Hard-truncating main paragraph.")
            main_p = re.sub(r'<[^>]+>', '', main_p)  # Strip HTML tags from main_p to make character cutting safe
            
            # Find maximum main_p length to satisfy 1000 limit
            # Limit = 1000 - len(emoji_prefix) - len(title) - len("Джерело | @raumainews") - formatting chars (~15)
            max_main_len = 1000 - len(emoji_prefix) - len(title) - 25
            if len(main_p) > max_main_len:
                main_p = main_p[:max_main_len - 3].strip() + "..."
            
            body_text = assemble_body(main_p, "", "")

    post_text = f"{emoji_prefix} <b>{html.escape(title, quote=False)}</b>\n\n{body_text}{footer}"
    return post_text.strip()
