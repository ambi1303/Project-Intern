import uvicorn
from app.db.init_db import init_db

if __name__ == "__main__":
    # Initialize database without resetting
    init_db(reset=False)
    
    # Run the application
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True) 