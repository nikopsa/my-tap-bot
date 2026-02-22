import os, asyncio, time, httpx, logging
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery, Update
from sqlalchemy import Column, BigInteger, Integer, String, select, desc, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- КОНФИГ ---
TOKEN = "8377110375:AAG31LE62g88acAmbSkdxk_pyeMRmLtqwdM"
APP_URL = "https://my-tap-bot.onrender.com" 
WEBHOOK_PATH = f"/webhook/{TOKEN}"

DB_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///db.sqlite3")
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql+asyncpg://", 1)

# Оптимизация пула соединений
engine = create_async_engine(DB_URL, pool_pre_ping=True, future=True)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    user_id = Column(BigInteger, primary_key=True)
    username = Column(String)
    balance = Column(Integer, default=1000)
    tap_power = Column(Integer, default=1)
    auto_power = Column(Integer, default=0)
    energy = Column(Integer, default=2500)
    max_energy = Column(Integer, default=2500)
    last_save = Column(Integer, default=lambda: int(time.time()))
    last_bonus = Column(Integer, default=0)
    referrer_id = Column(BigInteger, nullable=True)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- СИСТЕМА АВТО-ИСПРАВЛЕНИЯ БАЗЫ ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Бот запускается...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Проверка и добавление колонок
        cols = [
            ("last_save", "INTEGER DEFAULT 0"),
            ("last_bonus", "INTEGER DEFAULT 0"),
            ("referrer_id", "BIGINT")
        ]
        for col_name, col_type in cols:
            try:
                await conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))
                logger.info(f"Колонка {col_name} добавлена!")
            except Exception:
                pass
                
    # Установка вебхука
    webhook_url = f"{APP_URL}{WEBHOOK_PATH}"
    await bot.set_webhook(url=webhook_url, drop_pending_updates=True)
    logger.info(f"Вебхук установлен на {webhook_url}")
    
    asyncio.create_task(keep_alive())
    yield
    await bot.delete_webhook()
    await engine.dispose()

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

async def keep_alive():
    async with httpx.AsyncClient() as client:
        while True:
            await asyncio.sleep(600)
            try: await client.get(APP_URL)
            except: pass

# --- ЭНДПОИНТЫ API ---

@app.get("/", response_class=HTMLResponse)
async def index():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Bot is running!</h1>"

@app.post(WEBHOOK_PATH)
async def webhook(request: Request):
    try:
        update_data = await request.json()
        update = Update.model_validate(update_data, context={"bot": bot})
        await dp.feed_update(bot, update)
        return Response(status_code=200)
    except Exception as e:
        logger.error(f"Ошибка в вебхуке: {e}")
        return Response(status_code=500)

@app.get("/get_user")
async def get_user(id: int):
    async with async_session() as session:
        user = await session.get(User, id)
        if not user:
            user = User(user_id=id, last_save=int(time.time()), last_bonus=int(time.time()))
            session.add(user)
            await session.commit()
            await session.refresh(user)
        return {
            "score": user.balance, 
            "mult": user.tap_power, 
            "auto": user.auto_power, 
            "energy": user.energy, 
            "max_energy": user.max_energy
        }

@app.get("/get_top")
async def get_top():
    async with async_session() as session:
        result = await session.execute(select(User).order_by(desc(User.balance)).limit(10))
        users = result.scalars().all()
        return [{"username": u.username or f"Fen_{str(u.user_id)[-4:]}", "balance": u.balance} for u in users]

@app.post("/s")
async def save(request: Request):
    d = await request.json()
    now = int(time.time())
    async with async_session() as session:
        user = await session.get(User, int(d['id']))
        if user:
            elapsed = max(now - (user.last_save or now), 1)
            limit = ((user.tap_power * 30) + user.auto_power) * elapsed + 1000
            diff = int(d['score']) - user.balance
            if 0 <= diff <= limit:
                user.balance = int(d['score'])
                user.energy = int(d['energy'])
                user.last_save = now
                await session.commit()
    return {"ok": True}

# --- ОБРАБОТЧИКИ ТЕЛЕГРАМ ---

@dp.message(Command("start"))
async def start(m: types.Message):
    now = int(time.time())
    async with async_session() as session:
        user = await session.get(User, m.from_user.id)
        if not user:
            # Рефералка
            args = m.text.split()
            ref_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
            if ref_id and ref_id != m.from_user.id:
                ref = await session.get(User, ref_id)
                if ref: 
                    ref.balance += 10000
            
            user = User(user_id=m.from_user.id, username=m.from_user.username, balance=1000, last_save=now, last_bonus=now)
            session.add(user)
        else:
            if now - (user.last_bonus or 0) > 86400:
                user.balance += 25000
                user.last_bonus = now
        await session.commit()
    
    await m.answer(
        "🔥 Феникс готов к работе!\nНажми кнопку ниже, чтобы войти в игру.",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="💸 ИГРАТЬ", web_app=types.WebAppInfo(url=APP_URL))]
        ])
    )

@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)

@dp.message(F.successful_payment)
async def on_pay(m: types.Message):
    data = m.successful_payment.invoice_payload.split('_')
    async with async_session() as session:
        user = await session.get(User, int(data[2]))
        if user:
            p_type = data[1]
            if p_type == "pack_mult": user.tap_power += 5
            elif p_type == "pack_energy": 
                user.max_energy = 10000
                user.energy = 10000
            elif p_type == "pack_5m": user.balance += 5000000
            await session.commit()

# --- ЗАПУСК ---
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
