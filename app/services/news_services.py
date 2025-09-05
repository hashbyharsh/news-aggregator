import asyncio
import hashlib
import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
import httpx
from aiohttp import ClientSession
from fastapi import HTTPException
from playwright.async_api import async_playwright, Browser, Page
import redis
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models import Article
from app.utils.similarity import calculate_article_similarity, extract_car_brand_model, group_articles_by_similarity, string_similarity, cosine_similarity_score
from app.config import config

logger = logging.getLogger(__name__)

class NewsService:
    def __init__(self):
        self.is_running = False
        self.client = httpx.AsyncClient()
        self.redis = redis.Redis(host='localhost', port=6379, db=0)
        
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def execute_news_workflow(self, db: Session) -> None:
        """Main workflow execution - scraping and processing"""
        if self.is_running:
            logger.warning("Workflow skipped because previous run is still in progress")
            return
        
        self.is_running = True
        try:
            logger.info("Starting news workflow...")
            await self.scrape_all_sources(db)
            await self.process_articles(db)
            logger.info("News workflow completed.")
        except Exception as error:
            logger.error(f"Error in workflow: {error}")
        finally:
            self.is_running = False


    # ========================
    # SCRAPING FUNCTIONALITY
    # ========================

    async def scrape_all_sources(self, db: Session) -> None:
        """Scrape all sources from config"""
        logger.info("Starting news scraping phase...")
        
        logger.info(f"Processing {len(config.NEWS_SOURCES)} sources for topic: {config.NEWS_TOPIC}")
        
        scraped_articles = []
        
        semaphore = asyncio.Semaphore(3)
        
        async def scrape_with_semaphore(source):
            async with semaphore:
                return await self.scrape_source(source, config.NEWS_TOPIC)
        
        tasks = [scrape_with_semaphore(source) for source in config.NEWS_SOURCES]
        
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=600 
            )
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to scrape {config.NEWS_SOURCES[i]}: {result}")
                    continue
                
                source = config.NEWS_SOURCES[i]
                articles = result if isinstance(result, list) else []
                scraped_articles.extend([{**article, "source": source} for article in articles])
                
        except asyncio.TimeoutError:
            logger.error("Scraping batch timed out after 10 minutes")
        except Exception as e:
            logger.error(f"Error in batch scraping: {e}")
        
        await self.validate_and_save_articles(db, scraped_articles, config.NEWS_TOPIC)
        
        logger.info("News scraping phase completed.")

    async def scrape_source(self, source: str, topic: str) -> List[Dict[str, str]]:
        """Scrape a single source with robust timeout handling and proper resource management"""
        logger.info(f"Scraping source: {source}")
        
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                return await asyncio.wait_for(
                    self._scrape_source_internal(source, topic, attempt + 1),
                    timeout=180
                )
                
            except asyncio.TimeoutError:
                logger.error(f"Source {source} timed out on attempt {attempt + 1}")
            except Exception as error:
                logger.error(f"Attempt {attempt + 1} failed for {source}: {error}")
            
            if attempt < max_retries - 1:
                wait_time = min(2 ** attempt, 10)
                logger.info(f"Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)
        
        logger.error(f"Failed to scrape {source} after {max_retries} attempts")
        return []

    async def _scrape_source_internal(self, source: str, topic: str, attempt: int) -> List[Dict[str, str]]:
        """Internal scraping method with proper resource management"""
        browser = None
        context = None
        page = None
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-accelerated-2d-canvas',
                        '--no-first-run',
                        '--no-zygote',
                        '--disable-gpu',
                        '--disable-background-timer-throttling',
                        '--disable-backgrounding-occluded-windows',
                        '--disable-renderer-backgrounding'
                    ]
                )
                
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1366, "height": 768},
                    extra_http_headers={
                        "accept-language": "en-US,en;q=0.9",
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                        "cache-control": "no-cache",
                    }
                )
                
                page = await context.new_page()
                
                await page.goto(source, wait_until="domcontentloaded", timeout=45000)
                logger.debug(f"Navigation to {source} completed")
                
                try:
                    await page.wait_for_selector(
                        'article, div[class*="news"], div[class*="story"], div[class*="post"], div[class*="item"], div[class*="td-module"], .o-fznJEU, .o-cXgGJk, h1, h2, h3',
                        timeout=10000
                    )
                except Exception:
                    logger.warning(f"Timeout waiting for selectors on {source}, proceeding with available content")
                    await asyncio.sleep(2)
                
                logger.info(f"Successfully loaded: {source}")
                
                articles = await self.extract_articles(page, source)
                logger.info(f"Found {len(articles)} potential news from {source}")
                
                content_tasks = []
                for i, article in enumerate(articles[:5]):
                    task = asyncio.create_task(self.safe_scrape_content(article))
                    content_tasks.append(task)
                
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*content_tasks, return_exceptions=True),
                        timeout=120
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"Content scraping timed out for {source}")
                
                keywords = self.get_topic_keywords(topic)
                relevant_articles = []
                
                for article in articles:
                    try:
                        is_relevant = await self.check_relevance(
                            article["title"], 
                            article.get("content", ""), 
                            topic, 
                            keywords
                        )
                        if is_relevant:
                            relevant_articles.append(article)
                    except Exception as e:
                        logger.error(f"Error checking relevance for article {article['title']}: {e}")
                        continue
                
                logger.info(f"{len(relevant_articles)} relevant news found for topic: {topic}")
                return relevant_articles[:20]
                
        except Exception as e:
            logger.error(f"Error in _scrape_source_internal for {source}: {e}")
            raise
        finally:
            try:
                if page:
                    await page.close()
                if context:
                    await context.close()
                if browser:
                    await browser.close()
            except Exception as cleanup_error:
                logger.debug(f"Cleanup error for {source}: {cleanup_error}")

    async def safe_scrape_content(self, article: Dict[str, str]) -> None:
        """Safely scrape content for a single article"""
        try:
            article_content = await asyncio.wait_for(
                self.scrape_article_content(article["url"]),
                timeout=30
            )
            if article_content and len(article_content) > 200:
                article["content"] = article_content
            else:
                logger.debug(f"Insufficient content for {article['url']}: {len(article_content or '')} chars")
        except asyncio.TimeoutError:
            logger.warning(f"Timeout scraping content for {article['url']}")
        except Exception as e:
            logger.error(f"Failed to scrape content for {article['url']}: {str(e)}")

    async def extract_articles(self, page: Page, source_url: str) -> List[Dict[str, str]]:
        """Extract articles using source-specific selectors with better error handling"""
        logger.debug(f"Extracting articles from {source_url}")
        
        source_selectors = {
            "https://auto.economictimes.indiatimes.com": {
                "container": '.story-panel, .storyList, .et-story, .news-item, .story, div[class*="news"]',
                "title": 'h2 a, h3 a, .title, .headline, .story-headline',
                "content": '.content, .story-content, .summary, p',
                "url": 'a[href]'
            },
            "https://www.autocarindia.com/car-news": {
                "container": '.story-card, .article, .post, .news-item, .story',
                "title": '.story-headline, .entry-title, h2, h3, .title, .headline',
                "content": '.story-summary, .summary, .excerpt, .entry-content, p',
                "url": 'a[href]'
            },
            "https://www.rushlane.com": {
                "container": '.td-module-container, .post, .td-post, .entry, .news-item',
                "title": '.entry-title, .td-post-title, h2, h3, h4, .td-module-title',
                "content": '.td-excerpt, .td-post-content, .entry-content, .entry-summary, .excerpt, p',
                "url": '.td-module-title a, .entry-title a, a[href]'
            },
            "https://gaadiwaadi.com": {
                "container": '.td-module-container, .post, .td-post, .entry, .news-item',
                "title": '.entry-title, .td-post-title, h2, h3, h4, .td-module-title',
                "content": '.td-excerpt, .td-post-content, .entry-content, .entry-summary, .excerpt, p',
                "url": '.td-module-title a, .entry-title a, a[href]'
            },
            "https://www.autocarpro.in/news": {
                "container": '.news-item, .article, .post, .story, .content-item',
                "title": 'h2, h3, .title, .headline, .news-headline',
                "content": '.content, .summary, .excerpt, .news-content, p',
                "url": 'a[href]'
            },
            "https://auto.hindustantimes.com/auto/cars": {
                "container": '.story-card, .story, .article, .news-story, div[class*="story"]',
                "title": 'h2 a, h3 a, .title, .headline, .story-headline',
                "content": '.content, .summary, .story-summary, p',
                "url": 'a[href]'
            }
        }
        
        base_url = source_url.rstrip('/')
        selectors = None
        
        for url_pattern, sel in source_selectors.items():
            if base_url.startswith(url_pattern.rstrip('/')):
                selectors = sel
                break
        
        if not selectors:
            selectors = {
                "container": 'article, .post, .entry, .news-item, .article-item, .story, .td-module-container, .content-item',
                "title": 'h1, h2, h3, h4, .title, .headline, .entry-title, .td-post-title, .news-headline',
                "content": 'p, .content, .summary, .description, .excerpt, .entry-content, .td-post-content',
                "url": 'a[href]'
            }
        
        # Strategy 1: JSON-LD structured data
        try:
            articles = await page.evaluate("""
                () => {
                    const scripts = Array.from(document.querySelectorAll('script[type="application/ld+json"]'));
                    const articles = [];
                    
                    scripts.forEach(script => {
                        try {
                            const data = JSON.parse(script.textContent || '');
                            const processItem = (item) => {
                                if (item['@type'] === 'NewsArticle' || item['@type'] === 'Article') {
                                    articles.push({
                                        title: item.headline || item.name || '',
                                        content: item.description || item.articleBody || '',
                                        url: item.url || window.location.href,
                                        source: window.location.href
                                    });
                                }
                            };
                            
                            if (Array.isArray(data)) {
                                data.forEach(processItem);
                            } else {
                                processItem(data);
                            }
                        } catch (e) {
                            // Invalid JSON, skip
                        }
                    });
                    
                    return articles.filter(a => a.title && a.title.length > 10);
                }
            """)
            
            if articles and len(articles) > 0:
                logger.debug(f"Found {len(articles)} articles using JSON-LD strategy")
                return articles[:20]
        except Exception as e:
            logger.debug(f"JSON-LD extraction failed: {e}")
        
        # Strategy 2: Source-specific selectors with better error handling
        try:
            articles = await page.evaluate("""
                (args) => {
                    const { container, title, content, url, sourceUrl } = args;
                    
                    try {
                        const elements = Array.from(document.querySelectorAll(container));
                        const results = [];
                        
                        elements.forEach((el, index) => {
                            try {
                                const titleEl = el.querySelector(title);
                                const contentEl = el.querySelector(content);
                                const urlEl = el.querySelector(url);
                                
                                if (titleEl && titleEl.textContent) {
                                    const titleText = titleEl.textContent.trim();
                                    const contentText = contentEl ? contentEl.textContent.trim() : '';
                                    let articleUrl = sourceUrl;
                                    
                                    if (urlEl && urlEl.href) {
                                        try {
                                            articleUrl = new URL(urlEl.href, document.baseURI).href;
                                        } catch (e) {
                                            // Use source URL if URL parsing fails
                                        }
                                    }
                                    
                                    if (titleText.length > 10) {
                                        results.push({
                                            title: titleText,
                                            content: contentText,
                                            url: articleUrl,
                                            source: sourceUrl
                                        });
                                    }
                                }
                            } catch (e) {
                                console.log('Error processing element:', e);
                            }
                        });
                        
                        return results.filter(a => a.title && a.title.length > 10);
                    } catch (e) {
                        console.log('Error in selector strategy:', e);
                        return [];
                    }
                }
            """, {
                "container": selectors["container"],
                "title": selectors["title"],
                "content": selectors["content"],
                "url": selectors["url"],
                "sourceUrl": source_url
            })
            
            if articles and len(articles) > 0:
                logger.debug(f"Found {len(articles)} articles using source-specific selectors")
                return articles[:20]
        except Exception as e:
            logger.debug(f"Source-specific extraction failed: {e}")
        
        # Strategy 3: Generic fallback with improved logic
        try:
            articles = await page.evaluate("""
                (sourceUrl) => {
                    try {
                        const headings = Array.from(document.querySelectorAll('h1, h2, h3, h4, .headline, .title'));
                        const result = [];
                        
                        headings.forEach(heading => {
                            try {
                                const title = heading.textContent ? heading.textContent.trim() : '';
                                if (title && title.length > 10 && title.length < 200) {
                                    let content = '';
                                    let url = sourceUrl;
                                    
                                    // Try to find associated link
                                    const link = heading.querySelector('a') || heading.closest('a');
                                    if (link && link.href) {
                                        try {
                                            url = new URL(link.href, document.baseURI).href;
                                        } catch (e) {
                                            // Use source URL if parsing fails
                                        }
                                    }
                                    
                                    // Look for content in nearby elements
                                    let nextElement = heading.nextElementSibling;
                                    let attempts = 0;
                                    
                                    while (nextElement && attempts < 5) {
                                        if (nextElement.tagName === 'P' && nextElement.textContent) {
                                            const text = nextElement.textContent.trim();
                                            if (text.length > 50) {
                                                content = text;
                                                break;
                                            }
                                        }
                                        nextElement = nextElement.nextElementSibling;
                                        attempts++;
                                    }
                                    
                                    // Also check parent container for content
                                    if (!content) {
                                        const parent = heading.closest('article, .post, .news-item, .story');
                                        if (parent) {
                                            const paragraphs = parent.querySelectorAll('p');
                                            for (const p of paragraphs) {
                                                if (p.textContent && p.textContent.trim().length > 50) {
                                                    content = p.textContent.trim();
                                                    break;
                                                }
                                            }
                                        }
                                    }
                                    
                                    result.push({
                                        title,
                                        content: content || '',
                                        url,
                                        source: sourceUrl
                                    });
                                }
                            } catch (e) {
                                console.log('Error processing heading:', e);
                            }
                        });
                        
                        return result.slice(0, 20);
                    } catch (e) {
                        console.log('Error in generic strategy:', e);
                        return [];
                    }
                }
            """, source_url)
            
            logger.debug(f"Found {len(articles)} articles using generic strategy")
            return articles
            
        except Exception as e:
            logger.error(f"All extraction strategies failed for {source_url}: {e}")
            return []

    async def scrape_article_content(self, url: str) -> str:
        """Scrape full article content from a URL with timeout protection and proper cleanup"""
        browser = None
        context = None
        page = None
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu'
                    ]
                )
                context = await browser.new_context()
                page = await context.new_page()
                
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                
                content = await page.evaluate("""
                    () => {
                        // Remove unwanted elements
                        const unwanted = document.querySelectorAll('script, style, nav, header, footer, .advertisement, .ads, .social-share');
                        unwanted.forEach(el => el.remove());
                        
                        // Try multiple content selectors
                        const contentSelectors = [
                            '.article-content',
                            '.post-content', 
                            '.entry-content',
                            '.td-post-content',
                            '.story-content',
                            '.news-content',
                            'article p',
                            '.content p'
                        ];
                        
                        let content = '';
                        
                        for (const selector of contentSelectors) {
                            const elements = document.querySelectorAll(selector);
                            if (elements.length > 0) {
                                content = Array.from(elements)
                                    .map(el => el.textContent ? el.textContent.trim() : '')
                                    .filter(text => text.length > 20)
                                    .join('\\n');
                                if (content.length > 200) break;
                            }
                        }
                        
                        // Fallback: get all paragraphs
                        if (content.length < 200) {
                            const paragraphs = Array.from(document.querySelectorAll('p'));
                            content = paragraphs
                                .map(p => p.textContent ? p.textContent.trim() : '')
                                .filter(text => text.length > 20)
                                .join('\\n');
                        }
                        
                        return content;
                    }
                """)
                
                return content if content else ""
                
        except Exception as e:
            logger.error(f"Failed to scrape content from {url}: {str(e)}")
            return ""
        finally:
            # Ensure proper cleanup
            try:
                if page:
                    await page.close()
                if context:
                    await context.close()  
                if browser:
                    await browser.close()
            except Exception:
                pass
    
    async def check_relevance(self, title: str, content: str, topic: str, keywords: List[str]) -> bool:
        """Check if article is relevant based on keywords or car brand/model"""
        try:
            text = f"{title} {content}".lower()
            brand, model = extract_car_brand_model(text)  # Use imported function

            # If we found a car brand or model, it's definitely relevant
            if brand or model:
                return True

            # Check for topic keywords
            keyword_match = any(k.lower() in text for k in keywords)
            
            # Additional car-related terms for better filtering
            car_terms = [
                'automotive', 'vehicle', 'engine', 'transmission', 'fuel', 'mileage',
                'sedan', 'suv', 'hatchback', 'coupe', 'convertible', 'electric vehicle',
                'hybrid', 'diesel', 'petrol', 'launch', 'price', 'review', 'test drive',
                'showroom', 'dealer', 'booking', 'variant', 'feature', 'safety',
                'airbag', 'abs', 'esp', 'cruise control', 'sunroof', 'touchscreen'
            ]
            
            car_terms_match = any(term in text for term in car_terms)
            
            return keyword_match or car_terms_match
            
        except Exception as e:
            logger.error(f"Error in relevance check: {e}")
            return False
    
    def get_topic_keywords(self, topic: str) -> List[str]:
        """Get keywords for a topic"""
        keyword_map = {
            "car": [
                "car", "cars", "automobile", "vehicle", "automotive", "hatchback"
            ]
        }
        
        return keyword_map.get(topic.lower(), [topic])
    
    async def validate_and_save_articles(self, db: Session, scraped_articles: List[Dict], topic: str) -> None:
        """Validate and save articles, grouping different versions of the same story using enhanced similarity"""
        logger.debug(f"Validating {len(scraped_articles)} scraped articles.")
        
        if not scraped_articles:
            logger.info("No articles to validate and save")
            return
        
        valid_articles = []
        for article in scraped_articles:
            # Skip articles with insufficient content or generic titles
            if (not article.get("title") or 
                len(article.get("title", "")) < 10 or
                article.get("title", "").lower() in ["stay updated & make informed decisions", "latest news", "breaking news"]):
                logger.debug(f"Skipping article with insufficient/generic title: '{article.get('title', '')}'")
                continue
                
            # Skip if no meaningful content
            content_length = len(article.get("content", ""))
            if content_length < 30:  # Reduced minimum content length
                logger.debug(f"Skipping article '{article['title'][:50]}...' due to insufficient content ({content_length} chars)")
                continue
            
            valid_articles.append(article)
        
        if not valid_articles:
            logger.info("No valid articles found after filtering")
            return
        
        logger.debug(f"Processing {len(valid_articles)} valid articles for similarity grouping")

        groups = group_articles_by_similarity(valid_articles, similarity_threshold=0.70)
        
        saved_count = 0
        for group_id, group in groups.items():
            unique_sources = set(a["source"] for a in group)
            
            logger.debug(f"Group {group_id} has {len(group)} articles from {len(unique_sources)} sources: {list(unique_sources)}")
            
            if len(unique_sources) >= 1:
                representative = max(group, key=lambda x: len(x.get("content", "")), default=group[0])
                
                existing = db.query(Article).filter(
                    and_(
                        Article.source_url == representative["url"],
                        Article.title == representative["title"]
                    )
                ).first()
                
                if not existing:
                    try:
                        new_article = Article(
                            title=representative["title"],
                            content=representative["content"],
                            source_url=representative["url"],
                            group_id=group_id,
                            processed=False
                        )
                        db.add(new_article)
                        db.commit()
                        saved_count += 1
                        logger.info(f"Saved article: {representative['title'][:50]}... (Group: {group_id}, Sources: {len(unique_sources)})")
                    except Exception as e:
                        logger.error(f"Failed to save article {representative['title']}: {e}")
                        db.rollback()
                else:
                    logger.warning(f"Duplicate from same source skipped: {representative['url']}")
            else:
                logger.debug(f"Group {group_id} not saved, found in {len(unique_sources)} sources")
        
        logger.info(f"Saved {saved_count} validated articles for topic: {topic}")
    
    #  ========================
    #  PROCESSING FUNCTIONALITY
    #  ========================

    async def process_articles(self, db: Session) -> None:
        """Process unprocessed articles using GROQ LLM"""
        logger.info("Starting news processing phase...")
        
        unprocessed = db.query(Article).filter(Article.processed == False).all()
        
        if not unprocessed:
            logger.info("No unprocessed articles found")
            return
        
        logger.info(f"Processing {len(unprocessed)} unprocessed articles.")
        
        # Group articles by existing groupId or create new groups
        groups = {}
        
        for article in unprocessed:
            # Compute hash for article to check if already processed
            article_key = hashlib.sha256(f"{article.title}{article.content[:500]}".encode()).hexdigest()
            if self.redis.hexists("processed_articles", article_key):
                logger.info(f"Skipping already processed article: {article.title[:50]}...")
                article.processed = True
                article.processed_at = datetime.now()
                db.commit()
                continue
            
            if article.group_id:
                if article.group_id not in groups:
                    groups[article.group_id] = []
                groups[article.group_id].append(article)
            else:
                # Create new group for articles without groupId using enhanced similarity
                matched_group = None
                
                for group_id, group in groups.items():
                    # Use enhanced similarity calculation
                    similarity = calculate_article_similarity(
                        {'title': article.title, 'content': article.content[:200]},
                        {'title': group[0].title, 'content': group[0].content[:200]}
                    )
                    
                    if similarity > 0.70:  # Use same threshold as validation
                        matched_group = group_id
                        break
                
                if matched_group:
                    groups[matched_group].append(article)
                else:
                    new_group_id = str(uuid.uuid4())
                    groups[new_group_id] = [article]
        
        # Process each group
        for group_id, group in groups.items():
            await self.process_article_group(db, group_id, group)
        
        logger.info("News processing phase completed.")

    async def process_article_group(self, db: Session, group_id: str, group: List[Article]) -> None:
        """Process a group of similar articles using GROQ LLM"""
        if not group:
            return
        
        logger.info(f"Processing group {group_id} with {len(group)} articles.")
        
        try:
            combined_content = "\n\n".join([
                f"Source: {article.source_url}\nTitle: {article.title}\nContent: {article.content[:500] + '...' if len(article.content) > 500 else article.content}"
                for article in group
            ])

            group_key = hashlib.sha256(combined_content.encode()).hexdigest()
            if self.redis.hexists("processed_articles", group_key):
                logger.info(f"Skipping already processed group {group_id}")
                for article in group:
                    article.processed = True
                    article.processed_at = datetime.now()
                    article.group_id = group_id
                db.commit()
                return
            
            prompt = f"""You are a professional journalist and automotive expert. Your task is to merge and rewrite the following multiple versions of an article into a single, polished, publication-ready article in the specified format.

            ### Requirements:
            - **Headline**: One-line headline (max 300 characters) in this format: "Company X launches Product Y in India at INR Z lakhs" or similar, including key details (brand, action, price/date/numbers), using present tense, professional style (e.g., "Tata Motors launches Nexon EV Max in India at INR 17.74 lakhs ex-showroom").
            - **Subheadline**: Optional, 1–2 sentences (max 500 characters). Include only if it adds unique, non-repetitive details (e.g., additional specs, context, or outcomes not in the headline) in the same professional style (e.g., "The Nexon EV Max offers a 400 km range and advanced safety features.").
            - **Accuracy**: Verify facts across sources, resolve contradictions, ensure consistency.
            - **Impartiality**: Maintain a neutral, balanced, nonpartisan tone — avoid bias or opinions.
            - **Completeness**: Include full context, background, and key details in the article.
            - **Originality**: Write in your own words; no plagiarism or copy-paste. Add clear explanations or analysis where helpful.
            - **Professional Writing**: Use engaging, concise, clear language. Structure with introduction, body, conclusion.
            - **Style**: Follow reputable news outlets (e.g., Reuters, BBC, AP). Avoid fluff, jargon, sensationalism.
            - **Length**: Article body between 2,000 and 5,000 characters (roughly 300–800 words).
            - **Metadata**: Extract car brand (e.g., "Tata", "Hyundai") and model name (e.g., "Nexon", "Creta") or null if not found.
            - **Formatting**: Use the exact structure below, with section titles (Headline, Subheadline, Article, MetaData) and no '#' symbols in the output. Ensure proper spacing and newlines as shown.

            ### Output Format (Plain Text):
            [Generated headline (max 300 chars)]

            [Optional 1–2 sentence Subheadline (max 500 chars, non-repetitive, specific details if present, empty string if omitted)]

            [Article (max 2,000 - 3,000 chars, well-structured with paragraphs)]

            - Car Brand: [Car brand or null]
            - Model Name: [Car model or null]

            ### Source Versions:
            {combined_content}
            """

            response = await self.client.post(
                f"{config.GROQ_BASE_URL}/openai/v1/chat/completions",
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a professional journalist and automotive expert. Respond with plain text in the exact format specified."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.3
                },
                headers={
                    "Authorization": f"Bearer {config.GROQ_API_KEY}",
                    "Content-Type": "application/json"
                }
            )
            
            response.raise_for_status()
            ai_response = response.json()["choices"][0]["message"]["content"]
            
            try:
                lines = ai_response.splitlines()
                processed_content = ai_response
                brand_name = None
                model_name = None
                
                for i, line in enumerate(lines):
                    if line.startswith("- Car Brand:"):
                        brand_name = line.replace("- Car Brand: ", "").strip() or None
                    elif line.startswith("- Model Name:"):
                        model_name = line.replace("- Model Name: ", "").strip() or None
            except Exception as e:
                logger.warning(f"Failed to parse response for group {group_id}, using fallback extraction: {e}")
                processed_content = ai_response[:65535]
                full_text = f"{group[0].title} {group[0].content}"
                brand_name, model_name = extract_car_brand_model(full_text)
            
            MAX_CONTENT_LENGTH = 65535
            if len(processed_content) > MAX_CONTENT_LENGTH:
                processed_content = processed_content[:MAX_CONTENT_LENGTH-3] + "..."
                logger.warning(f"Truncated processed_content for group {group_id}")
            
            primary_article = group[0]
            primary_article.processed_content = processed_content
            primary_article.brand_name = brand_name
            primary_article.model_name = model_name
            primary_article.processed = True
            primary_article.processed_at = datetime.now()
            primary_article.group_id = group_id
            
            for i in range(1, len(group)):
                group[i].processed = True
                group[i].processed_at = datetime.now()
                group[i].group_id = group_id
                group[i].brand_name = brand_name
                group[i].model_name = model_name

            self.redis.hset("processed_articles", group_key, "processed")
            self.redis.expire("processed_articles", 3600)
            
            db.commit()
            logger.info(f"Successfully processed group {group_id} - Brand: {brand_name}, Model: {model_name}")
            
        except Exception as error:
            logger.error(f"Error processing group {group_id}: {error}")
            
            for article in group:
                if not article.brand_name or not article.model_name:
                    full_text = f"{article.title} {article.content}"
                    brand_name, model_name = extract_car_brand_model(full_text)
                    article.brand_name = brand_name
                    article.model_name = model_name
                
                article.processed = True
                article.processed_at = datetime.now()
                article.group_id = group_id

            self.redis.hset("processed_articles", group_key, "processed")
            self.redis.expire("processed_articles", 3600)
            
            db.commit()
        