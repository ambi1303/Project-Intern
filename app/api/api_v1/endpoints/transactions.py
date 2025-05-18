from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from app.db.session import get_db
from app.models.models import User, Wallet, Transaction, TransactionType, TransactionStatus, CurrencyType
from app.schemas.schemas import TransactionCreate, TransactionInDB, TransactionUpdate
from app.api.deps import get_current_user, get_current_admin_user
from app.services.fraud_detection import FraudDetectionService
from datetime import datetime
import logging
import traceback

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/debug/user/{user_id}", response_model=Dict[str, Any])
def debug_user(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Debug endpoint to check user and wallet existence"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {
                "exists": False,
                "message": f"User {user_id} not found"
            }
        
        wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
        return {
            "exists": True,
            "user": {
                "id": user.id,
                "email": user.email,
                "is_active": user.is_active
            },
            "wallet": {
                "exists": wallet is not None,
                "id": wallet.id if wallet else None,
                "balances": wallet.balances if wallet else None
            }
        }
    except Exception as e:
        logger.error(f"Error in debug endpoint: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking user: {str(e)}"
        )

@router.get("/admin/all", response_model=List[TransactionInDB])
def get_all_transactions(
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
):
    """Get all transactions (admin only)"""
    try:
        transactions = db.query(Transaction).order_by(Transaction.created_at.desc()).offset(skip).limit(limit).all()
        return transactions
    except Exception as e:
        logger.error(f"Error retrieving all transactions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving transactions: {str(e)}"
        )

@router.get("/admin/user/{user_id}", response_model=List[TransactionInDB])
def get_user_transactions(
    user_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get all transactions for a specific user (admin only)"""
    try:
        transactions = db.query(Transaction).filter(
            (Transaction.sender_id == user_id) |
            (Transaction.receiver_id == user_id)
        ).order_by(Transaction.created_at.desc()).all()
        return transactions
    except Exception as e:
        logger.error(f"Error retrieving user transactions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving transactions: {str(e)}"
        )

@router.put("/admin/{transaction_id}", response_model=TransactionInDB)
def update_transaction(
    transaction_id: int,
    transaction_update: TransactionUpdate,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Update a transaction (admin only)"""
    try:
        transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found"
            )

        # Update transaction fields
        for field, value in transaction_update.dict(exclude_unset=True).items():
            setattr(transaction, field, value)

        db.commit()
        db.refresh(transaction)
        return transaction
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error updating transaction: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating transaction: {str(e)}"
        )

@router.post("/admin/create", response_model=TransactionInDB)
def admin_create_transaction(
    transaction: TransactionCreate,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Create a transaction as admin (admin only)"""
    try:
        logger.info(f"Admin {current_admin.id} creating transaction: {transaction.dict()}")
        
        # Validate amount
        if transaction.amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transaction amount must be greater than 0"
            )

        # Get user by email for deposit/withdrawal
        user_email = transaction.receiver_email or current_admin.email
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with email {user_email} not found"
            )

        # Get user's wallet
        user_wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()
        if not user_wallet:
            # Create wallet if it doesn't exist
            user_wallet = Wallet(
                user_id=user.id,
                created_at=datetime.utcnow()
            )
            db.add(user_wallet)
            db.commit()
            db.refresh(user_wallet)
            logger.info(f"Created new wallet for user {user.id}")

        # Create transaction
        new_transaction = Transaction(
            sender_id=user.id,
            receiver_id=user.id,
            sender_wallet_id=user_wallet.id,
            receiver_wallet_id=user_wallet.id,
            amount=transaction.amount,
            currency=transaction.currency,
            type=transaction.type,
            description=transaction.description,
            created_at=datetime.utcnow(),
            status=TransactionStatus.COMPLETED  # Admin transactions are automatically completed
        )

        # Process transaction
        currency = transaction.currency.value
        if transaction.type == TransactionType.DEPOSIT:
            user_wallet.balances[currency] = user_wallet.balances.get(currency, 0) + transaction.amount
        elif transaction.type == TransactionType.WITHDRAWAL:
            if user_wallet.balances.get(currency, 0) < transaction.amount:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient {currency} balance. Current balance: {user_wallet.balances.get(currency, 0)}"
                )
            user_wallet.balances[currency] = user_wallet.balances.get(currency, 0) - transaction.amount

        db.add(new_transaction)
        db.commit()
        db.refresh(new_transaction)
        
        logger.info(f"Admin created transaction {new_transaction.id} for user {user.id}")
        return new_transaction

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error creating transaction: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating transaction: {str(e)}"
        )

@router.get("/", response_model=List[TransactionInDB])
def get_transactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's transactions"""
    try:
        transactions = db.query(Transaction).filter(
            (Transaction.sender_id == current_user.id) |
            (Transaction.receiver_id == current_user.id)
        ).order_by(Transaction.created_at.desc()).all()
        
        logger.info(f"Retrieved {len(transactions)} transactions for user {current_user.id}")
        return transactions
        
    except Exception as e:
        logger.error(f"Error retrieving transactions: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving transactions: {str(e)}"
        )

@router.post("/", response_model=TransactionInDB)
def create_transaction(
    transaction: TransactionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new transaction"""
    try:
        logger.info(f"Creating transaction: {transaction.dict()}")
        logger.info(f"Current user ID: {current_user.id}")
        
        # Validate amount
        if transaction.amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transaction amount must be greater than 0"
            )

        # Get sender's wallet
        sender_wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
        if not sender_wallet:
            logger.error(f"Sender wallet not found for user {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sender wallet not found"
            )
        logger.info(f"Found sender wallet: {sender_wallet.id}")

        # Handle different transaction types
        if transaction.type == TransactionType.TRANSFER:
            if not transaction.receiver_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Receiver email is required for transfer transactions"
                )
            
            # Get receiver by email
            receiver = db.query(User).filter(User.email == transaction.receiver_email).first()
            if not receiver:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Receiver with email {transaction.receiver_email} not found"
                )
            
            # Get receiver's wallet
            receiver_wallet = db.query(Wallet).filter(Wallet.user_id == receiver.id).first()
            if not receiver_wallet:
                # Create wallet for receiver if it doesn't exist
                receiver_wallet = Wallet(
                    user_id=receiver.id,
                    created_at=datetime.utcnow()
                )
                db.add(receiver_wallet)
                db.commit()
                db.refresh(receiver_wallet)
                logger.info(f"Created new wallet for receiver {receiver.id}")

            # Check if sender has sufficient balance
            currency = transaction.currency.value
            if sender_wallet.balances.get(currency, 0) < transaction.amount:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient {currency} balance. Current balance: {sender_wallet.balances.get(currency, 0)}"
                )

            # Create transfer transaction
            new_transaction = Transaction(
                sender_id=current_user.id,
                receiver_id=receiver.id,
                sender_wallet_id=sender_wallet.id,
                receiver_wallet_id=receiver_wallet.id,
                amount=transaction.amount,
                currency=transaction.currency,
                type=transaction.type,
                description=transaction.description,
                created_at=datetime.utcnow(),
                status=TransactionStatus.COMPLETED
            )

            # Update balances
            sender_wallet.balances[currency] = sender_wallet.balances.get(currency, 0) - transaction.amount
            receiver_wallet.balances[currency] = receiver_wallet.balances.get(currency, 0) + transaction.amount

        else:  # DEPOSIT or WITHDRAWAL
            # For deposit/withdrawal, use the same wallet for sender and receiver
            if transaction.type == TransactionType.WITHDRAWAL:
                currency = transaction.currency.value
                if sender_wallet.balances.get(currency, 0) < transaction.amount:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Insufficient {currency} balance. Current balance: {sender_wallet.balances.get(currency, 0)}"
                    )
                sender_wallet.balances[currency] = sender_wallet.balances.get(currency, 0) - transaction.amount
            else:  # DEPOSIT
                currency = transaction.currency.value
                sender_wallet.balances[currency] = sender_wallet.balances.get(currency, 0) + transaction.amount

            # Create self-transaction
            new_transaction = Transaction(
                sender_id=current_user.id,
                receiver_id=current_user.id,
                sender_wallet_id=sender_wallet.id,
                receiver_wallet_id=sender_wallet.id,
                amount=transaction.amount,
                currency=transaction.currency,
                type=transaction.type,
                description=transaction.description,
                created_at=datetime.utcnow(),
                status=TransactionStatus.COMPLETED
            )

        db.add(new_transaction)
        db.commit()
        db.refresh(new_transaction)
        
        logger.info(f"Created transaction {new_transaction.id} from user {current_user.id}")
        return new_transaction

    except HTTPException as he:
        logger.error(f"HTTP error in transaction creation: {he.detail}")
        raise he
    except Exception as e:
        logger.error(f"Error creating transaction: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating transaction: {str(e)}"
        ) 