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
    
    # Define a wrapper that limits output to 2 articles to save Groq API rate limits
    async def limited_fetch():
        articles = await original_fetch()
        print(f"Total articles found in feeds: {len(articles)}.")
        print("Limiting to top 2 articles for this test run to prevent rate-limiting.")
        return articles[:2]
    
    # Patch the parser with the limited one
    with patch("app.main.fetch_all_new_articles", limited_fetch):
        await check_and_publish_news()
        
    print("=" * 60)
    print("✅ TEST PIPELINE COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_test())
