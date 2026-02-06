import os
import re
import time
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.exc import OperationalError
from sqlmodel import Field, Session, SQLModel

from ..core.security import get_current_user
from ..database import get_session
from ..models.expense import Expense
from ..models.user import User

router = APIRouter(
    prefix="/receipts",
    tags=["receipts"],
)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}


class ReceiptExpenseItem(SQLModel):
    amount: float = Field(gt=0)
    currency: str = Field(default="CAD", min_length=3, max_length=3, regex="^[A-Z]{3}$")
    description: str = Field(min_length=1, max_length=255)
    category: str = Field(default="OTHER", min_length=1, max_length=50)
    expense_date: Optional[date] = Field(default=None, le=date.today())


class ExpenseRead(SQLModel):
    id: uuid.UUID
    user_id: uuid.UUID
    amount: float
    currency: str
    description: str
    category: str
    expense_date: date
    receipt_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class ReceiptProcessOut(SQLModel):
    receipt_path: str
    ocr_text: str
    expenses_preview: List[ExpenseRead]


class ReceiptConfirmItem(SQLModel):
    amount: float = Field(gt=0)
    currency: str = Field(default="CAD", min_length=3, max_length=3, regex="^[A-Z]{3}$")
    description: str = Field(min_length=1, max_length=255)
    category: str = Field(default="OTHER", min_length=1, max_length=50)
    expense_date: Optional[date] = Field(default=None)


class ReceiptConfirmIn(SQLModel):
    receipt_path: str
    expenses: List[ReceiptConfirmItem]


class ReceiptConfirmOut(SQLModel):
    receipt_path: str
    expenses_created: List[ExpenseRead]


def _ocr_image(image_path: Path) -> str:
    try:
        import pytesseract
        import cv2
        import numpy as np
    except ImportError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"OCR dependencies missing: {str(e)}. Install 'pytesseract' and 'opencv-python', and Tesseract OCR runtime.",
        )

    tess_cmd = os.getenv("TESSERACT_CMD")
    if tess_cmd:
        pytesseract.pytesseract.tesseract_cmd = tess_cmd

    try:
        img = cv2.imread(str(image_path))
        if img is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt file not found")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        h, w = gray.shape[:2]
        scale = 2.0 if max(h, w) < 2000 else 1.0
        if scale != 1.0:
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

        gray = cv2.GaussianBlur(gray, (3, 3), 0)

        thresh = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            10,
        )

        coords = np.column_stack(np.where(thresh < 255))
        if coords.size > 0:
            angle = cv2.minAreaRect(coords)[-1]
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle

            (hh, ww) = thresh.shape[:2]
            M = cv2.getRotationMatrix2D((ww // 2, hh // 2), angle, 1.0)
            thresh = cv2.warpAffine(
                thresh,
                M,
                (ww, hh),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE,
            )

        config = "--oem 3 --psm 6"
        try:
            return pytesseract.image_to_string(thresh, lang="spa+eng", config=config)
        except pytesseract.TesseractError:
            return pytesseract.image_to_string(thresh, lang="eng", config=config)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"OCR failed: {e}")


def _parse_receipt_with_llm(ocr_text: str) -> List[ReceiptExpenseItem]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Missing OPENAI_API_KEY",
        )

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.prompts import ChatPromptTemplate
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM dependencies missing. Install 'langchain' and 'langchain-openai'.",
        )

    import json
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You extract expenses from OCR text of a purchase receipt. "
                "Return only valid JSON. Do not include markdown.",
            ),
            (
                "human",
                "OCR TEXT:\n{ocr_text}\n\n"
                "Extract all line-item expenses (including taxes/tips if explicitly listed). "
                "Output ONLY a JSON array ([]) of objects with fields: amount, currency, description, category, expense_date. "
                "Rules: amount must be a positive number; currency must be 3-letter uppercase if present else CAD; "
                "category should be one of: FOOD, GROCERIES, TRANSPORT, ENTERTAINMENT, HEALTH, UTILITIES, RENT, OTHER; "
                "expense_date must be YYYY-MM-DD if present else null. "
                "If you cannot find any expenses, return an empty JSON array [].",
            ),
        ]
    )

    llm = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0,
        api_key=api_key,
    )

    try:
        result = llm.invoke(prompt.format_messages(ocr_text=ocr_text))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"LLM call failed: {e}")

    content = getattr(result, "content", None)
    if not content or not isinstance(content, str):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="LLM returned empty response")

    try:
        data = json.loads(content)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to parse LLM output: {e}")

    if data is None:
        return []

    if isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LLM output must be a JSON array, got object",
        )
    if not isinstance(data, list):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LLM output must be a JSON array",
        )

    items = [ReceiptExpenseItem(**x) for x in data]

    return items


def _parse_receipt_locally(ocr_text: str) -> List[ReceiptExpenseItem]:
    text = ocr_text.replace("\u00a0", " ")

    pattern = re.compile(
        r"\b(\d+)\s+([A-Za-z0-9\-\_ ]{3,}?)\s*(\d{1,4})\s*[\,\.\s]\s*(\d{2})\b"
    )

    items: List[ReceiptExpenseItem] = []
    for match in pattern.finditer(text):
        _qty_s, desc_raw, amount_int_s, amount_dec_s = match.groups()
        desc = " ".join(desc_raw.strip().split())
        if not desc:
            continue

        try:
            amount = float(f"{int(amount_int_s)}.{int(amount_dec_s):02d}")
        except Exception:
            continue

        if amount <= 0:
            continue

        items.append(
            ReceiptExpenseItem(
                amount=amount,
                currency="CAD",
                description=desc,
                category="OTHER",
                expense_date=None,
            )
        )

    return items


def _classify_categories(descriptions: List[str]) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Missing OPENAI_API_KEY",
        )

    if not descriptions:
        return {}

    unique = list(dict.fromkeys(descriptions))

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.prompts import ChatPromptTemplate
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM dependencies missing. Install 'langchain' and 'langchain-openai'.",
        )

    import json

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You classify expense descriptions into one of these categories: "
                "FOOD, GROCERIES, TRANSPORT, ENTERTAINMENT, HEALTH, UTILITIES, RENT, OTHER. "
                "Return only valid JSON. Do not include markdown.",
            ),
            (
                "human",
                "Given these expense descriptions, return a JSON object mapping each description to a category. "
                "Descriptions: {descriptions_json}",
            ),
        ]
    )

    llm = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0,
        api_key=api_key,
    )

    try:
        result = llm.invoke(
            prompt.format_messages(descriptions_json=json.dumps(unique, ensure_ascii=False))
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"LLM call failed: {e}")

    content = getattr(result, "content", None)
    if not content or not isinstance(content, str):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="LLM returned empty response")

    try:
        data = json.loads(content)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to parse LLM output: {e}")

    if not isinstance(data, dict):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="LLM output must be a JSON object")

    allowed = {"FOOD", "GROCERIES", "TRANSPORT", "ENTERTAINMENT", "HEALTH", "UTILITIES", "RENT", "OTHER"}
    out = {}
    for k, v in data.items():
        if isinstance(k, str) and isinstance(v, str) and v in allowed:
            out[k] = v
    return out


@router.post(
    "/process",
    response_model=ReceiptProcessOut,
    status_code=status.HTTP_201_CREATED,
)
def process_receipt(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo de archivo no permitido")

    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Archivo vacío")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Archivo demasiado grande (max 10MB)")

    ext = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
    }.get(content_type, "")

    base_dir = Path("uploads") / str(current_user.id)
    base_dir.mkdir(parents=True, exist_ok=True)

    filename = f"receipt_{uuid.uuid4().hex}{ext}"
    save_path = base_dir / filename
    with open(save_path, "wb") as f:
        f.write(data)

    receipt_path = str(save_path.as_posix())

    ocr_text = _ocr_image(save_path)
    try:
        ocr_lines = [ln for ln in (ocr_text or "").splitlines() if ln.strip()]
        print("=== DEBUG: OCR TEXT STATS ===")
        print(f"ocr_len={len(ocr_text or '')} nonempty_lines={len(ocr_lines)}")
        preview = (ocr_text or "").replace("\r", "")[:600]
        print("ocr_preview_start=\n" + preview)
        print("=== DEBUG: OCR TEXT STATS END ===")
    except Exception as e:
        print(f"=== DEBUG: OCR TEXT STATS FAILED: {e} ===")

    items = _parse_receipt_locally(ocr_text)
    print(f"=== DEBUG: PARSED ITEMS COUNT: {len(items)} ===")
    category_map = _classify_categories([i.description for i in items])
    for item in items:
        item.category = category_map.get(item.description, "OTHER")

    # DEBUG: Log parsed expenses without saving
    print("=== DEBUG: Parsed expenses from LLM ===")
    for i, item in enumerate(items, 1):
        print(f"{i}. amount={item.amount} currency={item.currency} description={item.description} category={item.category} expense_date={item.expense_date}")
    print("=========================================")

    now = datetime.utcnow()
    preview_out = [
        ExpenseRead(
            id=uuid.uuid4(),
            user_id=current_user.id,
            amount=item.amount,
            currency=item.currency,
            description=item.description,
            category=item.category,
            expense_date=item.expense_date or date.today(),
            receipt_path=receipt_path,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        for item in items
    ]

    # TODO: Uncomment to save to DB
    # now = datetime.utcnow()
    # created: List[Expense] = []
    #
    # for item in items:
    #     expense = Expense(
    #         id=uuid.uuid4(),
    #         user_id=current_user.id,
    #         amount=item.amount,
    #         currency=item.currency,
    #         description=item.description,
    #         category=item.category,
    #         expense_date=item.expense_date or date.today(),
    #         receipt_path=receipt_path,
    #         created_at=now,
    #         updated_at=now,
    #         deleted_at=None,
    #     )
    #     session.add(expense)
    #     created.append(expense)
    #
    # for attempt in range(3):
    #     try:
    #         session.commit()
    #         break
    #     except OperationalError:
    #         session.rollback()
    #         if attempt == 2:
    #             raise HTTPException(
    #                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #                 detail="Database is busy, please retry",
    #             )
    #         time.sleep(0.25 * (attempt + 1))
    #
    # for exp in created:
    #     session.refresh(exp)
    #
    # created_out = [
    #     ExpenseRead(
    #         id=exp.id,
    #         user_id=exp.user_id,
    #         amount=exp.amount,
    #         currency=exp.currency,
    #         description=exp.description,
    #         category=exp.category,
    #         expense_date=exp.expense_date,
    #         receipt_path=exp.receipt_path,
    #         created_at=exp.created_at,
    #         updated_at=exp.updated_at,
    #         deleted_at=exp.deleted_at,
    #     )
    #     for exp in created
    # ]
    #
    # return ReceiptProcessOut(receipt_path=receipt_path, ocr_text=ocr_text, expenses_created=created_out)

    return ReceiptProcessOut(receipt_path=receipt_path, ocr_text=ocr_text, expenses_preview=preview_out)


@router.post(
    "/confirm",
    response_model=ReceiptConfirmOut,
    status_code=status.HTTP_201_CREATED,
)
def confirm_receipt(
    payload: ReceiptConfirmIn,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    path = Path(payload.receipt_path)
    uploads_root = Path("uploads").resolve()
    try:
        resolved = path.resolve()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid receipt_path")
    if uploads_root not in resolved.parents and resolved != uploads_root:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="receipt_path must be under uploads/")

    user_dir = (Path("uploads") / str(current_user.id)).resolve()
    if user_dir not in resolved.parents:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="receipt_path does not belong to current user")

    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt file not found")

    now = datetime.utcnow()
    created: List[Expense] = []

    print(f"=== DEBUG /receipts/confirm ===")
    print(f"Received {len(payload.expenses)} expenses")
    
    for idx, item in enumerate(payload.expenses, 1):
        final_date = item.expense_date or date.today()
        print(f"Expense {idx}: received_date={item.expense_date}, final_date={final_date}, desc={item.description}")
        
        expense = Expense(
            id=uuid.uuid4(),
            user_id=current_user.id,
            amount=item.amount,
            currency=item.currency,
            description=item.description,
            category=item.category,
            expense_date=final_date,
            receipt_path=str(path.as_posix()),
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        session.add(expense)
        created.append(expense)
    
    print(f"================================")

    for attempt in range(3):
        try:
            session.commit()
            break
        except OperationalError:
            session.rollback()
            if attempt == 2:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database is busy, please retry",
                )
            time.sleep(0.25 * (attempt + 1))

    created_out = [
        ExpenseRead(
            id=exp.id,
            user_id=exp.user_id,
            amount=exp.amount,
            currency=exp.currency,
            description=exp.description,
            category=exp.category,
            expense_date=exp.expense_date,
            receipt_path=exp.receipt_path,
            created_at=exp.created_at,
            updated_at=exp.updated_at,
            deleted_at=exp.deleted_at,
        )
        for exp in created
    ]

    return ReceiptConfirmOut(receipt_path=str(path.as_posix()), expenses_created=created_out)
