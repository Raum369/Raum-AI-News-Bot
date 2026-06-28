import feedparser
import httpx
import logging
import asyncio
from datetime import datetime, timezone, timedelta
import re

logger = logging.getLogger(__name__)

# Curated list of AI RSS feeds
RSS_SOURCES = {
    "OpenAI": "https://openai.com/news/rss.xml",
    "Anthropic": "https://raw.githubusercontent.com/alan-turing-institute/ai-rss-feeds/main/feeds/anthropic-news.xml",
    "TechCrunch": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "VentureBeat": "https://venturebeat.com/category/ai/feed/",
}

# Premium fallback images per source (Unsplash, public domain)
# Used when RSS feed does not contain an embedded image
SOURCE_FALLBACK_IMAGES = {
    "OpenAI": "https://images.unsplash.com/photo-1677442136019-21780ecad995?w=1200&q=80",
    "Anthropic": "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?w=1200&q=80",
    "TechCrunch": "https://images.unsplash.com/photo-1518770660439-4636190af475?w=1200&q=80",
    "The Verge": "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=1200&q=80",
    "VentureBeat": "https://images.unsplash.com/photo-1635070041078-e363dbe005cb?w=1200&q=80",
}

# Keywords to filter general feeds (like The Verge) to only include AI articles
AI_KEYWORDS = ["ai", "robot", "llama", "gpt", "openai", "anthropic", "gemini", "copilot", "midjourney", "claude", "artificial intelligence", "machine learning", "neural network", "llm"]

def extract_image_url(entry) -> str | None:
    """
    Attempts to extract a primary image URL from an RSS feed entry.
    Checks media_content, enclosures, links, and HTML img tags.
    """
    # 1. Look in media:content / media_content
    media_content = entry.get("media_content")
    if media_content:
        for media in media_content:
            if isinstance(media, dict):
                # prioritize image medium or type
                if media.get("medium") == "image" or "image" in media.get("type", ""):
                    url = media.get("url")
                    if url:
                        return url

    # 2. Look in enclosures (standard RSS attachment tag)
    enclosures = entry.get("enclosures")
    if enclosures:
        for enc in enclosures:
            if isinstance(enc, dict) and "image" in enc.get("type", ""):
                url = enc.get("href")
                if url:
                    return url

    # 3. Look in links list
    links = entry.get("links", [])
    for link in links:
        if isinstance(link, dict) and "image" in link.get("type", ""):
            url = link.get("href")
            if url:
                return url

    # 4. Search in summary or description or content for HTML <img> tag
    for field in ["summary", "description", "content"]:
        val = entry.get(field)
        if isinstance(val, list):
            # content field in feedparser is usually a list of dicts
            val = "".join([item.get("value", "") for item in val if isinstance(item, dict)])
        if val and isinstance(val, str):
            # Extract src of the first img tag
            match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', val, re.IGNORECASE)
            if match:
                url = match.group(1)
                if url:
                    return url

    return None

async def fetch_source_articles(source_name: str, feed_url: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    async with httpx.AsyncClient(headers=headers, timeout=15.0, follow_redirects=True) as client:
        try:
            logger.info(f"Fetching RSS feed for {source_name}...")
            response = await client.get(feed_url)
            response.raise_for_status()
            
            # feedparser can parse direct string content
            feed = feedparser.parse(response.text)
            
            articles = []
            for entry in feed.entries[:15]:  # Slightly larger pool to filter from
                title = entry.get("title", "").strip()
                summary = entry.get("summary", "").strip() or entry.get("description", "").strip()
                link = entry.get("link", "")
                
                # Filter for The Verge to ensure only AI articles are processed
                if source_name == "The Verge":
                    text_to_check = (title + " " + summary).lower()
                    if not any(keyword in text_to_check for keyword in AI_KEYWORDS):
                        continue
                
                # Age filter: skip articles older than 5 days
                pub_parsed = entry.get("published_parsed")
                if pub_parsed:
                    try:
                        pub_dt = datetime(*pub_parsed[:6], tzinfo=timezone.utc)
                        if datetime.now(timezone.utc) - pub_dt > timedelta(days=5):
                            logger.info(f"Skipping old article ({pub_dt.strftime('%Y-%m-%d')}): {title}")
                            continue
                    except Exception as date_err:
                        logger.warning(f"Failed to parse date for {title}: {date_err}")

                # Clean up/normalize trailing slashes
                if link and link.endswith("/"):
                    link = link[:-1]

                articles.append({
                    "source": source_name,
                    "title": title,
                    "link": link.strip(),
                    "summary": summary,
                    "published_at": entry.get("published", "") or entry.get("pubDate", ""),
                    "image_url": extract_image_url(entry) or SOURCE_FALLBACK_IMAGES.get(source_name)
                })
            return articles[:10]
        except Exception as e:
            logger.error(f"Failed to fetch/parse feed {source_name}: {e}")
            return []

async def fetch_all_new_articles():
    tasks = []
    for source_name, feed_url in RSS_SOURCES.items():
        tasks.append(fetch_source_articles(source_name, feed_url))
        
    results = await asyncio.gather(*tasks)
    
    # Flatten array
    all_articles = []
    for source_articles in results:
        all_articles.extend(source_articles)
        
    return all_articles
