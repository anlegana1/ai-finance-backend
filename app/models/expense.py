import uuid
from datetime import datetime, date
from typing import Optional
from sqlmodel import SQLModel, Field


class Expense(SQLModel, table=True):
    __tablename__ = "expenses"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)

    user_id: uuid.UUID = Field(
        foreign_key="users.id",
        index=True
    )

    amount: float
    currency: str = Field(default="CAD", max_length=3)
    description: str
    category: str = Field(default="OTHER", max_length=50)
    expense_date: date = Field(default_factory=date.today)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    deleted_at: Optional[datetime] = Field(default=None)

