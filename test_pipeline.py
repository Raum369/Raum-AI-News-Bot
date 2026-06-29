import sys
import asyncio
import logging
from unittest.mock import patch
from app.db import init_db
from app.main import check_and_publish_news
import app.parser

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Set logger to INFO to see all steps
logging.getLogger("app.main").setLevel(logging.INFO)

async def run_test():
    print("=" * 60)
    print("🚀 STARTING LOCAL PIPELINE TEST")
    print("=" * 60)
    print("Initializing database...")
    await init_db()
    
    # Save the original fetch function
    original_fetch = app.parser.fetch_all_new_articles
    
    # Define a wrapper that filters out published articles and limits to 1 new article
    async def limited_fetch():
        from app.db import is_article_published
        articles = await original_fetch()
        print(f"Total articles found in feeds: {len(articles)}.")
        
        unpublished = []
        for art in articles:
            if not await is_article_published(art["link"]):
                unpublished.append(art)
                
        print(f"Total unpublished articles: {len(unpublished)}.")
        print("Limiting to the first 1 unpublished article for this test run to prevent rate-limiting.")
        return unpublished[:1]
    
    # Patch the parser with the limited one
    with patch("app.main.fetch_all_new_articles", limited_fetch):
        await check_and_publish_news()
        
    print("=" * 60)
    print("✅ TEST PIPELINE COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_test())
