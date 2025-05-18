from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any
from app.db.session import get_db
from app.models.models import User, Wallet, Transaction, TransactionStatus, TransactionType, CurrencyType
from app.schemas.schemas import AdminStats, TopUser, TransactionInDB
from app.api.deps import get_current_admin_user
from app.services.fraud_detection import FraudDetectionService
from datetime import datetime, timedelta
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/stats", response_model=AdminStats)
def get_admin_stats(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get system-wide statistics"""
    try:
        total_users = db.query(func.count(User.id)).filter(User.is_deleted == False).scalar() or 0
        total_transactions = db.query(func.count(Transaction.id)).scalar() or 0
        
        # Calculate total volume per currency
        total_volume = {}
        for currency in CurrencyType:
            volume = db.query(func.sum(Transaction.amount)).filter(
                Transaction.currency == currency,
                Transaction.status == TransactionStatus.COMPLETED
            ).scalar() or 0
            total_volume[currency.value] = float(volume)  # Ensure float value
        
        flagged_transactions = db.query(func.count(Transaction.id)).filter(
            Transaction.is_flagged == True
        ).scalar() or 0
        
        return AdminStats(
            total_users=total_users,
            total_transactions=total_transactions,
            total_volume=total_volume,
            flagged_transactions=flagged_transactions
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching admin stats: {str(e)}")

@router.get("/flagged-transactions", response_model=List[Dict[str, Any]])
def get_flagged_transactions(
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get all flagged transactions"""
    try:
        transactions = db.query(Transaction).filter(
            Transaction.is_flagged == True
        ).order_by(Transaction.created_at.desc()).all()
        
        return [
            {
                "id": t.id,
                "sender_id": t.sender_id,
                "receiver_id": t.receiver_id,
                "amount": t.amount,
                "currency": t.currency.value,
                "type": t.type.value,
                "status": t.status.value,
                "flag_reason": t.flag_reason,
                "created_at": t.created_at
            }
            for t in transactions
        ]
    except Exception as e:
        logger.error(f"Error retrieving flagged transactions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving flagged transactions: {str(e)}"
        )

@router.get("/user-balances", response_model=List[Dict[str, Any]])
def get_user_balances(
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get total balances for all users"""
    try:
        users = db.query(User).filter(User.is_deleted == False).all()
        balances = []
        
        for user in users:
            wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()
            if wallet:
                balances.append({
                    "user_id": user.id,
                    "email": user.email,
                    "balances": wallet.balances
                })
        
        return balances
    except Exception as e:
        logger.error(f"Error retrieving user balances: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving user balances: {str(e)}"
        )

@router.get("/top-users", response_model=List[Dict[str, Any]])
def get_top_users(
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    by: str = "balance",  # or "volume"
    limit: int = 10
):
    """Get top users by balance or transaction volume"""
    try:
        if by == "balance":
            # Get users with highest total balance across all currencies
            users = db.query(User).join(Wallet).order_by(
                func.jsonb_array_length(Wallet.balances).desc()
            ).limit(limit).all()
            
            return [
                {
                    "user_id": user.id,
                    "email": user.email,
                    "total_balance": sum(
                        float(amount) for amount in user.wallet.balances.values()
                    )
                }
                for user in users
            ]
        else:  # by volume
            # Get users with highest transaction volume
            users = db.query(
                User,
                func.count(Transaction.id).label('transaction_count')
            ).join(
                Transaction,
                (User.id == Transaction.sender_id) | (User.id == Transaction.receiver_id)
            ).group_by(User.id).order_by(
                func.count(Transaction.id).desc()
            ).limit(limit).all()
            
            return [
                {
                    "user_id": user.id,
                    "email": user.email,
                    "transaction_count": count
                }
                for user, count in users
            ]
    except Exception as e:
        logger.error(f"Error retrieving top users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving top users: {str(e)}"
        )

@router.get("/fraud-scan", response_model=List[Dict[str, Any]])
def run_fraud_scan(
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Run fraud detection scan on recent transactions"""
    try:
        fraud_service = FraudDetectionService(db)
        suspicious_transactions = fraud_service.scan_recent_transactions()
        return suspicious_transactions
    except Exception as e:
        logger.error(f"Error running fraud scan: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error running fraud scan: {str(e)}"
        )

@router.post("/transactions/{transaction_id}/review")
def review_transaction(
    transaction_id: int,
    action: str,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Review a flagged transaction"""
    try:
        transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        if not transaction.is_flagged:
            raise HTTPException(status_code=400, detail="Transaction is not flagged")
        
        if action not in ["approve", "reject"]:
            raise HTTPException(status_code=400, detail="Invalid action. Must be 'approve' or 'reject'")
        
        if action == "approve":
            transaction.status = TransactionStatus.COMPLETED
            transaction.is_flagged = False
            transaction.flag_reason = None
            
            # Process the transaction
            currency = transaction.currency.value
            if transaction.transaction_type == TransactionType.TRANSFER:
                sender_wallet = db.query(Wallet).filter(Wallet.user_id == transaction.sender_id).first()
                receiver_wallet = db.query(Wallet).filter(Wallet.user_id == transaction.receiver_id).first()
                
                if sender_wallet and receiver_wallet:
                    sender_wallet.balances[currency] = sender_wallet.balances.get(currency, 0) - transaction.amount
                    receiver_wallet.balances[currency] = receiver_wallet.balances.get(currency, 0) + transaction.amount
        else:  # reject
            transaction.status = TransactionStatus.REJECTED
            transaction.is_flagged = False
        
        db.commit()
        return {"message": f"Transaction {action}d successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error reviewing transaction: {str(e)}") 