from dotenv import load_dotenv
from pydantic import BaseModel
import os

# Carga el .env automáticamente
load_dotenv()


class Settings(BaseModel):
    environment: str = os.getenv("ENVIRONMENT", "development")
    database_url: str = os.getenv("DATABASE_URL")
    jwt_secret: str = os.getenv("JWT_SECRET")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM")


# Instancia global de settings
settings = Settings()
