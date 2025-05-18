from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.services.fraud_detection import scan_for_fraud
from app.core.config import settings
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create scheduler instance
scheduler = BackgroundScheduler()

def setup_scheduler():
    """Setup and configure the scheduler with jobs"""
    try:
        # Add daily fraud detection job
        scheduler.add_job(
            scan_for_fraud,
            trigger=CronTrigger(hour=0, minute=0),  # Run at midnight
            id='fraud_detection',
            name='Daily fraud detection scan',
            replace_existing=True
        )
        
        logger.info("Scheduler jobs configured successfully")
    except Exception as e:
        logger.error(f"Error setting up scheduler: {e}")
        raise

# Initialize scheduler when module is imported
setup_scheduler() 