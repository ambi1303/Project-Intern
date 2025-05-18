# Digital Wallet System

A secure and feature-rich digital wallet system built with FastAPI, implementing cash management and fraud detection capabilities.

## Features

- User Authentication & Session Management
  - Secure user registration and login
  - JWT token-based authentication
  - Protected endpoints with authentication middleware

- Wallet Operations
  - Deposit and withdraw virtual cash
  - Transfer funds between users
  - Transaction history tracking
  - Multi-currency support

- Transaction Processing & Validation
  - Atomic transaction processing
  - Balance validation
  - Transaction status tracking

- Fraud Detection
  - Rule-based fraud detection
  - Suspicious pattern monitoring
  - Daily automated fraud scans
  - Transaction flagging system

- Admin & Reporting
  - System statistics
  - Top users by balance
  - Transaction volume tracking
  - Flagged transaction monitoring

## Tech Stack

- FastAPI
- SQLAlchemy
- Pydantic
- JWT Authentication
- APScheduler
- SQLite (can be easily switched to PostgreSQL)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd digital-wallet
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
uvicorn app.main:app --reload
```

## API Documentation

Once the application is running, you can access the API documentation at:
- Swagger UI: http://localhost:8000/api/v1/docs
- ReDoc: http://localhost:8000/api/v1/redoc

## API Endpoints

### Authentication
- POST `/api/v1/register` - Register a new user
- POST `/api/v1/login` - Login and get access token

### Wallet
- GET `/api/v1/wallet` - Get wallet details
- POST `/api/v1/transactions` - Create a new transaction
- GET `/api/v1/transactions` - Get transaction history

### Admin
- GET `/api/v1/admin/stats` - Get system statistics
- GET `/api/v1/admin/top-users` - Get top users by balance

## Security Features

- Password hashing using bcrypt
- JWT token-based authentication
- Rate limiting
- Input validation
- Fraud detection rules:
  - Large transaction monitoring
  - Rapid transaction detection
  - Unusual pattern detection

## Development

### Running Tests
```bash
pytest
```

### Database Migrations
The project uses SQLite by default. To switch to PostgreSQL:
1. Update the DATABASE_URL in `app/core/config.py`
2. Create a new database
3. Run migrations

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 