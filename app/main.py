from fastapi import FastAPI, Depends, HTTPException, status, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from typing import List
from apscheduler.schedulers.background import BackgroundScheduler
from jose import JWTError, jwt

from app.core.config import settings
from app.core.security import create_access_token, verify_password, get_password_hash
from app.db.session import get_db, SessionLocal
from app.db.init_db import init_db
from app.models.models import User, Wallet, Transaction, TransactionStatus, TransactionType
from app.schemas.schemas import (
    UserCreate, UserInDB, Token, TransactionCreate, TransactionInDB,
    WalletInDB, AdminStats, TopUser
)
from app.services.fraud_detection import FraudDetectionService
from app.api.api_v1.api import api_router
from app.jobs.scheduler import start_scheduler
from app.core.logger import logger

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="""
    A secure digital wallet system with features including:
    - User authentication and authorization
    - Wallet management
    - Transaction processing
    - Fraud detection
    - Admin reporting
    """,
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create routers
auth_router = APIRouter(prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication"])
wallet_router = APIRouter(prefix=f"{settings.API_V1_STR}/wallet", tags=["Wallet"])
transaction_router = APIRouter(prefix=f"{settings.API_V1_STR}/transactions", tags=["Transactions"])
admin_router = APIRouter(prefix=f"{settings.API_V1_STR}/admin", tags=["Admin"])

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

# Dependencies
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

async def get_current_admin_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges"
        )
    return current_user

# Auth routes
@auth_router.post("/register", response_model=UserInDB, summary="Register a new user")
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user with the following information:
    - **email**: User's email address
    - **password**: User's password
    - **full_name**: User's full name
    """
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    
    hashed_password = get_password_hash(user.password)
    db_user = User(
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Create wallet for new user
    wallet = Wallet(user_id=db_user.id)
    db.add(wallet)
    db.commit()
    
    return db_user

@auth_router.post("/login", response_model=Token, summary="Login to get access token")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Login with email and password to get an access token.
    - **username**: Your email address
    - **password**: Your password
    """
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

# Wallet routes
@wallet_router.get("", response_model=WalletInDB, summary="Get user's wallet")
def get_wallet(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get the current user's wallet information including:
    - Balance
    - Currency
    - Transaction history
    """
    wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return wallet

# Transaction routes
@transaction_router.post("", response_model=TransactionInDB, summary="Create a new transaction")
def create_transaction(
    transaction: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new transaction with the following types:
    - **deposit**: Add money to your wallet
    - **withdrawal**: Remove money from your wallet
    - **transfer**: Send money to another user
    
    Required fields:
    - **amount**: Transaction amount
    - **transaction_type**: Type of transaction
    - **description**: Transaction description
    - **receiver_email**: Required only for transfers
    """
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
        if sender_wallet.balance < transaction.amount:
            raise HTTPException(status_code=400, detail="Insufficient funds")

    # Create transaction record
    db_transaction = Transaction(
        wallet_id=sender_wallet.id,
        sender_id=current_user.id,
        receiver_id=receiver_id,
        amount=transaction.amount,
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
            if transaction.transaction_type == TransactionType.DEPOSIT:
                sender_wallet.balance += transaction.amount
                db_transaction.status = TransactionStatus.COMPLETED
            elif transaction.transaction_type == TransactionType.WITHDRAWAL:
                sender_wallet.balance -= transaction.amount
                db_transaction.status = TransactionStatus.COMPLETED
            elif transaction.transaction_type == TransactionType.TRANSFER:
                # Create a separate transaction record for the receiver
                receiver_transaction = Transaction(
                    wallet_id=receiver_wallet.id,
                    sender_id=current_user.id,
                    receiver_id=receiver_id,
                    amount=transaction.amount,
                    transaction_type=TransactionType.TRANSFER,
                    description=f"Received from {current_user.email}: {transaction.description}",
                    status=TransactionStatus.COMPLETED
                )
                db.add(receiver_transaction)
                
                # Update balances
                sender_wallet.balance -= transaction.amount
                receiver_wallet.balance += transaction.amount
                db_transaction.status = TransactionStatus.COMPLETED

            db.add(db_transaction)
            db.commit()
            db.refresh(db_transaction)
            return db_transaction

        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")

@transaction_router.get("", response_model=List[TransactionInDB], summary="Get user's transactions")
def get_transactions(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all transactions for the current user, including:
    - Sent transactions
    - Received transactions
    - Transaction status
    - Transaction type
    """
    # Get both sent and received transactions
    transactions = db.query(Transaction).filter(
        (Transaction.sender_id == current_user.id) |
        (Transaction.receiver_id == current_user.id)
    ).order_by(Transaction.created_at.desc()).all()
    
    return transactions

# Admin routes
@admin_router.get("/stats", response_model=AdminStats, summary="Get system statistics")
def get_admin_stats(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get system-wide statistics including:
    - Total number of users
    - Total number of transactions
    - Total transaction volume
    - Number of flagged transactions
    """
    try:
        # Get total users (excluding deleted)
        total_users = db.query(func.count(User.id)).filter(
            User.deleted_at.is_(None)
        ).scalar() or 0

        # Get total transactions (excluding deleted)
        total_transactions = db.query(func.count(Transaction.id)).filter(
            Transaction.deleted_at.is_(None)
        ).scalar() or 0

        # Get total transaction volume
        total_volume = db.query(func.sum(Transaction.amount)).filter(
            Transaction.status == TransactionStatus.COMPLETED,
            Transaction.deleted_at.is_(None)
        ).scalar() or 0

        # Get flagged transactions
        flagged_transactions = db.query(func.count(Transaction.id)).filter(
            Transaction.is_flagged == True,
            Transaction.deleted_at.is_(None)
        ).scalar() or 0

        return AdminStats(
            total_users=total_users,
            total_transactions=total_transactions,
            total_volume=total_volume,
            flagged_transactions=flagged_transactions
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching admin stats: {str(e)}")

@admin_router.get("/top-users", response_model=List[TopUser], summary="Get top users by balance")
def get_top_users(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get top 10 users by wallet balance, including:
    - User details
    - Total balance
    - Number of transactions
    """
    try:
        # First, get users with their wallet balances
        user_balances = db.query(
            User.id,
            User.email,
            func.coalesce(Wallet.balance, 0).label("total_balance")
        ).outerjoin(
            Wallet,
            User.id == Wallet.user_id
        ).filter(
            User.deleted_at.is_(None)
        ).subquery()

        # Then, get transaction counts for each user
        user_transactions = db.query(
            User.id,
            func.count(Transaction.id).label("transaction_count")
        ).outerjoin(
            Transaction,
            (User.id == Transaction.sender_id) | (User.id == Transaction.receiver_id)
        ).filter(
            User.deleted_at.is_(None)
        ).group_by(User.id).subquery()

        # Finally, combine the results
        top_users = db.query(
            user_balances.c.id,
            user_balances.c.email,
            user_balances.c.total_balance,
            func.coalesce(user_transactions.c.transaction_count, 0).label("transaction_count")
        ).outerjoin(
            user_transactions,
            user_balances.c.id == user_transactions.c.id
        ).order_by(
            desc(user_balances.c.total_balance)
        ).limit(10).all()

        return [
            TopUser(
                id=user.id,
                email=user.email,
                total_balance=user.total_balance,
                transaction_count=user.transaction_count
            )
            for user in top_users
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching top users: {str(e)}")

@admin_router.get("/flagged-transactions", response_model=List[TransactionInDB], summary="Get flagged transactions")
def get_flagged_transactions(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get all flagged transactions with details including:
    - Transaction details
    - Sender and receiver information
    - Flag reason
    """
    try:
        return db.query(Transaction).filter(
            Transaction.is_flagged == True,
            Transaction.deleted_at.is_(None)
        ).order_by(Transaction.created_at.desc()).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching flagged transactions: {str(e)}")

@admin_router.post("/transactions/{transaction_id}/review", response_model=TransactionInDB, summary="Review flagged transaction")
def review_transaction(
    transaction_id: int,
    action: str,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Review a flagged transaction and take action:
    - Approve: Mark as completed
    - Reject: Mark as failed
    """
    try:
        transaction = db.query(Transaction).filter(
            Transaction.id == transaction_id,
            Transaction.is_flagged == True
        ).first()
        
        if not transaction:
            raise HTTPException(status_code=404, detail="Flagged transaction not found")

        if action.lower() == "approve":
            transaction.status = TransactionStatus.COMPLETED
            transaction.is_flagged = False
            transaction.flag_reason = None
            
            # Process the transaction
            if transaction.transaction_type == TransactionType.TRANSFER:
                sender_wallet = db.query(Wallet).filter(Wallet.user_id == transaction.sender_id).first()
                receiver_wallet = db.query(Wallet).filter(Wallet.user_id == transaction.receiver_id).first()
                
                if sender_wallet and receiver_wallet:
                    sender_wallet.balance -= transaction.amount
                    receiver_wallet.balance += transaction.amount
                    
        elif action.lower() == "reject":
            transaction.status = TransactionStatus.FAILED
            transaction.is_flagged = False
            transaction.flag_reason = "Transaction rejected by admin"
        else:
            raise HTTPException(status_code=400, detail="Invalid action. Use 'approve' or 'reject'")

        db.commit()
        db.refresh(transaction)
        return transaction
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error reviewing transaction: {str(e)}")

# Include routers
app.include_router(auth_router)
app.include_router(wallet_router)
app.include_router(transaction_router)
app.include_router(admin_router)

# Scheduled fraud detection
scheduler = BackgroundScheduler()

def run_fraud_detection():
    with SessionLocal() as db:
        fraud_service = FraudDetectionService(db)
        fraud_service.scan_recent_transactions()

scheduler.add_job(run_fraud_detection, 'interval', hours=24)
scheduler.start()

# Cleanup on shutdown
@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()

@app.on_event("startup")
async def startup_event():
    """Initialize database and start scheduler on startup"""
    try:
        init_db()
        start_scheduler()
        logger.info("Application startup completed successfully")
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        raise e

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Welcome to Digital Wallet API"} 