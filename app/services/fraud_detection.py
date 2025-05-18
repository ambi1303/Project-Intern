from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.models import Transaction, TransactionStatus, TransactionType, CurrencyType
from app.core.config import settings

class FraudDetectionService:
    def __init__(self, db: Session):
        self.db = db

    def check_transaction(self, transaction: Transaction) -> bool:
        """
        Check if a transaction is suspicious based on various rules
        """
        # Get user's recent transactions
        recent_transactions = self.db.query(Transaction).filter(
            (Transaction.sender_id == transaction.sender_id) |
            (Transaction.receiver_id == transaction.sender_id),
            Transaction.created_at >= datetime.utcnow() - timedelta(hours=24)
        ).all()

        # Check for high frequency of transactions
        if len(recent_transactions) > 10:
            return True

        # Check for large transaction amount
        currency = transaction.currency.value
        if currency == CurrencyType.USD.value:
            if transaction.amount > 10000:  # $10,000 threshold for USD
                return True
        elif currency == CurrencyType.EUR.value:
            if transaction.amount > 8500:  # €8,500 threshold for EUR
                return True
        elif currency == CurrencyType.GBP.value:
            if transaction.amount > 7500:  # £7,500 threshold for GBP
                return True
        elif currency == CurrencyType.BONUS.value:
            if transaction.amount > 1000:  # 1,000 bonus points threshold
                return True

        # Check for multiple transfers to the same recipient
        if transaction.transaction_type == TransactionType.TRANSFER:
            transfers_to_recipient = sum(
                1 for t in recent_transactions
                if t.transaction_type == TransactionType.TRANSFER
                and t.receiver_id == transaction.receiver_id
            )
            if transfers_to_recipient > 3:
                return True

        return False

    def scan_recent_transactions(self):
        """
        Scan recent transactions for suspicious activity
        """
        # Get transactions from the last 24 hours
        recent_transactions = self.db.query(Transaction).filter(
            Transaction.created_at >= datetime.utcnow() - timedelta(hours=24),
            Transaction.is_flagged == False
        ).all()

        for transaction in recent_transactions:
            if self.check_transaction(transaction):
                transaction.is_flagged = True
                transaction.flag_reason = "Suspicious transaction pattern detected"
                transaction.status = TransactionStatus.FLAGGED
                self.db.add(transaction)

        self.db.commit()

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