import uuid
from datetime import datetime

from sqlmodel import SQLModel, Field


class Budget(SQLModel, table=True):
    __tablename__ = "budgets"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)

    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)

    # YYYY-MM (e.g. 2026-02)
    month: str = Field(index=True, min_length=7, max_length=7)

    category: str = Field(default="OTHER", max_length=50, index=True)

    amount: float = Field(gt=0)
    currency: str = Field(default="CAD", max_length=3)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
