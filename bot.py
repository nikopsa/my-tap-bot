import os, asyncio, json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import LabeledPrice, PreCheckoutQuery
from sqlalchemy import Column, BigInteger, Integer, String, update, ForeignKey, select, desc
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# --- НАСТРОЙКИ ---
TOKEN = "8377110375:AAGHQZZi-AP4cWMT_CsvsdO93fMcSaZz_jw"
ADMIN_ID = 1292046104 
APP_URL = "https://my-tap-bot.onrender.com" 
REF_REWARD = 2500
AD_REWARD = 5000 

# Исправление ссылки БД для Render PostgreSQL
DB_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///db.sqlite3").strip().replace("postgres://", "postgresql+asyncpg://")
engine = create_async_engine(DB_URL, pool_pre_ping=True)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    user_id = Column(BigInteger, primary_key=True)
    username = Column(String)
    balance = Column(Integer, default=500)
    tap_power = Column(Integer, default=1)
    auto_power = Column(Integer, default=0)
    energy = Column(Integer, default=2500)
    max_energy = Column(Integer, default=2500)
    referrer_id = Column(BigInteger, nullable=True)

app = FastAPI()

# CORS для связи игры и сервера без ошибок "Загрузка"
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bot = Bot(token=TOKEN)
dp = Dispatcher()

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    base_path = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_path, "index.html")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            # Автоматическая замена путей для стабильной работы
            return content.replace("fetch('/", f"fetch('{APP_URL}/").replace("fetch('u/", f"fetch('{APP_URL}/u/")
    return "<h1>Ошибка: index.html не найден</h1>"

@app.get("/u/{uid}")
async def get_user(uid: int):
    async with async_session() as session:
        user = await session.get(User, uid)
        if not user:
            user = User(user_id=uid); session.add(user); await session.commit(); await session.refresh(user)
        return {"score": user.balance, "mult": user.tap_power, "auto": user.auto_power, "energy": user.energy, "max_energy": user.max_energy}

@app.post("/s")
async def save_user(request: Request):
    data = await request.json()
    async with async_session() as session:
        await session.execute(update(User).where(User.user_id == int(data['id'])).values(
            balance=data['score'], tap_power=data['mult'], auto_power=data['auto'], 
            energy=data['energy'], max_energy=data.get('max_energy', 2500)))
        await session.commit()
    return {"status": "ok"}

@app.post("/reward_ad")
async def reward_ad(request: Request):
    data = await request.json()
    uid = int(data['id'])
    async with async_session() as session:
        user = await session.get(User, uid)
        if user:
            user.balance += AD_REWARD; await session.commit()
            return {"status": "ok", "new_balance": user.balance}
    return {"status": "error"}

# ОПЛАТА ЗВЕЗДАМИ: 5000 ЭНЕРГИИ ЗА 100 ЗВЕЗД
@app.get("/create_invoice/{uid}/{item}")
async def create_invoice(uid: int, item: str):
    prices = {"mult": 50, "energy": 100} # 100 звезд за 5000 энергии
    amount = prices.get(item, 50)
    title = "Сила клика +1" if item == "mult" else "Мега-бак +5000"
    link = await bot.create_invoice_link(
        title=title, 
        description="Покупка за Звезды", 
        payload=f"{uid}_{item}", 
        provider_token="", 
        currency="XTR", 
        prices=[LabeledPrice(label=title, amount=amount)]
    )
    return {"link": link}

@dp.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery): await query.answer(ok=True)

@dp.message(F.successful_payment)
async def on_success_pay(message: types.Message):
    uid_item = message.successful_payment.invoice_payload.split("_")
    uid, item = int(uid_item[0]), uid_item[1]
    async with async_session() as session:
        user = await session.get(User, uid)
        if item == "mult": 
            user.tap_power += 1
        else: 
            user.max_energy += 5000; user.energy = user.max_energy # ДОБАВЛЕНО +5000
        await session.commit()
    await message.answer("✅ Улучшение на 5000 энергии активировано!")

@dp.message(Command("start"))
async def start(message: types.Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="🔥 ИГРАТЬ", web_app=types.WebAppInfo(url=APP_URL))
    await message.answer("FenixTap: Тапай и зарабатывай!", reply_markup=kb.as_markup())

async def energy_recovery():
    while True:
        await asyncio.sleep(60)
        async with async_session() as session:
            await session.execute(update(User).where(User.energy < User.max_energy).values(energy=User.energy + 1))
            await session.commit()

@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(dp.start_polling(bot))
    asyncio.create_task(energy_recovery())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
