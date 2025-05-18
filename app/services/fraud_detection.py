from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.models import Transaction, TransactionStatus, TransactionType, CurrencyType
from app.core.config import settings
from app.db.session import SessionLocal
import logging

logger = logging.getLogger(__name__)

class FraudDetectionService:
    def __init__(self, db: Session):
        self.db = db

    def check_transaction(self, transaction: Transaction) -> tuple[bool, str]:
        """Check if a transaction is suspicious"""
        try:
            # Check for multiple transfers in short period
            if transaction.type == TransactionType.TRANSFER:
                recent_transfers = self.db.query(Transaction).filter(
                    Transaction.sender_id == transaction.sender_id,
                    Transaction.type == TransactionType.TRANSFER,
                    Transaction.created_at >= datetime.utcnow() - timedelta(minutes=5)
                ).count()
                
                if recent_transfers >= 3:
                    return True, "Multiple transfers in short period"

            # Check for large withdrawal
            if transaction.type == TransactionType.WITHDRAWAL:
                if transaction.amount > 1000:  # Threshold for large withdrawal
                    return True, "Large withdrawal amount"

            # Check for sudden large transfer
            if transaction.type == TransactionType.TRANSFER:
                if transaction.amount > 500:  # Threshold for large transfer
                    return True, "Large transfer amount"

            # Check for rapid balance changes
            recent_transactions = self.db.query(Transaction).filter(
                (Transaction.sender_id == transaction.sender_id) |
                (Transaction.receiver_id == transaction.sender_id),
                Transaction.created_at >= datetime.utcnow() - timedelta(hours=1)
            ).all()

            total_volume = sum(t.amount for t in recent_transactions)
            if total_volume > 2000:  # Threshold for rapid balance changes
                return True, "Rapid balance changes detected"

            return False, ""

        except Exception as e:
            logger.error(f"Error in fraud detection: {str(e)}")
            return False, ""

    def scan_recent_transactions(self) -> list[dict]:
        """Scan recent transactions for fraud patterns"""
        try:
            suspicious_transactions = []
            recent_transactions = self.db.query(Transaction).filter(
                Transaction.created_at >= datetime.utcnow() - timedelta(hours=24)
            ).all()

            for transaction in recent_transactions:
                is_suspicious, reason = self.check_transaction(transaction)
                if is_suspicious:
                    suspicious_transactions.append({
                        "transaction_id": transaction.id,
                        "user_id": transaction.sender_id,
                        "amount": transaction.amount,
                        "type": transaction.type,
                        "reason": reason,
                        "created_at": transaction.created_at
                    })
                    # Update transaction status
                    transaction.is_flagged = True
                    transaction.flag_reason = reason
                    self.db.commit()

            return suspicious_transactions

        except Exception as e:
            logger.error(f"Error scanning transactions: {str(e)}")
            return []

    def get_fraud_stats(self) -> dict:
        """
        Get statistics about fraudulent transactions.
        """
        total_flagged = self.db.query(func.count(Transaction.id)).filter(
            Transaction.is_flagged == True
        ).scalar()

        total_amount_flagged = self.db.query(func.sum(Transaction.amount)).filter(
            Transaction.is_flagged == True
        ).scalar() or 0

        return {
            "total_flagged_transactions": total_flagged,
            "total_flagged_amount": total_amount_flagged,
            "last_scan": datetime.utcnow()
        }

def scan_for_fraud():
    """Scan for potentially fraudulent transactions"""
    db = SessionLocal()
    try:
        # Get transactions from the last 24 hours
        yesterday = datetime.utcnow() - timedelta(days=1)
        
        # Check for large transactions
        large_transactions = db.query(Transaction).filter(
            Transaction.created_at >= yesterday,
            Transaction.amount > 10000,  # Threshold for large transactions
            Transaction.is_flagged == False
        ).all()
        
        # Check for rapid transactions
        rapid_transactions = db.query(Transaction).filter(
            Transaction.created_at >= yesterday,
            Transaction.is_flagged == False
        ).group_by(Transaction.user_id).having(
            func.count(Transaction.id) > 10  # More than 10 transactions in 24 hours
        ).all()
        
        # Flag suspicious transactions
        for transaction in large_transactions + rapid_transactions:
            transaction.is_flagged = True
            transaction.flag_reason = "Automated fraud detection"
            logger.info(f"Flagged transaction {transaction.id} for fraud detection")
        
        db.commit()
        logger.info("Fraud detection scan completed successfully")
        
    except Exception as e:
        logger.error(f"Error in fraud detection scan: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def check_transaction_fraud(transaction: Transaction, db: SessionLocal) -> bool:
    """Check if a single transaction is potentially fraudulent"""
    try:
        # Check for large amount
        if transaction.amount > 10000:
            return True
            
        # Check for rapid transactions
        recent_transactions = db.query(Transaction).filter(
            Transaction.user_id == transaction.user_id,
            Transaction.created_at >= datetime.utcnow() - timedelta(hours=1)
        ).count()
        
        if recent_transactions > 5:  # More than 5 transactions in an hour
            return True
            
        return False
        
    except Exception as e:
        logger.error(f"Error checking transaction fraud: {e}")
        return False 