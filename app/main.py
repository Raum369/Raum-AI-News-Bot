import asyncio
import logging
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import settings
from app.db import init_db, is_article_published, mark_article_published
from app.parser import fetch_all_new_articles
from app.processor import process_article, format_telegram_post
from app.telegram_client import send_to_channel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("app.main")

async def check_and_publish_news():
    """
    Main job that polls RSS feeds, filters duplicates,
    scores and ranks articles by importance, and posts
    the cream-of-the-crop to Telegram.
    """
    logger.info("Starting news check cycle...")
    
    try:
        articles = await fetch_all_new_articles()
        logger.info(f"Fetched {len(articles)} total articles from RSS feeds.")
        
        # 1. Filter out already processed articles
        new_articles = []
        for article in articles:
            url = article["link"]
            if not await is_article_published(url):
                new_articles.append(article)
                
        if not new_articles:
            logger.info("No new articles found since last cycle.")
            return

        logger.info(f"Found {len(new_articles)} new articles to evaluate.")
        
        # 2. Limit candidate pool to at most 6 articles to avoid excessive API calls
        candidates = []
        for article in new_articles[:6]:
            logger.info(f"Evaluating candidate: {article['title']}")
            processed_data = await process_article(
                source=article["source"],
                original_title=article["title"],
                original_summary=article["summary"]
            )
            candidates.append((article, processed_data))
            await asyncio.sleep(0.5)  # Polite delay between API calls

        # 3. Sort candidates by importance score (highest first)
        candidates.sort(key=lambda x: x[1].get("importance_score", 0), reverse=True)

        # 4. Selection logic:
        # - Always publish the single most important article.
        # - Also publish other articles if they are exceptionally hot (score >= 8), up to max 2 total.
        to_publish = []
        if candidates:
            to_publish.append(candidates[0])
            for candidate in candidates[1:]:
                if len(to_publish) >= 2:
                    break
                if candidate[1].get("importance_score", 0) >= 8:
                    to_publish.append(candidate)

        logger.info(f"Selected {len(to_publish)} articles to publish out of {len(candidates)} candidates.")

        # 5. Publish selected articles to Telegram
        published_urls = set()
        for article, processed_data in to_publish:
            post_text = format_telegram_post(
                source=article["source"],
                link=article["link"],
                processed_data=processed_data
            )
            
            logger.info(f"Posting article to Telegram: {article['title']} (Importance: {processed_data.get('importance_score')})")
            success = await send_to_channel(
                text=post_text,
                image_url=article.get("image_url")
            )
            
            if success:
                logger.info(f"Successfully posted article: {article['title']}")
                # Mark as published immediately
                await mark_article_published(
                    url=article["link"],
                    title=article["title"],
                    published_at=article["published_at"]
                )
                published_urls.add(article["link"])
                await asyncio.sleep(5)
            else:
                logger.error(f"Failed to post article: {article['title']}")

        # 6. Archive/Mark all other evaluated candidates in database so they are skipped in future cycles
        for article, _ in candidates:
            if article["link"] not in published_urls:
                # If it was chosen to publish but failed, don't mark it (let it retry)
                is_failed_publish = any(p[0]["link"] == article["link"] for p in to_publish) and article["link"] not in published_urls
                if not is_failed_publish:
                    logger.info(f"Archiving skipped/low-importance candidate: {article['title']}")
                    await mark_article_published(
                        url=article["link"],
                        title=article["title"],
                        published_at=article["published_at"]
                    )

        logger.info(f"Finished news check cycle. Published {len(published_urls)} posts.")

    except Exception as e:
        logger.exception(f"Error during check_and_publish_news execution: {e}")

async def main():
    logger.info("Initializing Raum AI News Bot database...")
    await init_db()
    logger.info("Database initialized.")

    # Setup the scheduler
    scheduler = AsyncIOScheduler()
    
    # Schedule job: runs immediately on start, and then every N hours
    scheduler.add_job(
        check_and_publish_news,
        "interval",
        hours=settings.POLL_INTERVAL_HOURS,
        id="check_news_job"
    )
    
    # Also trigger one check run immediately on startup
    scheduler.add_job(check_and_publish_news, id="initial_check_job")
    
    scheduler.start()
    logger.info(f"Scheduler started. Polling every {settings.POLL_INTERVAL_HOURS} hours.")
    
    # Keep the main loop running
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown signal received. Stopping scheduler...")
        scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
