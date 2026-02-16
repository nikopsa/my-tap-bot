import os, asyncio, json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
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
APP_URL = "https://your-app-name.onrender.com" # ЗАМЕНИ ПОСЛЕ ДЕПЛОЯ
REF_REWARD = 2500

DB_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///db.sqlite3").strip().replace("postgres://", "postgresql+asyncpg://")
engine = create_async_engine(DB_URL)
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

class UserTask(Base):
    __tablename__ = 'user_tasks'
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.user_id'))
    task_id = Column(String)

app = FastAPI()
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- API ДЛЯ ИГРЫ ---
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    with open("index.html", "r", encoding="utf-8") as f: return f.read()

@app.get("/u/{uid}")
async def get_user(uid: int):
    async with async_session() as session:
        user = await session.get(User, uid)
        if not user:
            user = User(user_id=uid); session.add(user); await session.commit()
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

@app.get("/create_invoice/{uid}/{item}")
async def create_invoice(uid: int, item: str):
    prices = {"mult": 50, "energy": 100}
    amount = prices.get(item, 50)
    title = "Сила клика +1" if item == "mult" else "Бак +500"
    link = await bot.create_invoice_link(title=title, description="Покупка за Звезды", payload=f"{uid}_{item}", provider_token="", currency="XTR", prices=[LabeledPrice(label=title, amount=amount)])
    return {"link": link}

# --- ЛОГИКА ТЕЛЕГРАМ ---
@dp.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery): await query.answer(ok=True)

@dp.message(F.successful_payment)
async def on_success_pay(message: types.Message):
    uid_item = message.successful_payment.invoice_payload.split("_")
    uid, item = int(uid_item[0]), uid_item[1]
    async with async_session() as session:
        user = await session.get(User, uid)
        if item == "mult": user.tap_power += 1
        else: user.max_energy += 500; user.energy = user.max_energy
        await session.commit()
    await message.answer("✅ Звезды приняты! Улучшение активировано.")

@dp.message(Command("set_balance"))
async def set_bal(message: types.Message, command: CommandObject):
    if message.from_user.id == ADMIN_ID:
        async with async_session() as session:
            await session.execute(update(User).where(User.user_id == ADMIN_ID).values(balance=int(command.args)))
            await session.commit()
        await message.answer("💰 Баланс изменен!")

@dp.message(Command("start"))
async def start(message: types.Message, command: CommandObject):
    async with async_session() as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            user = User(user_id=message.from_user.id, username=message.from_user.first_name)
            if command.args and command.args.isdigit():
                ref_id = int(command.args)
                if ref_id != message.from_user.id:
                    user.referrer_id = ref_id
                    ref_user = await session.get(User, ref_id)
                    if ref_user: ref_user.balance += REF_REWARD; user.balance += REF_REWARD
            session.add(user); await session.commit()
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
    async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(dp.start_polling(bot))
    asyncio.create_task(energy_recovery())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
