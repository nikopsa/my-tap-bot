import os, asyncio, time
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

TOKEN = "8377110375:AAG31LE62g88acAmbSkdxk_pyeMRmLtqwdM"
APP_URL = "https://my-tap-bot.onrender.com" 

# НАСТРОЙКА КАНАЛОВ (Бот должен быть админом в обоих!)
CHANNEL_ID = "@твой_канал" 
REKLAMA_CHANNEL_ID = "@рекламный_канал" 

WEBHOOK_PATH = f"/webhook/{TOKEN}"

DB_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///db.sqlite3")
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DB_URL, pool_pre_ping=True)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    user_id = Column(BigInteger, primary_key=True)
    username = Column(String)
    balance = Column(BigInteger, default=1000)
    tap_power = Column(Integer, default=1)
    auto_power = Column(Integer, default=0)
    energy = Column(Integer, default=2500)
    max_energy = Column(Integer, default=2500)
    last_bonus = Column(Integer, default=0)
    task_sub = Column(Integer, default=0)      # Основной канал
    task_reklama = Column(Integer, default=0)  # Рекламный канал

bot = Bot(token=TOKEN)
dp = Dispatcher()

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # await conn.execute(text("UPDATE users SET auto_power = 0")) # Решетка стоит
        await conn.commit()
    await bot.set_webhook(url=f"{APP_URL}{WEBHOOK_PATH}", drop_pending_updates=True)
    yield
    await engine.dispose()

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("index.html", "r", encoding="utf-8") as f: return f.read()

@app.get("/get_user")
async def get_user(id: int):
    async with async_session() as session:
        user = await session.get(User, id)
        if not user:
            user = User(user_id=id, username=f"User_{str(id)[-4:]}")
            session.add(user)
            await session.commit()
            await session.refresh(user)
        return {"score": user.balance, "auto": user.auto_power, "energy": user.energy, "max_energy": user.max_energy}

@app.post("/s")
async def save(request: Request):
    d = await request.json()
    async with async_session() as session:
        user = await session.get(User, int(d['id']))
        if user:
            user.balance, user.energy = int(d['score']), int(d['energy'])
            await session.commit()
    return {"ok": True}

# Проверка основного канала
@app.post("/check_sub")
async def check_sub(request: Request):
    d = await request.json()
    uid = int(d['id'])
    try:
        chat_member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=uid)
        if chat_member.status in ["member", "administrator", "creator"]:
            async with async_session() as session:
                user = await session.get(User, uid)
                if user and user.task_sub == 0:
                    user.balance += 50000
                    user.task_sub = 1
                    await session.commit()
                    return {"ok": True, "message": "Подписка подтверждена! +50,000 монет"}
        return {"ok": False, "message": "Вы не подписаны или уже получили награду"}
    except: return {"ok": False, "message": "Ошибка проверки подписки"}

# Проверка рекламного канала
@app.post("/check_reklama")
async def check_reklama(request: Request):
    d = await request.json()
    uid = int(d['id'])
    try:
        chat_member = await bot.get_chat_member(chat_id=REKLAMA_CHANNEL_ID, user_id=uid)
        if chat_member.status in ["member", "administrator", "creator"]:
            async with async_session() as session:
                user = await session.get(User, uid)
                if user and user.task_reklama == 0:
                    user.balance += 70000
                    user.task_reklama = 1
                    await session.commit()
                    return {"ok": True, "message": "Рекламный бонус получен! +70,000 монет"}
        return {"ok": False, "message": "Подпишитесь на рекламный канал!"}
    except: return {"ok": False, "message": "Ошибка рекламного канала"}

@app.get("/get_top")
async def get_top():
    async with async_session() as session:
        res = await session.execute(select(User).order_by(desc(User.balance)).limit(10))
        users = res.scalars().all()
        return [{"username": u.username or f"ID{str(u.user_id)[-4:]}", "balance": u.balance} for u in users]

@app.post("/claim_bonus")
async def claim_bonus(request: Request):
    d = await request.json()
    now = int(time.time())
    async with async_session() as session:
        user = await session.get(User, int(d['id']))
        if user and (now - user.last_bonus >= 86400):
            user.last_bonus = now
            user.balance += 10000
            await session.commit()
            return {"ok": True, "message": "🎁 +10,000 монет!"}
    return {"ok": False, "message": "Раз в 24 часа"}

@app.post("/create_invoice")
async def create_invoice(request: Request):
    d = await request.json()
    p = {"pack_light": ["⚡ Start (+8/s)", 100], "pack_ext": ["🔥 Pro (+25/s)", 300]}.get(d['type'])
    link = await bot.create_invoice_link(title=p[0], description="Boost", payload=f"buy_{d['type']}_{d['id']}", provider_token="", currency="XTR", prices=[LabeledPrice(label=p[0], amount=p[1])])
    return {"link": link}

@app.post(WEBHOOK_PATH)
async def wh(r: Request):
    await dp.feed_update(bot, Update.model_validate(await r.json(), context={"bot": bot}))
    return Response(content="ok")

@dp.pre_checkout_query()
async def pcq(q: PreCheckoutQuery): await q.answer(ok=True)

@dp.message(F.successful_payment)
async def on_pay(m: types.Message):
    data = m.successful_payment.invoice_payload.split('_')
    async with async_session() as session:
        user = await session.get(User, int(data[2]))
        if user:
            user.auto_power += 8 if data[1] == "pack_light" else 25
            await session.commit()

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer("🔥 Играй в Fenix Tap!", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="💸 ИГРАТЬ", web_app=types.WebAppInfo(url=APP_URL))]]))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
