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

# Логирование для отлова косяков
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- КОНФИГ (ЗАМЕНИ APP_URL НА СВОЙ!) ---
TOKEN = "8377110375:AAG31LE62g88acAmbSkdxk_pyeMRmLtqwdM"
APP_URL = "https://my-tap-bot.onrender.com" 
WEBHOOK_PATH = f"/webhook/{TOKEN}"

# Настройка БД (SQLite или Postgres)
DB_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///db.sqlite3")
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DB_URL, pool_pre_ping=True)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()

# Модель юзера со ВСЕМИ колонками
class User(Base):
    __tablename__ = 'users'
    user_id = Column(BigInteger, primary_key=True)
    username = Column(String)
    balance = Column(Integer, default=1000)
    tap_power = Column(Integer, default=1)
    auto_power = Column(Integer, default=0)
    energy = Column(Integer, default=2500)
    max_energy = Column(Integer, default=2500)
    last_save = Column(Integer, default=int(time.time()))
    last_bonus = Column(Integer, default=0)
    referrer_id = Column(BigInteger, nullable=True)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- СИСТЕМА АВТО-ИСПРАВЛЕНИЯ БАЗЫ ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Бот заводится...")
    try:
        async with engine.begin() as conn:
            # Создаем таблицы если их нет
            await conn.run_sync(Base.metadata.create_all)
            
            # Насильно добавляем колонки, которых не хватает (исправляем твою ошибку из лога)
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
                    pass # Если уже есть - игнорим
                    
        await bot.set_webhook(url=f"{APP_URL}{WEBHOOK_PATH}", drop_pending_updates=True)
        asyncio.create_task(keep_alive())
        logger.info("Вебхук установлен!")
    except Exception as e:
        logger.error(f"Ошибка при старте: {e}")
    yield
    await bot.delete_webhook()

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

async def keep_alive():
    async with httpx.AsyncClient() as client:
        while True:
            await asyncio.sleep(600)
            try: await client.get(APP_URL)
            except: pass

@app.get("/", response_class=HTMLResponse)
async def index():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "Ошибка: index.html не найден в корне проекта!"

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
        res = await session.execute(select(User).order_by(desc(User.balance)).limit(10))
        return [{"username": u.username or f"Fen_{str(u.user_id)[-4:]}", "balance": u.balance} for u in res.scalars().all()]

@app.post("/s")
async def save(request: Request):
    d = await request.json()
    now = int(time.time())
    async with async_session() as session:
        user = await session.get(User, int(d['id']))
        if user:
            # Простая защита от накрутки
            elapsed = max(now - user.last_save, 1)
            limit = ((user.tap_power * 30) + user.auto_power) * elapsed + 1000
            diff = int(d['score']) - user.balance
            if 0 <= diff <= limit:
                user.balance = int(d['score'])
                user.energy = int(d['energy'])
                user.last_save = now
                await session.commit()
    return {"ok": True}

@app.post("/create_invoice")
async def create_invoice(request: Request):
    d = await request.json()
    prices = {
        "pack_mult": ["🚀 Мультитапер x5", 250], 
        "pack_energy": ["⚡ Энерго-Монстр", 150], 
        "pack_5m": ["💰 5M Монет", 999]
    }
    item = prices.get(d['type'])
    link = await bot.create_invoice_link(
        title=item[0], description="Донат", payload=f"buy_{d['type']}_{d['id']}", 
        provider_token="", currency="XTR", prices=[LabeledPrice(label=item[0], amount=item[1])]
    )
    return {"link": link}

@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)

@dp.message(F.successful_payment)
async def on_pay(m: types.Message):
    data = m.successful_payment.invoice_payload.split('_')
    async with async_session() as session:
        user = await session.get(User, int(data[2]))
        if user:
            if data[1] == "pack_mult": user.tap_power += 5
            elif data[1] == "pack_energy": user.max_energy, user.energy = 10000, 10000
            elif data[1] == "pack_5m": user.balance += 5000000
            await session.commit()

@app.post(WEBHOOK_PATH)
async def webhook(request: Request):
    data = await request.json()
    await dp.feed_update(bot, Update.model_validate(data, context={"bot": bot}))
    return Response(content='ok')

@dp.message(Command("start"))
async def start(m: types.Message):
    now = int(time.time())
    async with async_session() as session:
        user = await session.get(User, m.from_user.id)
        if not user:
            # Рефералка
            ref_id = int(m.text.split()[1]) if len(m.text.split()) > 1 and m.text.split()[1].isdigit() else None
            if ref_id:
                ref = await session.get(User, ref_id)
                if ref: ref.balance += 10000
            user = User(user_id=m.from_user.id, username=m.from_user.username, balance=1000, last_save=now, last_bonus=now)
            session.add(user)
        else:
            # Бонус раз в сутки
            if now - user.last_bonus > 86400:
                user.balance += 25000
                user.last_bonus = now
        await session.commit()
    
    await m.answer(
        "🔥 Феникс обновлен! База данных исправлена.\nНажми кнопку ниже, чтобы начать.",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="💸 ИГРАТЬ", web_app=types.WebAppInfo(url=APP_URL))]
        ])
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
