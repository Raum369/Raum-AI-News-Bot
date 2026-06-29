import feedparser
import httpx
import logging
import asyncio
from datetime import datetime, timezone, timedelta
import re
import urllib.parse
import html as html_lib

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
    "OpenAI": [
        "https://images.unsplash.com/photo-1677442136019-21780ecad995?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1507668077129-56e32842fceb?auto=format&fit=crop&w=1200&q=80"
    ],
    "Anthropic": [
        "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1607604276583-eef5d076aa5f?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1639762681485-074b7f938ba0?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?auto=format&fit=crop&w=1200&q=80"
    ],
    "TechCrunch": [
        "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1519389950473-47ba0277781c?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1531297484001-80022131f5a1?auto=format&fit=crop&w=1200&q=80"
    ],
    "The Verge": [
        "https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1563986768609-322da13575f3?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1542751371-adc38448a05e?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?auto=format&fit=crop&w=1200&q=80"
    ],
    "VentureBeat": [
        "https://images.unsplash.com/photo-1635070041078-e363dbe005cb?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1605810230434-7631ac76ec81?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1677442136019-21780ecad995?auto=format&fit=crop&w=1200&q=80"
    ],
    "BuildFastWithAI": [
        "https://images.unsplash.com/photo-1677442136019-21780ecad995?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1507668077129-56e32842fceb?auto=format&fit=crop&w=1200&q=80"
    ],
    "TransparencyCoalition": [
        "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1450133064473-71024230f91b?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1521791136064-7986c2920216?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1427504494785-3a9ca7044f45?auto=format&fit=crop&w=1200&q=80"
    ],
}

import hashlib

def get_source_fallback_image(source_name: str, article_link: str) -> str:
    images = SOURCE_FALLBACK_IMAGES.get(source_name)
    if not images:
        images = ["https://images.unsplash.com/photo-1677442136019-21780ecad995?w=1200&q=80"]
    
    # Generate stable index from URL
    hash_val = int(hashlib.md5(article_link.encode('utf-8')).hexdigest(), 16)
    idx = hash_val % len(images)
    return images[idx]


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

async def scrape_og_image(url: str) -> str | None:
    """
    Scrapes the target URL to extract the Open Graph or Twitter Card image URL.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        logger.info(f"Scraping OG image for URL: {url}")
        async with httpx.AsyncClient(headers=headers, timeout=5.0, follow_redirects=True) as client:
            response = await client.get(url)
            if response.status_code != 200:
                logger.warning(f"Failed to scrape webpage, status code: {response.status_code}")
                return None
            
            html_content = response.text
            
            # Match og:image with property before content
            match = re.search(r'<meta\s+[^>]*property=["\']og:image["\']\s+[^>]*content=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
            if not match:
                # Match og:image with content before property
                match = re.search(r'<meta\s+[^>]*content=["\']([^"\']+)["\']\s+[^>]*property=["\']og:image["\']', html_content, re.IGNORECASE)
            if not match:
                # Match twitter:image with name before content
                match = re.search(r'<meta\s+[^>]*name=["\']twitter:image["\']\s+[^>]*content=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
            if not match:
                # Match twitter:image with content before name
                match = re.search(r'<meta\s+[^>]*content=["\']([^"\']+)["\']\s+[^>]*name=["\']twitter:image["\']', html_content, re.IGNORECASE)
                
            if match:
                img_url = match.group(1).strip()
                resolved_url = urllib.parse.urljoin(url, img_url)
                logger.info(f"Successfully scraped OG image: {resolved_url}")
                return resolved_url
    except Exception as e:
        logger.warning(f"Failed to scrape OG image from {url}: {e}")
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
                link = entry.get("link", "").strip()
                if "openai.com" in link and not link.endswith("/"):
                    link += "/"
                
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

                articles.append({
                    "source": source_name,
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "published_at": entry.get("published", "") or entry.get("pubDate", ""),
                    "image_url": extract_image_url(entry) or get_source_fallback_image(source_name, link)
                })
            return articles[:10]
        except Exception as e:
            logger.error(f"Failed to fetch/parse feed {source_name}: {e}")
            return []

MONTH_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12
}

def parse_date_from_url(url: str) -> datetime | None:
    url_lower = url.lower()
    months_pattern = '|'.join(MONTH_MAP.keys())
    match = re.search(rf'({months_pattern})-?(\d+)-?(\d{{4}})', url_lower)
    if match:
        month_str, day_str, year_str = match.groups()
        month = MONTH_MAP.get(month_str)
        if month:
            try:
                return datetime(int(year_str), month, int(day_str), tzinfo=timezone.utc)
            except ValueError:
                pass
    return None

def clean_paragraph_text(text: str) -> str:
    sentences = re.split(r'(?<=[.!?])\s+', text)
    cleaned_sentences = []
    for s in sentences:
        s_lower = s.lower()
        is_promo = (
            "build fast with ai" in s_lower or
            "6-week program" in s_lower or
            "intensive 6-week" in s_lower or
            "rag pipelines" in s_lower or
            "don't just use chatgpt" in s_lower or
            "don't just use" in s_lower or
            "learn to build" in s_lower or
            "our program" in s_lower
        )
        if not is_promo:
            cleaned_sentences.append(s)
    return " ".join(cleaned_sentences).strip()

async def scrape_buildfastwithai_digests() -> list:
    logger.info("Scraping BuildFastWithAI...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    articles = []
    async with httpx.AsyncClient(headers=headers, timeout=15.0, follow_redirects=True) as client:
        try:
            r = await client.get("https://www.buildfastwithai.com/blogs")
            if r.status_code != 200:
                logger.error(f"Failed to fetch BF index: {r.status_code}")
                return []
            
            blog_paths = set(re.findall(r'href=["\'](/blogs/ai-news-today-[\w\-]+)["\']', r.text))
            
            for path in sorted(blog_paths):
                url = f"https://www.buildfastwithai.com{path}"
                dt = parse_date_from_url(url)
                if not dt:
                    continue
                
                # Age filter: skip digests older than 5 days
                if (datetime.now(timezone.utc) - dt) > timedelta(days=5):
                    continue
                
                page_resp = await client.get(url)
                if page_resp.status_code != 200:
                    continue
                
                html_content = page_resp.text
                matches = list(re.finditer(r"<(p|h2|h3|h4|div)[^>]*>(?:&nbsp;|\s)*(\d+)\.\s*(.*?)</\1>", html_content, re.IGNORECASE))
                
                for i, m in enumerate(matches):
                    tag, num_str, raw_title = m.groups()
                    story_title = re.sub(r"<[^>]+>", "", raw_title).strip()
                    story_title = html_lib.unescape(story_title)
                    
                    start_idx = m.end()
                    if i + 1 < len(matches):
                        end_idx = matches[i+1].start()
                    else:
                        faq_idx = html_content.find("Frequently Asked Questions", start_idx)
                        if faq_idx != -1:
                            end_idx = faq_idx
                        else:
                            end_idx = len(html_content)
                            
                    story_html = html_content[start_idx:end_idx]
                    paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", story_html, re.IGNORECASE)
                    paragraphs_clean = []
                    for p in paragraphs:
                        p_clean = re.sub(r"<[^>]+>", "", p).strip()
                        p_clean = html_lib.unescape(p_clean)
                        p_clean = clean_paragraph_text(p_clean)
                        if p_clean and not p_clean.startswith("&nbsp;"):
                            paragraphs_clean.append(p_clean)
                            
                    story_summary = "\n\n".join(paragraphs_clean)
                    story_url = f"{url}#story{num_str}"
                    
                    articles.append({
                        "source": "BuildFastWithAI",
                        "title": story_title,
                        "link": story_url,
                        "summary": story_summary,
                        "published_at": dt.isoformat(),
                        "image_url": get_source_fallback_image("BuildFastWithAI", story_url)
                    })
        except Exception as e:
            logger.error(f"Error scraping BuildFastWithAI: {e}")
    return articles

async def scrape_transparencycoalition_updates() -> list:
    logger.info("Scraping Transparency Coalition...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    articles = []
    async with httpx.AsyncClient(headers=headers, timeout=15.0, follow_redirects=True) as client:
        try:
            r = await client.get("https://www.transparencycoalition.ai/news")
            if r.status_code != 200:
                logger.error(f"Failed to fetch TC index: {r.status_code}")
                return []
                
            update_paths = set(re.findall(r'href=["\'](/news/ai-legislative-update-[\w\-]+)["\']', r.text))
            
            for path in sorted(update_paths):
                url = f"https://www.transparencycoalition.ai{path}"
                dt = parse_date_from_url(url)
                if not dt:
                    continue
                    
                # Age filter: skip updates older than 5 days
                if (datetime.now(timezone.utc) - dt) > timedelta(days=5):
                    continue
                
                page_resp = await client.get(url)
                if page_resp.status_code != 200:
                    continue
                    
                html_content = page_resp.text
                start_match = re.search(r"<h3>AI bill action this week</h3>", html_content, re.IGNORECASE)
                if not start_match:
                    start_match = re.search(r"<h3>", html_content, re.IGNORECASE)
                
                start_pos = start_match.end() if start_match else 0
                end_match = re.search(r"<h3>Track AI legislation", html_content, re.IGNORECASE)
                end_pos = end_match.start() if end_match else len(html_content)
                
                body_html = html_content[start_pos:end_pos]
                state_matches = list(re.finditer(r"<h4[^>]*>(.*?)</h4>", body_html, re.IGNORECASE))
                
                for i, m in enumerate(state_matches):
                    state_name = re.sub(r"<[^>]+>", "", m.group(1)).strip()
                    state_name = html_lib.unescape(state_name)
                    
                    state_start = m.end()
                    if i + 1 < len(state_matches):
                        state_end = state_matches[i+1].start()
                    else:
                        state_end = len(body_html)
                        
                    state_html = body_html[state_start:state_end]
                    elements = re.findall(r"<(p|li)[^>]*>(.*?)</\1>", state_html, re.IGNORECASE)
                    lines = []
                    for tag, content in elements:
                        clean = re.sub(r"<[^>]+>", "", content).strip()
                        clean = html_lib.unescape(clean)
                        if clean and not clean.startswith("&nbsp;"):
                            if tag == "li":
                                lines.append(f"- {clean}")
                            else:
                                lines.append(clean)
                                
                    state_text = "\n\n".join(lines)
                    state_slug = re.sub(r"[^\w]+", "-", state_name.lower()).strip("-")
                    state_url = f"{url}#{state_slug}"
                    
                    articles.append({
                        "source": "TransparencyCoalition",
                        "title": f"US AI Legislative Update: {state_name}",
                        "link": state_url,
                        "summary": state_text,
                        "published_at": dt.isoformat(),
                        "image_url": get_source_fallback_image("TransparencyCoalition", state_url)
                    })
        except Exception as e:
            logger.error(f"Error scraping Transparency Coalition: {e}")
    return articles

async def fetch_all_new_articles():
    tasks = []
    for source_name, feed_url in RSS_SOURCES.items():
        tasks.append(fetch_source_articles(source_name, feed_url))
        
    tasks.append(scrape_buildfastwithai_digests())
    tasks.append(scrape_transparencycoalition_updates())
        
    results = await asyncio.gather(*tasks)
    
    # Flatten array
    all_articles = []
    for source_articles in results:
        all_articles.extend(source_articles)
        
    return all_articles
