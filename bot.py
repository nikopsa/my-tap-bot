import os
import asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from urllib.parse import urlparse

# Твой токен (Помни: @BotFather -> /revoke для безопасности!)
BOT_TOKEN = "8377110375:AAG3GmbEpQGyIcfzyOByu6qPUPVbxhYpPSg"

# 1. ПОЛУЧАЕМ И ИСПРАВЛЯЕМ URL БАЗЫ
raw_db_url = os.getenv("DATABASE_URL")

def get_valid_url(url: str) -> str:
    if not url:
        # Если переменная пустая, используем заглушку, чтобы не было ошибки парсинга при запуске
        return "postgresql+asyncpg://user:pass@localhost/db"
    
    # Render часто дает postgres://, меняем на postgresql+asyncpg://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    return url

DATABASE_URL = get_valid_url(raw_db_url)

# 2. СОЗДАЕМ ДВИЖОК (со всеми фиксами)
engine = create_async_engine(
    DATABASE_URL, 
    pool_pre_ping=True,
    echo=False  # Поставь True, если хочешь видеть SQL-запросы в логах
)

async_session = sessionmaker(
    engine, 
    expire_on_commit=False, 
    class_=AsyncSession
)

# 3. ИНИЦИАЛИЗАЦИЯ ПРИЛОЖЕНИЯ
app = FastAPI()

@app.get("/")
async def status():
    return {"status": "ok", "bot_id": "8377110375"}

# Твоя логика бота (aiogram или другая
