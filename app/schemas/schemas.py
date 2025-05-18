from typing import Optional, Dict
from pydantic import BaseModel, EmailStr
from datetime import datetime
from app.models.models import TransactionType, TransactionStatus, CurrencyType

# User schemas
class UserBase(BaseModel):
    email: EmailStr
    full_name: str

class UserCreate(UserBase):
    password: str

class UserInDB(UserBase):
    id: int
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime
    is_deleted: bool
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: Optional[str] = None

# Wallet schemas
class WalletBase(BaseModel):
    balances: Dict[str, float]

class WalletInDB(WalletBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    is_deleted: bool
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Transaction schemas
class TransactionBase(BaseModel):
    amount: float
    currency: CurrencyType = CurrencyType.USD
    transaction_type: TransactionType
    description: Optional[str] = None
    receiver_email: Optional[EmailStr] = None

class TransactionCreate(TransactionBase):
    pass

class TransactionInDB(TransactionBase):
    id: int
    wallet_id: int
    sender_id: Optional[int]
    receiver_id: Optional[int]
    status: TransactionStatus
    created_at: datetime
    updated_at: datetime
    is_deleted: bool
    deleted_at: Optional[datetime] = None
    is_flagged: bool
    flag_reason: Optional[str] = None

    class Config:
        from_attributes = True

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