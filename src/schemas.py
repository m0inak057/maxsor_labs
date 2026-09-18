import datetime
from pydantic import BaseModel, EmailStr
from typing import Optional


class UserRegister(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True


class TicketCreate(BaseModel):
    message: str


class DecisionOut(BaseModel):
    id: int
    action: str
    reason: str
    confidence: float
    sources: list[str]
    created_at: datetime.datetime

    class Config:
        from_attributes = True


class TicketOut(BaseModel):
    id: int
    message: str
    created_at: datetime.datetime
    decision: Optional[DecisionOut] = None

    class Config:
        from_attributes = True


class AIDecision(BaseModel):
    action: str
    confidence: float
    reason: str
    sources: list[str]
