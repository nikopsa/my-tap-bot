import os, asyncio, json, time, logging
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import LabeledPrice, PreCheckoutQuery, Update
from sqlalchemy import Column, BigInteger, Integer, String, DateTime, update, select, desc, func, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- НАСТРОЙКИ ---
TOKEN = "8377110375:AAG31LE62g88acAmbSkdxk_pyeMRmLtqwdM"
APP_URL = "https://my-tap-bot.onrender.com" 
WEBHOOK_PATH = f"/webhook/{TOKEN}"

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
    last_touch = Column(Integer, default=int(time.time()))
    level = Column(Integer, default=1)
    streak = Column(Integer, default=0)
    last_checkin = Column(DateTime, default=datetime.utcnow() - timedelta(days=1))
    referrer_id = Column(BigInteger, nullable=True)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
bot = Bot(token=TOKEN)
dp = Dispatcher()

@app.post(WEBHOOK_PATH)
async def bot_webhook(request: Request):
    try:
        data = await request.json()
        upd = Update.model_validate(data, context={"bot": bot})
        asyncio.create_task(dp.feed_update(bot, upd))
        return Response(content='ok', status_code=200)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return Response(content='error', status_code=500)

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    file_path = os.path.join(os.getcwd(), "index.html")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f: return f.read()
    return "<h1>index.html not found</h1>"

@app.get("/get_user")
async def get_user(id: int):
    async with async_session() as session:
        user = await session.get(User, id)
        if not user:
            user = User(user_id=id, last_touch=int(time.time()))
            session.add(user); await session.commit(); await session.refresh(user)
        
        now = int(time.time())
        last_t = user.last_touch or now
        off = (now - last_t) * (user.auto_power or 0)
        user.balance += off
        user.last_touch = now
        await session.commit()
        return {"score": user.balance, "mult": user.tap_power, "auto": user.auto_power, "energy": user.energy, "max_energy": user.max_energy}

@app.post("/s")
async def save_user(request: Request):
    data = await request.json()
    async with async_session() as session:
        user = await session.get(User, int(data.get('id')))
        if user:
            user.balance = int(data.get('score', user.balance))
            user.energy = int(data.get('energy', user.energy))
            user.last_touch = int(time.time())
            await session.commit()
    return {"status": "ok"}

@app.get("/top")
async def get_top():
    async with async_session() as session:
        res = await session.execute(select(User).order_by(User.balance.desc()).limit(10))
        return [{"n": u.username or f"ID{u.user_id}", "s": u.balance} for u in res.scalars().all()]

@dp.message(Command("start"))
async def start(m: types.Message, command: CommandObject):
    ref_id = int(command.args) if command.args and command.args.isdigit() else None
    async with async_session() as session:
        user = await session.get(User, m.from_user.id)
        if not user:
            user = User(user_id=m.from_user.id, username=m.from_user.username, referrer_id=ref_id)
            session.add(user)
            if ref_id:
                ref = await session.get(User, ref_id)
                if ref: ref.balance += 2500
            await session.commit()
    
    kb = InlineKeyboardBuilder().button(text="🔥 ИГРАТЬ", web_app=types.WebAppInfo(url=APP_URL))
    await m.answer("Здарова! Заходи в игру.", reply_markup=kb.as_markup())

async def recovery():
    while True:
        await asyncio.sleep(60)
        try:
            async with async_session() as session:
                await session.execute(update(User).where(User.energy < User.max_energy).values(energy=User.energy + 20))
                await session.commit()
        except: pass

@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Добавляем недостающие колонки по одной (если их нет)
        cols = [
            ("last_touch", "INTEGER DEFAULT 0"),
            ("level", "INTEGER DEFAULT 1"),
            ("streak", "INTEGER DEFAULT 0"),
            ("last_checkin", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("referrer_id", "BIGINT")
        ]
        for name, type_sql in cols:
            try: await conn.execute(text(f"ALTER TABLE users ADD COLUMN {name} {type_sql}"))
            except: pass 

    await bot.set_webhook(url=f"{APP_URL}{WEBHOOK_PATH}", drop_pending_updates=True)
    asyncio.create_task(recovery())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
