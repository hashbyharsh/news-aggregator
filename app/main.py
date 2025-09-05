import logging
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import create_tables, get_db
from app.models import Article
from app.schemas import ArticleResponse
from app.services.news_services import NewsService
from apscheduler.triggers.cron import CronTrigger
from app.scheduler import NewsScheduler
from app.config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Global scheduler instance
scheduler = NewsScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    create_tables()
    scheduler.start()
    yield
    # Shutdown
    scheduler.stop()

app = FastAPI(
    title="News Scraping API",
    description="Automated news scraping and processing service",
    version="1.0.0",
    lifespan=lifespan
)

# =============================================================================
# ARTICLE ENDPOINTS
# =============================================================================

@app.get("/articles", response_model=List[ArticleResponse])
async def get_processed_articles(
    limit: int = 50, 
    brand: Optional[str] = None, 
    model: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get processed articles with optional brand and model filtering"""
    query = db.query(Article).filter(Article.processed == True)
    
    if brand:
        query = query.filter(Article.brand_name.ilike(f"%{brand}%"))
    
    if model:
        query = query.filter(Article.model_name.ilike(f"%{model}%"))
    
    return query.order_by(Article.processed_at.desc()).limit(limit).all()

@app.get("/articles/brands", response_model=List[str])
async def get_available_brands(db: Session = Depends(get_db)):
    """Get list of all available car brands"""
    brands = db.query(Article.brand_name).filter(
        Article.brand_name.isnot(None),
        Article.processed == True
    ).distinct().all()
    
    return [brand[0] for brand in brands if brand[0]]

@app.get("/articles/models", response_model=List[str])
async def get_available_models(brand: Optional[str] = None, db: Session = Depends(get_db)):
    """Get list of all available car models, optionally filtered by brand"""
    query = db.query(Article.model_name).filter(
        Article.model_name.isnot(None),
        Article.processed == True
    )
    
    if brand:
        query = query.filter(Article.brand_name.ilike(f"%{brand}%"))
    
    models = query.distinct().all()
    return [model[0] for model in models if model[0]]

# =============================================================================
# WORKFLOW ENDPOINTS
# =============================================================================

@app.post("/workflow/run", response_model=str)
async def run_workflow_manually(db: Session = Depends(get_db)):
    """Manually trigger the complete news workflow"""
    try:
        async with NewsService() as news_service:
            await news_service.execute_news_workflow(db)
        return "Workflow executed successfully"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow execution failed: {str(e)}")

@app.post("/workflow/scrape", response_model=str)
async def run_scraping_only(db: Session = Depends(get_db)):
    """Manually trigger scraping only"""
    try:
        async with NewsService() as news_service:
            await news_service.scrape_all_sources(db)
        return "Scraping executed successfully"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraping execution failed: {str(e)}")

@app.post("/workflow/process", response_model=str)
async def run_processing_only(db: Session = Depends(get_db)):
    """Manually trigger processing only"""
    try:
        async with NewsService() as news_service:
            await news_service.process_articles(db)
        return "Processing executed successfully"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing execution failed: {str(e)}")

# =============================================================================
# CONFIG ENDPOINTS (Read-only)
# =============================================================================

@app.get("/config/sources", response_model=List[str])
async def get_configured_sources():
    """Get list of configured news sources"""
    return config.NEWS_SOURCES

@app.get("/config/topic", response_model=str)
async def get_configured_topic():
    """Get the configured topic"""
    return config.NEWS_TOPIC

# =============================================================================
# HEALTH CHECK
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "service": "news-scraping-api",
        "sources_count": len(config.NEWS_SOURCES),
        "topic": config.NEWS_TOPIC
    }

if __name__ == "__main__":

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)