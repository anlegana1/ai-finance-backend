# 💰 AI Finance Assistant - Backend API

REST API for intelligent expense management with JWT authentication, OCR receipt processing, and AI-powered classification. Built with FastAPI, SQLModel, and SQLite.

## 🎯 Features

- 🔐 **JWT Authentication** - Secure registration and login with bcrypt
- 📸 **Receipt OCR** - Automatic processing with Tesseract
- 🤖 **AI Classification** - Smart categorization using OpenAI GPT
- 🖼️ **Image Preprocessing** - Image optimization with OpenCV
- 💾 **Database** - SQLite with soft-delete and SQLModel ORM
- 📊 **Full CRUD** - Complete expense management per user
- 🔍 **Validation** - Pydantic data validation
- 📝 **Auto Docs** - Swagger UI and ReDoc included

---

## 🛠️ Tech Stack

- **FastAPI** - Modern, high-performance web framework
- **SQLModel** - ORM with integrated Pydantic validation
- **Tesseract OCR** - Text extraction from images
- **LangChain + OpenAI** - AI-powered expense categorization with GPT-3.5
- **OpenCV** - Image preprocessing and enhancement
- **JWT + Bcrypt** - Authentication and security
- **SQLite/PostgreSQL** - Lightweight relational database
- **Python 3.11+** - Base language

---

## 📦 Installation

### Prerequisites
- Python **3.11** or higher
- Tesseract OCR installed ([Download](https://github.com/tesseract-ocr/tesseract))
- OpenAI account with API Key

### 1. Clone and Setup
```powershell
cd backend
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Environment Variables
Create `backend/.env` based on `.env.example`:

```env
OPENAI_API_KEY=sk-your-key-here
SECRET_KEY=your-secret-jwt-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
TESSERACT_CMD=C:/Program Files/Tesseract-OCR/tesseract.exe
```

**Generate secure SECRET_KEY:**
```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Start Server
```powershell
cd backend
uvicorn app.main:app --reload
```

**Available URLs:**
- 🌐 API: http://127.0.0.1:8000  
- 📚 Swagger UI: http://127.0.0.1:8000/docs  
- 📖 ReDoc: http://127.0.0.1:8000/redoc

---

## 📁 Project Structure

```
backend/
├── .env                    # Environment variables (DO NOT commit)
├── .env.example            # Configuration template
├── .gitignore
├── requirements.txt        # Python dependencies
├── finance.db              # SQLite database
├── uploads/                # Receipts per user
│   └── {user_id}/         # Folder per user
└── app/
    ├── __init__.py
    ├── main.py             # Entry point - FastAPI app
    ├── config.py           # Global configuration
    ├── database.py         # SQLModel setup and sessions
    ├── core/
    │   ├── jwt.py          # JWT generation/validation
    │   └── security.py     # Password hashing (bcrypt)
    ├── models/
    │   ├── user.py         # User model
    │   └── expense.py      # Expense model
    └── routers/
        ├── auth.py         # POST /auth/register, /login
        ├── receipts.py     # POST /receipts/process, /confirm
        └── expenses.py     # CRUD /expenses/*
```

---

## 🏗️ Backend Architecture

### Application Layers

```
┌─────────────────────────────────────────┐
│         FastAPI Application             │
│         (app/main.py)                   │
│  - CORS Middleware                      │
│  - Auto table creation                  │
└─────────────────┬───────────────────────┘
                  │
        ┌─────────┴──────────┐
        │                    │
┌───────▼────────┐  ┌────────▼─────────┐
│   Routers      │  │   Dependencies   │
│  /auth         │  │  - get_session   │
│  /receipts     │  │  - get_current   │
│  /expenses     │  │    _user (JWT)   │
└───────┬────────┘  └──────────────────┘
        │
┌───────▼──────────────────────────────┐
│      Business Logic Layer            │
│ - OCR (Tesseract)                    │
│ - Preprocessing (OpenCV)             │
│ - AI Classification (OpenAI)         │
│ - Data validation                    │
│ - File security                      │
└───────┬──────────────────────────────┘
        │
┌───────▼────────┐  ┌────────────────┐
│   Models       │  │   Security     │
│  User          │  │  JWT tokens    │
│  Expense       │  │  Bcrypt hash   │
└───────┬────────┘  └────────────────┘
        │
┌───────▼──────────┐
│   Database       │
│   SQLite         │
│   SQLModel ORM   │
└──────────────────┘
```

### Core Components

#### 1. **Models** (`app/models/`)
Data structure definition with automatic validation:

**User:**
- Unique ID (UUID)
- Email (unique, indexed)
- Hashed password (bcrypt)
- Timestamps (created_at, updated_at)
- Soft-delete (deleted_at)

**Expense:**
- Unique ID (UUID)
- Linked to User (FK)
- Amount, currency, description, category
- Expense date
- Receipt path (optional)
- Timestamps and soft-delete

#### 2. **Routers** (`app/routers/`)
REST endpoints organized by domain:

**auth.py** - Authentication
- `POST /auth/register` - Create account
- `POST /auth/login` - Get JWT token
- `POST /auth/token` - OAuth2 compatible (Swagger UI)

**receipts.py** - OCR Processing
- `POST /receipts/process` - Upload and process receipt
- `POST /receipts/confirm` - Save edited expenses

**expenses.py** - CRUD
- `GET /expenses/` - List expenses
- `GET /expenses/{id}` - Get specific expense
- `PATCH /expenses/{id}` - Update expense
- `DELETE /expenses/{id}` - Delete (soft-delete)

#### 3. **Core** (`app/core/`)
Cross-cutting functionalities:

**security.py**
- `hash_password()` - Bcrypt with cost factor 12
- `verify_password()` - Password validation

**jwt.py**
- `create_access_token()` - Generate JWT with expiration
- `get_current_user()` - Dependency for token validation

#### 4. **Database** (`app/database.py`)
- SQLModel engine configured for SQLite
- `get_session()` - Dependency injection
- `init_db()` - Automatic table creation

#### 5. **LangChain Integration** (`app/routers/receipts.py`)

We use LangChain as a wrapper around OpenAI's API for intelligent expense categorization:

**Purpose:**
- Automatically classify expense descriptions into predefined categories
- Process single or batch expenses efficiently
- Provide structured prompts to GPT-3.5-turbo

**Implementation:**
```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# Initialize LLM
llm = ChatOpenAI(
    model="gpt-3.5-turbo",
    api_key=openai_api_key,
    temperature=0
)

# Create prompt template
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expense categorizer..."),
    ("human", "Classify: {descriptions}")
])

# Chain prompt with LLM
chain = prompt | llm
result = chain.invoke({"descriptions": expense_descriptions})
```

**Categories Supported:**
- `FOOD` - Restaurants and food delivery
- `GROCERIES` - Supermarket purchases
- `TRANSPORT` - Gas, public transit, parking
- `ENTERTAINMENT` - Movies, games, subscriptions
- `HEALTH` - Pharmacy, medical services
- `UTILITIES` - Bills (electricity, water, internet)
- `RENT` - Housing payments
- `OTHER` - Miscellaneous expenses

**Functions:**
- `classify_category_with_ai(description)` - Single expense classification
- `classify_multiple_with_ai(descriptions_list)` - Batch classification (more efficient)

**Why LangChain?**
- Cleaner, more maintainable code than raw OpenAI API calls
- Built-in prompt templates and chaining
- Easy to swap LLM providers if needed
- Structured output parsing

---

## 🔄 Backend Workflow

### 1. Authentication

```
Client → POST /auth/register
           │
           ├─ Validates email format
           ├─ Verifies email doesn't exist
           ├─ Validates password (no spaces)
           ├─ Hashes password with bcrypt
           └─ Creates User record in DB
           
Client → POST /auth/login
           │
           ├─ Finds User by email
           ├─ Verifies password with bcrypt
           ├─ Generates JWT token (30 min)
           │  └─ Payload: {sub: user_id, email}
           └─ Returns: {access_token, token_type}
           
Client → Subsequent requests
           └─ Header: Authorization: Bearer <token>
```

### 2. Receipt Processing Pipeline

```
Client → POST /receipts/process (multipart/form-data)
           │
           ├─ 1. AUTHENTICATION
           │    ├─ Validates JWT token
           │    └─ Extracts user_id from token
           │
           ├─ 2. FILE VALIDATION
           │    ├─ Content-Type: image/jpeg or image/png
           │    ├─ Max size: 10MB
           │    └─ Non-empty file
           │
           ├─ 3. STORAGE
           │    ├─ Creates folder: uploads/{user_id}/
           │    ├─ Generates unique name: receipt_{uuid}.jpg
           │    └─ Saves file to disk
           │
           ├─ 4. PREPROCESSING (OpenCV)
           │    ├─ Reads image with cv2
           │    ├─ Converts to grayscale
           │    ├─ Resizes (max 2000px)
           │    ├─ Applies adaptive threshold
           │    ├─ Detects and corrects rotation (deskew)
           │    └─ Saves processed image temporarily
           │
           ├─ 5. OCR (Tesseract)
           │    ├─ Executes pytesseract.image_to_string()
           │    ├─ Extracts all text from receipt
           │    └─ Returns string with full text
           │
           ├─ 6. LOCAL PARSING (Regex)
           │    ├─ Pattern: \d+ [text] \d+[,.]\d{2}
           │    ├─ Extracts: quantity, description, price
           │    ├─ Validates amount > 0
           │    ├─ Cleans description
           │    ├─ Assigns default currency: CAD
           │    └─ Creates list of ReceiptExpenseItem
           │
           ├─ 7. AI CLASSIFICATION (LangChain + OpenAI)
           │    ├─ Uses LangChain ChatOpenAI wrapper
           │    ├─ Creates ChatPromptTemplate with system message
           │    ├─ Sends descriptions to GPT-3.5-turbo
           │    ├─ Prompt: "Classify into categories"
           │    ├─ Categories: FOOD, GROCERIES, TRANSPORT, etc.
           │    ├─ LangChain chains: prompt | llm
           │    ├─ Parses JSON response
           │    └─ Maps categories to each item
           │
           └─ 8. RESPONSE
                └─ Returns: {
                     receipt_path: "uploads/...",
                     ocr_text: "extracted text",
                     expenses_preview: [...]
                   }
```

### 3. Confirmation and Save

```
Client → POST /receipts/confirm
           │
           ├─ 1. AUTHENTICATION
           │    └─ Validates JWT and extracts user_id
           │
           ├─ 2. SECURITY VALIDATION
           │    ├─ Verifies receipt_path exists
           │    ├─ Validates path is in uploads/
           │    ├─ Confirms path belongs to user_id
           │    └─ Error 403 if mismatch
           │
           ├─ 3. DATA VALIDATION
           │    ├─ For each expense:
           │    │   ├─ amount > 0
           │    │   ├─ currency = 3 chars uppercase
           │    │   ├─ description: 1-255 chars
           │    │   ├─ category: 1-50 chars
           │    │   └─ valid expense_date
           │    └─ Error 400 if validation fails
           │
           ├─ 4. PERSISTENCE
           │    ├─ Creates Expense records in DB
           │    ├─ Assigns: created_at, updated_at
           │    ├─ Links: user_id, receipt_path
           │    ├─ Attempts commit (3 retries)
           │    └─ Rollback on error
           │
           └─ 5. RESPONSE
                └─ Returns: {
                     receipt_path,
                     expenses_created: [...]
                   }
```

### 4. Expense Management

```
Client → GET /expenses/
           ├─ JWT authentication
           ├─ Filters by user_id automatically
           ├─ Excludes deleted_at != null
           └─ Returns expense list

Client → GET /expenses/{id}
           ├─ JWT authentication
           ├─ Verifies belongs to user
           └─ Returns expense or 404

Client → PATCH /expenses/{id}
           ├─ JWT authentication
           ├─ Validates sent fields
           ├─ Updates only present fields
           └─ Returns updated expense

Client → DELETE /expenses/{id}
           ├─ JWT authentication
           ├─ Soft-delete: marks deleted_at
           └─ Returns 204 No Content
```

---

## 📡 API Reference

### Health Check

#### `GET /health`
Verifies server is operational.

**Response:** `200 OK`
```json
{
  "status": "ok"
}
```

---

### Authentication (`/auth`)

#### `POST /auth/register`
Creates new user account.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securepass123"
}
```

**Response:** `201 Created`
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "created_at": "2026-02-03T20:00:00",
  "updated_at": "2026-02-03T20:00:00"
}
```

**Errors:**
- `409` - Email already registered
- `400` - Password contains spaces

---

#### `POST /auth/login`
Login and obtain JWT token.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securepass123"
}
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Errors:**
- `401` - Invalid email or password

---

### Receipts (`/receipts`)

#### `POST /receipts/process`
Processes receipt image with OCR and AI classification.

**Headers:**
- `Authorization: Bearer <token>`

**Request:** `multipart/form-data`
- `file`: JPG or PNG image (max 10MB)

**Response:** `201 Created`
```json
{
  "receipt_path": "uploads/550e8400.../receipt_abc123.jpg",
  "ocr_text": "SHAWARMA PITA\n4 Shawarma MIXTO 27.00\n...",
  "expenses_preview": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "user_id": "550e8400-e29b-41d4-a716-446655440000",
      "amount": 27.0,
      "currency": "CAD",
      "description": "Shawarma MIXTO",
      "category": "FOOD",
      "expense_date": "2026-02-03",
      "receipt_path": "uploads/.../receipt_abc123.jpg",
      "created_at": "2026-02-03T20:00:00",
      "updated_at": "2026-02-03T20:00:00",
      "deleted_at": null
    }
  ]
}
```

**Errors:**
- `400` - Invalid format or file too large
- `401` - Invalid token
- `503` - OPENAI_API_KEY not configured

---

#### `POST /receipts/confirm`
Saves processed expenses to database.

**Headers:**
- `Authorization: Bearer <token>`

**Request:**
```json
{
  "receipt_path": "uploads/550e8400.../receipt_abc123.jpg",
  "expenses": [
    {
      "amount": 27.0,
      "currency": "CAD",
      "description": "Shawarma MIXTO",
      "category": "FOOD",
      "expense_date": "2026-02-03"
    }
  ]
}
```

**Response:** `201 Created`
```json
{
  "receipt_path": "uploads/550e8400.../receipt_abc123.jpg",
  "expenses_created": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "user_id": "550e8400-e29b-41d4-a716-446655440000",
      "amount": 27.0,
      "currency": "CAD",
      "description": "Shawarma MIXTO",
      "category": "FOOD",
      "expense_date": "2026-02-03",
      "receipt_path": "uploads/.../receipt_abc123.jpg",
      "created_at": "2026-02-03T20:00:00",
      "updated_at": "2026-02-03T20:00:00",
      "deleted_at": null
    }
  ]
}
```

**Errors:**
- `400` - Validation failed (invalid amount, etc.)
- `403` - receipt_path doesn't belong to user
- `404` - File not found

---

### Expenses (`/expenses`)

#### `GET /expenses/`
Lists all expenses for authenticated user.

**Headers:**
- `Authorization: Bearer <token>`

**Response:** `200 OK`
```json
[
  {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "amount": 27.0,
    "currency": "CAD",
    "description": "Shawarma MIXTO",
    "category": "FOOD",
    "expense_date": "2026-02-03",
    "receipt_path": "uploads/.../receipt_abc123.jpg",
    "created_at": "2026-02-03T20:00:00",
    "updated_at": "2026-02-03T20:00:00",
    "deleted_at": null
  }
]
```

---

#### `GET /expenses/{expense_id}`
Gets a specific expense.

**Headers:**
- `Authorization: Bearer <token>`

**Response:** `200 OK` or `404 Not Found`

---

#### `PATCH /expenses/{expense_id}`
Partially updates an expense.

**Headers:**
- `Authorization: Bearer <token>`

**Request:**
```json
{
  "amount": 30.0,
  "description": "Updated description"
}
```

**Response:** `200 OK`

**Errors:**
- `400` - No fields to update
- `404` - Expense not found

---

#### `DELETE /expenses/{expense_id}`
Soft-deletes an expense (sets deleted_at).

**Headers:**
- `Authorization: Bearer <token>`

**Response:** `204 No Content`

**Errors:**
- `404` - Expense not found

---

## 🔐 Security

### JWT Authentication
- Tokens expire in 30 minutes
- Include `user_id` and `email` in payload
- Validation on every protected endpoint with `Depends(get_current_user)`

### Passwords
- Hashed with **bcrypt** (cost factor 12)
- Never stored in plain text
- Validation for forbidden spaces

### Files
- Only JPG/PNG allowed
- Maximum 10MB per file
- Path validation to prevent directory traversal
- Files organized by user: `uploads/{user_id}/`

### CORS
- Configured for development: `http://localhost:5173`
- Adjust for production in `app/main.py`

---

## 🗄️ Database

### User Model
```python
User:
  - id: UUID (PK)
  - email: String (unique, indexed)
  - hashed_password: String
  - created_at: DateTime
  - updated_at: DateTime
  - deleted_at: DateTime (nullable, soft-delete)
```

### Expense Model
```python
Expense:
  - id: UUID (PK)
  - user_id: UUID (FK → User)
  - amount: Float (> 0)
  - currency: String (3 chars, uppercase)
  - description: String (1-255 chars)
  - category: String (1-50 chars)
  - expense_date: Date
  - receipt_path: String (nullable)
  - created_at: DateTime
  - updated_at: DateTime
  - deleted_at: DateTime (nullable, soft-delete)
```

### Soft Delete
Records aren't physically deleted, only `deleted_at` is marked. This allows:
- Complete audit trail
- Data recovery
- Referential integrity

---

## 🛠️ Development

### Testing with Swagger UI
Access http://127.0.0.1:8000/docs and use the **"Authorize"** button:
1. Login via `/auth/login` to get token
2. Click "Authorize" and paste the token
3. Test all protected endpoints

### Debugging
Backend has logging enabled. For more details:
```python
# In backend/app/routers/receipts.py
print(f"DEBUG: {variable}")
```

### Available Categories
- `FOOD` - Food and restaurants
- `GROCERIES` - Supermarket
- `TRANSPORT` - Public transport, gas
- `ENTERTAINMENT` - Entertainment
- `HEALTH` - Health and pharmacy
- `UTILITIES` - Services (electricity, water, internet)
- `RENT` - Rent
- `OTHER` - Other expenses

### OCR Improvements
For better results:
- Photos with good lighting
- Legible and focused text
- Receipts without wrinkles or stains
- Minimum recommended resolution: 1000x1000px

### Switch to PostgreSQL
```python
# backend/.env
DATABASE_URL=postgresql://user:password@localhost/financedb

# Install driver (already in requirements.txt)
pip install psycopg2-binary
```

### Deploying to Render

This project includes a custom `build.sh` script to install system dependencies on Render.

**build.sh** installs:
- `tesseract-ocr` - OCR engine
- `tesseract-ocr-eng` - English language pack
- `tesseract-ocr-spa` - Spanish language pack
- All Python dependencies from `requirements.txt`

**Render Configuration:**
```bash
# Build Command (in Render Dashboard):
chmod +x build.sh && ./build.sh

# Start Command:
uvicorn app.main:app --host 0.0.0.0 --port $PORT

# Environment Variables required:
OPENAI_API_KEY=sk-your-key
SECRET_KEY=your-jwt-secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
TESSERACT_CMD=/usr/bin/tesseract
DATABASE_URL=postgresql://...supabase.com:6543/postgres
FRONTEND_URL=https://your-frontend.vercel.app
```

**Note:** `build.sh` uses `apt-get` to install system packages. This only works on Render's Ubuntu-based environment. For local development, install Tesseract manually as described in the Installation section above.

---

## 📝 Important Notes

- SQLite database is created automatically on startup
- Files in `uploads/` must be excluded from Git
- For production, generate new `SECRET_KEY` and `OPENAI_API_KEY`
- JWT tokens expire in 30 minutes (configurable in `.env`)
- Tesseract must be installed on the operating system

---

## 🤝 Contributing

1. Fork the project
2. Create a branch: `git checkout -b feature/new-feature`
3. Commit your changes: `git commit -m 'Add new feature'`
4. Push to branch: `git push origin feature/new-feature`
5. Open a Pull Request

---

## 📄 License

MIT

---

## 👤 Author

Built with ❤️ as a personal financial management project with AI.

