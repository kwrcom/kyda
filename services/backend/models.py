"""
Pydantic models for request/response validation

Reason: Defines data schemas for API endpoints with automatic validation
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class LoginRequest(BaseModel):
    """
    Login request schema
    
    Reason: Validates username and password for authentication
    """
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)


class TokenResponse(BaseModel):
    """
    Token response schema
    
    Reason: Returns access and refresh tokens after successful authentication
    """
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """
    Token refresh request schema
    
    Reason: Validates refresh token for obtaining new access token
    """
    refresh_token: str


class Transaction(BaseModel):
    """
    Transaction data schema
    
    Reason: Represents a single transaction with all relevant fields
    """
    transaction_id: str
    user_id: str
    amount: float
    merchant_category: str
    timestamp: datetime
    location: str
    device_id: str
    is_fraud: bool


class TransactionListResponse(BaseModel):
    """
    Transaction list response schema
    
    Reason: Returns paginated list of transactions
    """
    transactions: list[Transaction]
    total: int
    page: int
    page_size: int


class WebSocketMessage(BaseModel):
    """
    WebSocket message schema
    
    Reason: Defines structure for real-time notifications
    """
    type: str  # "transaction", "fraud_alert", "system"
    data: dict
    timestamp: datetime
