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

    use_photo = bool(image_url and len(text) <= 1024)
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            if use_photo:
                logger.info(f"Downloading image from {image_url}...")
                try:
                    img_resp = await client.get(image_url)
                    if img_resp.status_code == 200:
                        image_bytes = img_resp.content
                        files = {"photo": ("image.jpg", image_bytes, "image/jpeg")}
                        data = {
                            "chat_id": settings.TELEGRAM_CHANNEL_ID,
                            "caption": text,
                            "parse_mode": "HTML"
                        }
                        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendPhoto"
                        logger.info("Uploading photo to Telegram...")
                        response = await client.post(url, data=data, files=files)
                        res_json = response.json()
                        if response.status_code == 200 and res_json.get("ok"):
                            logger.info("Successfully posted to Telegram with uploaded photo.")
                            return True
                        else:
                            description = res_json.get('description', 'Unknown error')
                            logger.error(f"Telegram photo upload failed: {description}")
                    else:
                        logger.error(f"Failed to download image: HTTP {img_resp.status_code}")
                except Exception as img_err:
                    logger.error(f"Error downloading/sending photo: {img_err}")
                
                # If we get here, photo sending failed; fall back to text message
                logger.info("Attempting fallback to text-only message...")

            # Send text-only message
            url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": settings.TELEGRAM_CHANNEL_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            response = await client.post(url, json=payload)
            res_json = response.json()
            if response.status_code == 200 and res_json.get("ok"):
                logger.info("Successfully posted text-only message to Telegram.")
                return True
            else:
                description = res_json.get('description', 'Unknown error')
                logger.error(f"Telegram sendMessage failed: {description}")
                return False
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False
