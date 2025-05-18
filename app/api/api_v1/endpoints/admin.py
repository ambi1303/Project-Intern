from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from app.db.session import get_db
from app.models.models import User, Wallet, Transaction, TransactionStatus, TransactionType, CurrencyType
from app.schemas.schemas import AdminStats, TopUser, TransactionInDB
from app.api.deps import get_current_admin_user

router = APIRouter()

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

@router.get("/top-users", response_model=List[TopUser])
def get_top_users(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get top users by balance and transaction count"""
    try:
        # Get all active users with their wallets
        users = db.query(User).filter(User.is_deleted == False).all()
        
        top_users = []
        for user in users:
            wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()
            if wallet:
                transaction_count = db.query(func.count(Transaction.id)).filter(
                    (Transaction.sender_id == user.id) | (Transaction.receiver_id == user.id)
                ).scalar() or 0
                
                # Ensure all balances are float values
                balances = {k: float(v) for k, v in wallet.balances.items()}
                
                top_users.append(TopUser(
                    id=user.id,
                    email=user.email,
                    balances=balances,
                    transaction_count=transaction_count
                ))
        
        # Sort by total balance (sum of all currencies)
        top_users.sort(key=lambda x: sum(x.balances.values()), reverse=True)
        return top_users[:10]  # Return top 10 users
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching top users: {str(e)}")

@router.get("/flagged-transactions", response_model=List[TransactionInDB])
def get_flagged_transactions(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get all flagged transactions"""
    try:
        return db.query(Transaction).filter(Transaction.is_flagged == True).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching flagged transactions: {str(e)}")

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