from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.jobs.fraud_scanner import scan_for_fraud
from app.core.logger import logger

def start_scheduler():
    """Start the background scheduler"""
    scheduler = BackgroundScheduler()
    
    # Schedule fraud scanner to run daily at midnight
    scheduler.add_job(
        scan_for_fraud,
        trigger=CronTrigger(hour=0, minute=0),
        id='fraud_scanner',
        name='Daily fraud scan',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("Scheduler started successfully") 