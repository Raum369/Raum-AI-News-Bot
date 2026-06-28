import httpx
import logging
from app.config import settings

logger = logging.getLogger(__name__)

async def send_to_channel(text: str, image_url: str | None = None) -> bool:
    """
    Sends an HTML-formatted message (with an optional photo) to the target Telegram channel.
    If image_url is provided, it uses the sendPhoto method. Falls back to sendMessage if photo
    sending fails or if the text is longer than 1024 characters.
    """
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHANNEL_ID:
        logger.info("[Mock Telegram Post] Token or Channel ID missing. Printing output:")
        print("=" * 60)
        if image_url:
            print(f"[Image URL]: {image_url}")
        print(text)
        print("=" * 60)
        return True

    # Check if we should try sending a photo
    use_photo = bool(image_url and len(text) <= 1024)
    
    if use_photo:
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendPhoto"
        payload = {
            "chat_id": settings.TELEGRAM_CHANNEL_ID,
            "photo": image_url,
            "caption": text,
            "parse_mode": "HTML"
        }
    else:
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": settings.TELEGRAM_CHANNEL_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload)
            data = response.json()
            
            if response.status_code == 200 and data.get("ok"):
                logger.info(f"Successfully posted to Telegram (photo={use_photo}).")
                return True
            else:
                description = data.get('description', 'Unknown error')
                logger.error(f"Telegram API returned an error (photo={use_photo}): {description}")
                
                # Fallback to text message if photo sending failed
                if use_photo:
                    logger.info("Attempting fallback to text-only message...")
                    fallback_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
                    fallback_payload = {
                        "chat_id": settings.TELEGRAM_CHANNEL_ID,
                        "text": text,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True
                    }
                    fallback_resp = await client.post(fallback_url, json=fallback_payload)
                    fallback_data = fallback_resp.json()
                    if fallback_resp.status_code == 200 and fallback_data.get("ok"):
                        logger.info("Fallback text-only message posted successfully.")
                        return True
                    else:
                        logger.error(f"Fallback text-only message also failed: {fallback_data.get('description')}")
                
                return False
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False
