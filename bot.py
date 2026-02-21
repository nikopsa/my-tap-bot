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
ADMIN_ID = 1292046104 
APP_URL = "https://my-tap-bot.onrender.com" 
WEBHOOK_PATH = f"/webhook/{TOKEN}"

# КОРРЕКТИВА: Обработка URL базы данных для Render/PostgreSQL
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
# КОРРЕКТИВА: Убедимся, что CORS полностью открыт для фронтенда
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
bot = Bot(token=TOKEN)
dp = Dispatcher()

@app.post(WEBHOOK_PATH)
async def bot_webhook(request: Request):
    try:
        data = await request.json()
        update_obj = Update.model_validate(data, context={"bot": bot})
        await dp.feed_update(bot, update_obj) # КОРРЕКТИВА: Убрали лишний task для стабильности на Render
        return Response(content='ok', status_code=200)
    except Exception as e:
        logger.error(f"Error in webhook: {e}")
        return Response(content='error', status_code=500)

@app.get("/", response_class=HTMLResponse)
@app.head("/")
async def serve_index(request: Request):
    if request.method == "HEAD": return Response(status_code=200)
    file_path = os.path.join(os.getcwd(), "index.html")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f: return f.read()
    return "<h1>index.html не найден.</h1>"

@app.get("/get_user")
async def get_user(id: int):
    async with async_session() as session:
        user = await session.get(User, id)
        if not user:
            user = User(user_id=id, last_touch=int(time.time()), balance=500)
            session.add(user)
            await session.commit()
            await session.refresh(user)
        
        now = int(time.time())
        # Логика авто-майнинга при входе
        if user.auto_power > 0:
            off = (now - user.last_touch) * user.auto_power
            user.balance += off
        
        user.last_touch = now
        await session.commit()
        return {"score": user.balance, "mult": user.tap_power, "auto": user.auto_power, "energy": user.energy, "max_energy": user.max_energy}

@app.post("/s")
async def save_user(request: Request):
    try:
        data = await request.json()
        uid = int(data.get('id'))
        async with async_session() as session:
            user = await session.get(User, uid)
            if user:
                user.balance = int(data.get('score', user.balance))
                user.tap_power = int(data.get('mult', user.tap_power))
                user.auto_power = int(data.get('auto', user.auto_power))
                user.energy = int(data.get('energy', user.energy))
                user.last_touch = int(time.time())
                await session.commit()
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Save error: {e}")
        return {"status": "error"}

@app.get("/top")
async def get_top():
    async with async_session() as session:
        res = await session.execute(select(User).order_by(User.balance.desc()).limit(10))
        users = res.scalars().all()
        return [{"n": u.username or f"ID{u.user_id}", "s": u.balance} for u in users]

@dp.message(Command("start"))
async def start(m: types.Message, command: CommandObject):
    ref_id = None
    if command.args and command.args.isdigit():
        ref_id = int(command.args)
        
    async with async_session() as session:
        user = await session.get(User, m.from_user.id)
        if not user:
            user = User(
                user_id=m.from_user.id, 
                username=m.from_user.username or m.from_user.first_name, 
                referrer_id=ref_id, 
                last_touch=int(time.time())
            )
            session.add(user)
            if ref_id and ref_id != m.from_user.id:
                referrer = await session.get(User, ref_id)
                if referrer: referrer.balance += 2500
            await session.commit()
    
    kb = InlineKeyboardBuilder().button(text="🔥 ИГРАТЬ", web_app=types.WebAppInfo(url=APP_URL))
    await m.answer(f"Здарова, {m.from_user.first_name}! Заходи в игру.", reply_markup=kb.as_markup())

async def recovery():
    while True:
        await asyncio.sleep(60)
        try:
            async with async_session() as session:
                # КОРРЕКТИВА: Более безопасный апдейт энергии
                await session.execute(
                    update(User)
                    .where(User.energy < User.max_energy)
                    .values(energy=func.least(User.max_energy, User.energy + 20))
                )
                await session.commit()
        except Exception as e:
            logger.error(f"Recovery error: {e}")

@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Установка вебхука
    webhook_url = f"{APP_URL}{WEBHOOK_PATH}"
    await bot.set_webhook(url=webhook_url, drop_pending_updates=True)
    asyncio.create_task(recovery())
    logger.info(f"Webhook set to {webhook_url}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
