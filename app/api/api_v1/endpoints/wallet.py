from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db
from app.models.models import User, Wallet
from app.schemas.schemas import WalletInDB
from datetime import datetime
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/", response_model=WalletInDB)
def get_wallet(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's wallet"""
    try:
        # Get or create wallet
        wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
        
        if not wallet:
            # Create new wallet with current timestamp
            wallet = Wallet(
                user_id=current_user.id,
                created_at=datetime.utcnow()
            )
            db.add(wallet)
            db.commit()
            db.refresh(wallet)
            logger.info(f"Created new wallet for user {current_user.id}")
        elif not wallet.created_at:
            # Update existing wallet with created_at if missing
            wallet.created_at = datetime.utcnow()
            db.commit()
            db.refresh(wallet)
            logger.info(f"Updated created_at for wallet {wallet.id}")
        
        logger.info(f"Retrieved wallet for user {current_user.id}")
        return wallet
        
    except Exception as e:
        logger.error(f"Error retrieving wallet: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving wallet"
        ) 