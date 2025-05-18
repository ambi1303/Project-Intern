import uvicorn
from app.main import app
from app.db.session import SessionLocal
from app.core.config import settings
from app.services.scheduler import scheduler
from sqlalchemy import text

def check_db_connection():
    """Check database connection and create tables if they don't exist"""
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        print("Database connection successful")
    except Exception as e:
        print(f"Database connection failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    # Check database connection
    check_db_connection()
    
    # Start the scheduler
    scheduler.start()
    print("Scheduler started")
    
    # Run the application with development settings
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,    # Enable auto-reload for development
        reload_dirs=["app"],  # Only watch the app directory
        workers=1,
        log_level="info"
    ) 