from typing import Optional, Dict, List
from pydantic import BaseModel, EmailStr
from datetime import datetime
from app.models.models import TransactionType, TransactionStatus, CurrencyType

# User schemas
class UserBase(BaseModel):
    email: EmailStr
    full_name: str

class UserCreate(UserBase):
    password: str

class UserUpdate(UserBase):
    password: Optional[str] = None

class UserInDB(UserBase):
    id: int
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_deleted: bool
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# Wallet schemas
class WalletBase(BaseModel):
    balances: Dict[str, float] = {
        "USD": 0.0,
        "EUR": 0.0,
        "GBP": 0.0,
        "JPY": 0.0,
        "INR": 0.0,
        "BONUS": 0.0
    }

class WalletCreate(WalletBase):
    user_id: int

class WalletUpdate(WalletBase):
    pass

class WalletInDB(WalletBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

# Transaction schemas
class TransactionBase(BaseModel):
    amount: float
    currency: CurrencyType
    type: TransactionType
    description: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class TransactionCreate(TransactionBase):
    receiver_email: Optional[str] = None  # Only required for TRANSFER type

class TransactionUpdate(BaseModel):
    status: Optional[TransactionStatus] = None
    is_flagged: Optional[bool] = None
    flag_reason: Optional[str] = None

class TransactionInDB(TransactionBase):
    id: int
    sender_id: int
    receiver_id: int
    sender_wallet_id: int
    receiver_wallet_id: int
    status: TransactionStatus
    is_flagged: bool = False
    flag_reason: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None

    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# Admin schemas
class AdminStats(BaseModel):
    total_users: int
    total_transactions: int
    total_volume: Dict[str, float]  # Volume per currency
    flagged_transactions: int

class TopUser(BaseModel):
    id: int
    email: str
    balances: Dict[str, float]  # Balances per currency
    transaction_count: int 