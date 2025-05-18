# Digital Wallet System

A secure and feature-rich digital wallet system built with FastAPI, supporting multiple currencies and advanced security features.

## Features

- Multi-currency support (USD, EUR, GBP, JPY, INR, BONUS)
- Secure user authentication with JWT tokens
- Transaction management with fraud detection
- Admin dashboard for system monitoring
- Email notifications for transactions
- Soft delete functionality for data retention
- Daily fraud detection scanning

## Prerequisites

- Python 3.8+
- PostgreSQL
- Redis (for background tasks)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd digital-wallet
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Initialize the database:
```bash
python init_db.py
```

## Running the Application

Start the application:
```bash
python run.py
```

The API will be available at `http://localhost:8000`

API Documentation: `http://localhost:8000/docs`

## API Endpoints

### Authentication
- POST `/api/v1/auth/register` - Register new user
- POST `/api/v1/auth/login` - Login and get access token

### Wallet
- GET `/api/v1/wallet` - Get user's wallet
- GET `/api/v1/wallet/transactions` - Get transaction history

### Transactions
- POST `/api/v1/transactions` - Create new transaction
- GET `/api/v1/transactions` - List user's transactions

### Admin
- GET `/api/v1/admin/stats` - Get system statistics
- GET `/api/v1/admin/top-users` - Get top users
- GET `/api/v1/admin/flagged-transactions` - Get flagged transactions
- POST `/api/v1/admin/transactions/{transaction_id}/review` - Review flagged transaction

## Security Features

- Password hashing with bcrypt
- JWT token authentication
- Rate limiting
- Fraud detection system
- Input validation
- SQL injection prevention
- XSS protection

## Database Schema

The system uses PostgreSQL with the following main tables:
- users
- wallets
- transactions
- admin_users

## Background Jobs

- Daily fraud detection scanning
- Email notification sending
- Transaction status updates

## Development

### Code Structure
```
app/
├── api/
│   └── api_v1/
│       └── endpoints/
├── core/
├── db/
├── models/
├── schemas/
├── services/
└── utils/
```

### Running Tests
```bash
pytest
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 