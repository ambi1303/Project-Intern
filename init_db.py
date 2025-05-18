from app.db.session import SessionLocal, engine
from app.models.models import Base, User, AdminUser, Wallet
from app.core.security import get_password_hash
from app.core.config import settings
from sqlalchemy import inspect
from datetime import datetime
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    """Initialize the database with required tables and initial data."""
    try:
        # Drop all tables first
        logger.info("Dropping all existing tables...")
        Base.metadata.drop_all(bind=engine)
        
        # Create all tables
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        
        db = SessionLocal()
        try:
            # Create admin user
            admin = db.query(User).filter(User.email == "admin@example.com").first()
            if not admin:
                admin = User(
                    email="admin@example.com",
                    hashed_password=get_password_hash("admin123"),
                    full_name="Admin User",
                    is_active=True,
                    is_admin=True,
                    created_at=datetime.utcnow()
                )
                db.add(admin)
                db.commit()
                logger.info("Admin user created successfully")
            else:
                logger.info("Admin user already exists")
            
            # Create regular user for testing
            test_user = db.query(User).filter(User.email == "test@example.com").first()
            if not test_user:
                test_user = User(
                    email="test@example.com",
                    hashed_password=get_password_hash("test123"),
                    full_name="Test User",
                    is_active=True,
                    created_at=datetime.utcnow()
                )
                db.add(test_user)
                db.commit()
                db.refresh(test_user)
                
                # Create wallet for test user
                test_wallet = Wallet(
                    user_id=test_user.id,
                    created_at=datetime.utcnow()
                )
                db.add(test_wallet)
                db.commit()
                logger.info("Test user and wallet created successfully")
            
            # Update any existing wallets with missing created_at
            wallets = db.query(Wallet).filter(Wallet.created_at.is_(None)).all()
            for wallet in wallets:
                wallet.created_at = datetime.utcnow()
            if wallets:
                db.commit()
                logger.info(f"Updated {len(wallets)} wallets with created_at timestamps")
                
        except Exception as e:
            logger.error(f"Error during database initialization: {e}")
            db.rollback()
            raise
        finally:
            db.close()
            
        logger.info("Database initialization completed successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

if __name__ == "__main__":
    logger.info("Starting database initialization...")
    init_db()
    logger.info("Database initialization completed") 