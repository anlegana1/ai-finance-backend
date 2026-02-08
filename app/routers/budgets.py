import re
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Field, Session, SQLModel, select

from ..core.security import get_current_user
from ..database import get_session
from ..models.budget import Budget
from ..models.user import User


router = APIRouter(
    prefix="/budgets",
    tags=["budgets"],
)


_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


class BudgetBase(SQLModel):
    month: str = Field(min_length=7, max_length=7)
    category: str = Field(default="OTHER", min_length=1, max_length=50)
    amount: float = Field(gt=0)


class BudgetCreate(BudgetBase):
    pass


class BudgetRead(BudgetBase):
    id: uuid.UUID
    user_id: uuid.UUID
    currency: str
    created_at: datetime
    updated_at: datetime


@router.get(
    "",
    response_model=List[BudgetRead],
    status_code=status.HTTP_200_OK,
)
def list_budgets(
    month: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Budget).where(Budget.user_id == current_user.id)
    if month:
        if not _MONTH_RE.match(month):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid month")
        stmt = stmt.where(Budget.month == month)
    stmt = stmt.order_by(Budget.month.desc(), Budget.category.asc())
    return list(session.exec(stmt).all())


@router.post(
    "",
    response_model=BudgetRead,
    status_code=status.HTTP_201_CREATED,
)
def upsert_budget(
    payload: BudgetCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if not _MONTH_RE.match(payload.month):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid month")

    now = datetime.utcnow()

    existing = session.exec(
        select(Budget).where(
            Budget.user_id == current_user.id,
            Budget.month == payload.month,
            Budget.category == payload.category,
        )
    ).first()

    if existing is None:
        b = Budget(
            id=uuid.uuid4(),
            user_id=current_user.id,
            month=payload.month,
            category=payload.category,
            amount=payload.amount,
            currency=current_user.default_currency,
            created_at=now,
            updated_at=now,
        )
        session.add(b)
        session.commit()
        session.refresh(b)
        return b

    existing.amount = payload.amount
    existing.currency = current_user.default_currency
    existing.updated_at = now
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return existing


@router.delete(
    "/{budget_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_budget(
    budget_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    b = session.get(Budget, budget_id)
    if not b or b.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    session.delete(b)
    session.commit()
    return None
