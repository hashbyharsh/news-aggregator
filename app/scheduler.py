from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.services.news_services import NewsService

logger = logging.getLogger(__name__)

class NewsScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        
    def start(self):
        """Start the scheduler and add the news workflow job"""
        self.scheduler.add_job(
            self.run_workflow,
            CronTrigger(minute="*/30"),
            id="news_workflow",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300
        )
        self.scheduler.start()
        logger.info("News scheduler started with workflow scheduled every 30 minutes")
    
    def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()
        logger.info("News scheduler stopped")

    async def run_workflow(self):
        """Run the news workflow"""
        logger.info("Starting scheduled news workflow execution")
        db: Session = SessionLocal()
        try:
            async with NewsService() as news_service:
                await news_service.execute_news_workflow(db)
                logger.info("Scheduled news workflow completed successfully")
        except Exception as e:
                logger.error(f"Scheduled news workflow failed: {str(e)}")
        finally:
            db.close()