import uuid
from datetime import datetime, date
from typing import List, Optional

import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlmodel import SQLModel, Field, Session, select
from sqlalchemy.exc import OperationalError
import time

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
    receipt_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class OCRRead(SQLModel):
    text: str


# ─────────────────────────────
#   ENDPOINTS
# ─────────────────────────────

@router.post(
    "",
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


@router.post(
    "/{expense_id}/ocr",
    response_model=OCRRead,
    status_code=status.HTTP_200_OK,
)
def ocr_receipt(
    expense_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    expense = session.get(Expense, expense_id)
    if not expense or expense.deleted_at is not None or expense.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
    if not expense.receipt_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No receipt_path set for this expense")

    path = Path(expense.receipt_path)
    # Restrict to uploads directory for safety
    uploads_root = Path("uploads").resolve()
    try:
        resolved = path.resolve()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid receipt_path")
    if uploads_root not in resolved.parents and resolved != uploads_root:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="receipt_path must be under uploads/")
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt file not found")

    ext = resolved.suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only JPEG/PNG supported for OCR")

    try:
        # Local imports to avoid startup crash if deps not installed
        from PIL import Image
        import pytesseract
        # Allow overriding tesseract executable via env var
        tess_cmd = os.getenv("TESSERACT_CMD")
        if tess_cmd:
            pytesseract.pytesseract.tesseract_cmd = tess_cmd
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OCR dependencies missing. Install 'pillow' and 'pytesseract', and Tesseract OCR runtime.",
        )

    try:
        with Image.open(resolved) as img:
            text = pytesseract.image_to_string(img)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"OCR failed: {e}")

    return OCRRead(text=text)


@router.get(
    "",
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


MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "application/pdf"}


@router.post(
    "/{expense_id}/receipt",
    response_model=ExpenseRead,
    status_code=status.HTTP_200_OK,
)
def upload_receipt(
    expense_id: uuid.UUID,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Sube un recibo (imagen/pdf) para un gasto y guarda la ruta local.

    - Tipos permitidos: image/jpeg, image/png, application/pdf.
    - Tamaño máximo: 10 MB.
    - Ruta: uploads/{user_id}/{expense_id}_{uuid}.{ext}
    """
    expense = session.get(Expense, expense_id)
    if not expense or expense.deleted_at is not None or expense.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expense not found for user {current_user.id}; expense_id={expense_id}",
        )

    # Validar tipo
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo de archivo no permitido")

    # Leer contenido con límite
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Archivo vacío")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Archivo demasiado grande (max 10MB)")

    # Determinar extensión por content-type
    ext = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "application/pdf": ".pdf",
    }.get(content_type, "")

    # Carpeta destino
    base_dir = Path("uploads") / str(current_user.id)
    base_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{expense_id}_{uuid.uuid4().hex}{ext}"
    save_path = base_dir / filename

    with open(save_path, "wb") as f:
        f.write(data)

    # Guardar ruta relativa
    expense.receipt_path = str(save_path.as_posix())
    expense.updated_at = datetime.utcnow()
    # Try committing with small retries to avoid transient SQLite locks
    for attempt in range(3):
        try:
            session.add(expense)
            session.commit()
            session.refresh(expense)
            break
        except OperationalError:
            session.rollback()
            if attempt == 2:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database is busy, please retry",
                )
            time.sleep(0.25 * (attempt + 1))
    return expense
