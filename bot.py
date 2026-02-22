import os, asyncio, time
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandObject
from aiogram.types import LabeledPrice, PreCheckoutQuery, Update
from sqlalchemy import Column, BigInteger, Integer, String, select, desc, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

TOKEN = "8377110375:AAG31LE62g88acAmbSkdxk_pyeMRmLtqwdM"
APP_URL = "https://my-tap-bot.onrender.com" 

# НАСТРОЙКА КАНАЛОВ
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
    task_sub = Column(Integer, default=0)
    task_reklama = Column(Integer, default=0)
    referrer_id = Column(BigInteger, nullable=True) # Кто пригласил

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Функция для авто-постинга ТОПа в канал
async def auto_leaderboard():
    while True:
        await asyncio.sleep(3600) # Раз в час
        async with async_session() as session:
            res = await session.execute(select(User).order_by(desc(User.balance)).limit(5))
            users = res.scalars().all()
            text = "🏆 **ТОП ЛИДЕРОВ ЧАСА** 🏆\n\n"
            for i, u in enumerate(users):
                name = u.username or f"Игрок {str(u.user_id)[-4:]}"
                text += f"{i+1}. {name} — {u.balance:,} 💰\n"
            text += f"\n🚀 Играй и побеждай: {APP_URL}"
            try:
                await bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="Markdown")
            except: pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await bot.set_webhook(url=f"{APP_URL}{WEBHOOK_PATH}", drop_pending_updates=True)
    asyncio.create_task(auto_leaderboard()) # Запуск рассылки ТОПа
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

@app.post("/check_sub")
async def check_sub(request: Request):
    d = await request.json()
    uid = int(d['id'])
    try:
        m = await bot.get_chat_member(CHANNEL_ID, uid)
        if m.status in ["member", "administrator", "creator"]:
            async with async_session() as session:
                u = await session.get(User, uid)
                if u and u.task_sub == 0:
                    u.balance += 100000 # Увеличил до 100к для мотивации
                    u.task_sub = 1
                    await session.commit()
                    return {"ok": True, "message": "Успешно! +100,000 монет"}
    except: pass
    return {"ok": False, "message": "Подпишитесь на канал!"}

@app.post("/check_reklama")
async def check_reklama(request: Request):
    d = await request.json()
    uid = int(d['id'])
    try:
        m = await bot.get_chat_member(REKLAMA_CHANNEL_ID, uid)
        if m.status in ["member", "administrator", "creator"]:
            async with async_session() as session:
                u = await session.get(User, uid)
                if u and u.task_reklama == 0:
                    u.balance += 150000
                    u.task_reklama = 1
                    await session.commit()
                    return {"ok": True, "message": "Успешно! +150,000 монет"}
    except: pass
    return {"ok": False, "message": "Подпишитесь на рекламный канал!"}

@app.get("/get_top")
async def get_top():
    async with async_session() as session:
        res = await session.execute(select(User).order_by(desc(User.balance)).limit(10))
        users = res.scalars().all()
        return [{"username": u.username or f"ID{str(u.user_id)[-4:]}", "balance": u.balance} for u in users]

@dp.message(Command("start"))
async def cmd_start(m: types.Message, command: CommandObject):
    ref_id = None
    if command.args and command.args.isdigit():
        ref_id = int(command.args)

    async with async_session() as session:
        user = await session.get(User, m.from_user.id)
        if not user:
            user = User(user_id=m.from_user.id, username=m.from_user.username, referrer_id=ref_id)
            session.add(user)
            # Бонус пригласившему (1 уровень)
            if ref_id:
                ref_user = await session.get(User, ref_id)
                if ref_user:
                    ref_user.balance += 50000
                    # Бонус за 2 уровень (тому, кто пригласил твоего реферала)
                    if ref_user.referrer_id:
                        grand_ref = await session.get(User, ref_user.referrer_id)
                        if grand_ref: grand_ref.balance += 15000
            await session.commit()
    
    await m.answer(f"🔥 Привет! Приглашай друзей и получай до 50,000 монет за каждого!", 
                   reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="💸 ИГРАТЬ", web_app=types.WebAppInfo(url=APP_URL))]]))

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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    
