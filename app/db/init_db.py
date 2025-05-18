from sqlalchemy.orm import Session
from app.db.base_class import Base
from app.db.session import engine
from app.models.models import User, Wallet, Transaction  # Import all models
from app.core.security import get_password_hash
from app.core.config import settings

def init_db(reset: bool = False):
    """
    Initialize the database.
    Args:
        reset (bool): If True, drops all tables before creating them.
    """
    if reset:
        print("Dropping all tables...")
        Base.metadata.drop_all(bind=engine)
    
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    
    # Create admin user only if reset is True or admin doesn't exist
    db = Session(engine)
    admin_email = "admin@example.com"
    admin_password = "admin123"  # You should change this in production
    
    # Check if admin already exists
    admin = db.query(User).filter(User.email == admin_email).first()
    if not admin:
        admin = User(
            email=admin_email,
            hashed_password=get_password_hash(admin_password),
            full_name="Admin User",
            is_admin=True,
            is_active=True
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        
        # Create wallet for admin
        admin_wallet = Wallet(user_id=admin.id)
        db.add(admin_wallet)
        db.commit()
        print("Admin user created successfully!")
    else:
        print("Admin user already exists.")
    
    db.close()
    print("Database initialization completed!")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Initialize the database")
    parser.add_argument("--reset", action="store_true", help="Reset the database by dropping all tables")
    args = parser.parse_args()
    
    init_db(reset=args.reset) 