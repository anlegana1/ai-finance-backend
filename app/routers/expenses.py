import uuid
from datetime import datetime, date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import SQLModel, Field, Session, select

from ..database import get_session
from ..models.expense import Expense
from ..models.user import User
from ..core.security import get_current_user

router = APIRouter(
    prefix="/expenses",
    tags=["expenses"],
)

# ─────────────────────────────
#   SCHEMAS (Pydantic/SQLModel)
# ─────────────────────────────

class ExpenseBase(SQLModel):
    amount: float = Field(gt=0)
    currency: str = Field(default="CAD", min_length=3, max_length=3, regex="^[A-Z]{3}$")
    description: str = Field(min_length=1, max_length=255)
    category: str = Field(default="OTHER", min_length=1, max_length=50)
    expense_date: Optional[date] = Field(default=None, le=date.today())


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseUpdate(SQLModel):
    amount: Optional[float] = Field(default=None, gt=0)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3, regex="^[A-Z]{3}$")
    description: Optional[str] = Field(default=None, min_length=1, max_length=255)
    category: Optional[str] = Field(default=None, min_length=1, max_length=50)
    expense_date: Optional[date] = Field(default=None, le=date.today())


class ExpenseRead(ExpenseBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


# ─────────────────────────────
#   ENDPOINTS
# ─────────────────────────────

@router.post(
    "/",
    response_model=ExpenseRead,
    status_code=status.HTTP_201_CREATED,
)
def create_expense(
    expense_in: ExpenseCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Crear un gasto nuevo para el usuario autenticado.

    - El user_id se obtiene del JWT vía get_current_user.
    """
    now = datetime.utcnow()

    expense = Expense(
        id=uuid.uuid4(),
        user_id=current_user.id,
        amount=expense_in.amount,
        currency=expense_in.currency,
        description=expense_in.description,
        category=expense_in.category,
        expense_date=expense_in.expense_date or date.today(),
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )

    session.add(expense)
    session.commit()
    session.refresh(expense)
    return expense


@router.get(
    "/",
    response_model=List[ExpenseRead],
)
def list_expenses(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Listar gastos del usuario autenticado.

    - Siempre excluye los que tienen deleted_at (soft delete).
    - Ordenados por fecha de gasto descendente.
    """
    statement = select(Expense).where(Expense.deleted_at.is_(None))
    statement = statement.where(Expense.user_id == current_user.id)
    statement = statement.order_by(Expense.expense_date.desc())

    expenses = session.exec(statement).all()
    return expenses


@router.get(
    "/{expense_id}",
    response_model=ExpenseRead,
)
def get_expense(
    expense_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Obtener un gasto por ID del usuario autenticado (si no está soft-deleted)."""
    expense = session.get(Expense, expense_id)

    if not expense or expense.deleted_at is not None or expense.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found",
        )

    return expense


@router.patch(
    "/{expense_id}",
    response_model=ExpenseRead,
)
def update_expense(
    expense_id: uuid.UUID,
    expense_in: ExpenseUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Actualizar parcialmente un gasto del usuario autenticado."""
    expense = session.get(Expense, expense_id)

    if not expense or expense.deleted_at is not None or expense.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found",
        )

    updated = False

    if expense_in.amount is not None:
        expense.amount = expense_in.amount
        updated = True
    if expense_in.currency is not None:
        expense.currency = expense_in.currency
        updated = True
    if expense_in.description is not None:
        expense.description = expense_in.description
        updated = True
    if expense_in.category is not None:
        expense.category = expense_in.category
        updated = True
    if expense_in.expense_date is not None:
        expense.expense_date = expense_in.expense_date
        updated = True

    if updated:
        expense.updated_at = datetime.utcnow()
        session.add(expense)
        session.commit()
        session.refresh(expense)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    return expense


@router.delete(
    "/{expense_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_expense(
    expense_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Soft delete del gasto del usuario autenticado:
    - En vez de borrar el registro, marca deleted_at.
    """
    expense = session.get(Expense, expense_id)

    if not expense or expense.deleted_at is not None or expense.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found",
        )

    expense.deleted_at = datetime.utcnow()
    expense.updated_at = datetime.utcnow()

    session.add(expense)
    session.commit()
    return
