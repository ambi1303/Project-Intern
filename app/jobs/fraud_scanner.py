from app.db.session import SessionLocal
from app.services.fraud_detection import FraudDetectionService
from app.core.logger import logger

def scan_for_fraud():
    """Scan for fraudulent transactions"""
    try:
        db = SessionLocal()
        fraud_service = FraudDetectionService(db)
        fraud_service.scan_recent_transactions()
        stats = fraud_service.get_fraud_stats()
        logger.info(f"Fraud scan completed. Stats: {stats}")
    except Exception as e:
        logger.error(f"Error during fraud scan: {str(e)}")
    finally:
        db.close() 