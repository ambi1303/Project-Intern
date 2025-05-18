from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.session import get_db
from app.models.models import User, Wallet, Transaction, TransactionType, TransactionStatus, CurrencyType
from app.schemas.schemas import TransactionCreate, TransactionInDB
from app.api.deps import get_current_active_user
from app.services.fraud_detection import FraudDetectionService

router = APIRouter()

@router.post("", response_model=TransactionInDB)
def create_transaction(
    transaction: TransactionCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new transaction"""
    # Get sender's wallet
    sender_wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
    if not sender_wallet:
        raise HTTPException(status_code=404, detail="Sender wallet not found")

    # Initialize receiver variables
    receiver = None
    receiver_wallet = None
    receiver_id = None

    # Handle transfer-specific logic
    if transaction.transaction_type == TransactionType.TRANSFER:
        if not transaction.receiver_email:
            raise HTTPException(status_code=400, detail="Receiver email required for transfers")
        
        # Find receiver by email
        receiver = db.query(User).filter(User.email == transaction.receiver_email).first()
        if not receiver:
            raise HTTPException(status_code=404, detail="Receiver not found")
        
        if receiver.id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot transfer to yourself")
        
        # Get receiver's wallet
        receiver_wallet = db.query(Wallet).filter(Wallet.user_id == receiver.id).first()
        if not receiver_wallet:
            raise HTTPException(status_code=404, detail="Receiver wallet not found")
        
        receiver_id = receiver.id

    # Check sufficient balance for withdrawals and transfers
    if transaction.transaction_type in [TransactionType.WITHDRAWAL, TransactionType.TRANSFER]:
        currency = transaction.currency.value
        if sender_wallet.balances.get(currency, 0) < transaction.amount:
            raise HTTPException(status_code=400, detail=f"Insufficient {currency} balance")

    # Create transaction record
    db_transaction = Transaction(
        wallet_id=sender_wallet.id,
        sender_id=current_user.id,
        receiver_id=receiver_id,
        amount=transaction.amount,
        currency=transaction.currency,
        transaction_type=transaction.transaction_type,
        description=transaction.description,
        status=TransactionStatus.PENDING
    )

    # Check for fraud
    fraud_service = FraudDetectionService(db)
    if fraud_service.check_transaction(db_transaction):
        db_transaction.is_flagged = True
        db_transaction.flag_reason = "Suspicious transaction pattern detected"
        db_transaction.status = TransactionStatus.FLAGGED
    else:
        # Process transaction
        try:
            currency = transaction.currency.value
            if transaction.transaction_type == TransactionType.DEPOSIT:
                sender_wallet.balances[currency] = sender_wallet.balances.get(currency, 0) + transaction.amount
                db_transaction.status = TransactionStatus.COMPLETED
            elif transaction.transaction_type == TransactionType.WITHDRAWAL:
                sender_wallet.balances[currency] = sender_wallet.balances.get(currency, 0) - transaction.amount
                db_transaction.status = TransactionStatus.COMPLETED
            elif transaction.transaction_type == TransactionType.TRANSFER:
                # Create a separate transaction record for the receiver
                receiver_transaction = Transaction(
                    wallet_id=receiver_wallet.id,
                    sender_id=current_user.id,
                    receiver_id=receiver_id,
                    amount=transaction.amount,
                    currency=transaction.currency,
                    transaction_type=TransactionType.TRANSFER,
                    description=f"Received from {current_user.email}: {transaction.description}",
                    status=TransactionStatus.COMPLETED
                )
                db.add(receiver_transaction)
                
                # Update balances
                sender_wallet.balances[currency] = sender_wallet.balances.get(currency, 0) - transaction.amount
                receiver_wallet.balances[currency] = receiver_wallet.balances.get(currency, 0) + transaction.amount
                db_transaction.status = TransactionStatus.COMPLETED

            db.add(db_transaction)
            db.commit()
            db.refresh(db_transaction)
            return db_transaction

        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")

@router.get("", response_model=List[TransactionInDB])
def get_transactions(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user's transactions"""
    transactions = db.query(Transaction).filter(
        (Transaction.sender_id == current_user.id) |
        (Transaction.receiver_id == current_user.id)
    ).order_by(Transaction.created_at.desc()).all()
    
    return transactions 