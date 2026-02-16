import os, asyncio, json, time
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import LabeledPrice, PreCheckoutQuery
from sqlalchemy import Column, BigInteger, Integer, String, DateTime, update, select, desc, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# --- НАСТРОЙКИ ---
TOKEN = "8377110375:AAG31LE62g88acAmbSkdxk_pyeMRmLtqwdM"
ADMIN_ID = 1292046104 
APP_URL = "https://my-tap-bot.onrender.com" 

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
    auto_power = Column(Integer, default=0) # Пассивный доход в секунду
    energy = Column(Integer, default=2500)
    max_energy = Column(Integer, default=2500)
    last_touch = Column(Integer, default=int(time.time())) # Для пассивного дохода
    last_bonus = Column(DateTime, default=datetime.utcnow() - timedelta(days=1))
    referrer_id = Column(BigInteger, nullable=True)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- АДМИНКА (РАССЫЛКА) ---
@dp.message(Command("send"))
async def broadcast(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID or not command.args: return
    async with async_session() as session:
        users = await session.execute(select(User.user_id))
        u_list = users.scalars().all()
    
    count = 0
    for uid in u_list:
        try:
            await bot.send_message(uid, command.args)
            count += 1
            await asyncio.sleep(0.05) # Защита от спам-фильтра ТГ
        except: continue
    await message.answer(f"✅ Рассылка завершена. Получили: {count} чел.")

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    async with async_session() as session:
        count = (await session.execute(select(func.count(User.user_id)))).scalar()
        text = f"📊 **Админ-панель**\n👤 Юзеров: {count}\n\n`/send текст` — рассылка"
    await message.answer(text, parse_mode="Markdown")

# --- ЛОГИКА ИГРЫ ---
@app.get("/u/{uid}")
async def get_user(uid: int):
    async with async_session() as session:
        user = await session.get(User, uid)
        if not user:
            user = User(user_id=uid, last_touch=int(time.time()))
            session.add(user); await session.commit(); await session.refresh(user)
        
        # Расчет пассивного дохода (оффлайн бонус)
        now = int(time.time())
        offline_seconds = now - user.last_touch
        passive_earned = offline_seconds * user.auto_power
        if passive_earned > 0:
            user.balance += passive_earned
            user.last_touch = now
            await session.commit()
            
        return {
            "score": user.balance, "mult": user.tap_power, "auto": user.auto_power, 
            "energy": user.energy, "max_energy": user.max_energy, "offline": passive_earned
        }

@app.post("/s")
async def save_user(request: Request):
    data = await request.json()
    uid = int(data['id'])
    async with async_session() as session:
        user = await session.get(User, uid)
        if user:
            # Базовая защита: проверяем, не пришло ли слишком много за раз
            diff = data['score'] - user.balance
            if diff > 50000: return {"status": "nice_try_hacker"} # Лимит на один пакет данных
            
            user.balance = data['score']
            user.tap_power = data['mult']
            user.auto_power = data['auto']
            user.energy = data['energy']
            user.last_touch = int(time.time())
            await session.commit()
    return {"status": "ok"}

@dp.message(Command("bonus"))
async def daily_bonus(message: types.Message):
    async with async_session() as session:
        user = await session.get(User, message.from_user.id)
        if user:
            now = datetime.utcnow()
            if now - user.last_bonus > timedelta(days=1):
                user.balance += 5000
                user.last_bonus = now
                await session.commit()
                await message.answer("🎁 Ежедневный бонус +5000 монет зачислен!")
            else:
                await message.answer("⏳ Бонус можно взять раз в 24 часа.")

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
                    ref_parent = await session.get(User, ref_id)
                    if ref_parent: ref_parent.balance += 2500; user.balance += 2500
            session.add(user); await session.commit()
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔥 ИГРАТЬ", web_app=types.WebAppInfo(url=APP_URL))
    kb.button(text="🎁 БОНУС", callback_data="daily") # Можно вызвать через команду /bonus
    await message.answer("FenixTap: Тапай, копи пассив и забирай бонусы!", reply_markup=kb.as_markup())

# --- ТЕХНИЧЕСКАЯ ЧАСТЬ ---
async def energy_recovery():
    while True:
        await asyncio.sleep(60)
        async with async_session() as session:
            await session.execute(update(User).where(User.energy < User.max_energy).values(energy=User.energy + 10))
            await session.commit()

@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(dp.start_polling(bot, skip_updates=True))
    asyncio.create_task(energy_recovery())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
