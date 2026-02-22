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

# --- НАСТРОЙКИ ---
TOKEN = "8377110375:AAG31LE62g88acAmbSkdxk_pyeMRmLtqwdM"
APP_URL = "https://my-tap-bot.onrender.com" 

CHANNEL_ID = "" 
REKLAMA_CHANNEL_ID = "" 
# -----------------

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
    referrer_id = Column(BigInteger, nullable=True)

bot = Bot(token=TOKEN)
dp = Dispatcher()

async def auto_leaderboard():
    while True:
        await asyncio.sleep(3600)
        if not CHANNEL_ID: continue
        try:
            async with async_session() as session:
                res = await session.execute(select(User).order_by(desc(User.balance)).limit(5))
                users = res.scalars().all()
                msg = "🏆 **ТОП ЛИДЕРОВ** 🏆\n\n"
                for i, u in enumerate(users):
                    name = u.username or f"Игрок {str(u.user_id)[-4:]}"
                    msg += f"{i+1}. {name} — {u.balance:,} 💰\n"
                await bot.send_message(chat_id=CHANNEL_ID, text=msg, parse_mode="Markdown")
        except: pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ПРИНУДИТЕЛЬНОЕ ОБНОВЛЕНИЕ СТРУКТУРЫ ТАБЛИЦЫ
    async with engine.begin() as conn:
        try:
            # Пытаемся добавить колонки, если их нет
            await conn.execute(text("ALTER TABLE users ADD COLUMN task_sub INTEGER DEFAULT 0"))
            await conn.execute(text("ALTER TABLE users ADD COLUMN task_reklama INTEGER DEFAULT 0"))
            await conn.execute(text("ALTER TABLE users ADD COLUMN referrer_id BIGINT"))
            print("База данных обновлена: добавлены новые колонки")
        except Exception:
            # Если уже есть — просто игнорируем ошибку
            pass
        await conn.run_sync(Base.metadata.create_all)

    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(url=f"{APP_URL}{WEBHOOK_PATH}")
    asyncio.create_task(auto_leaderboard())
    yield
    await engine.dispose()

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/", response_class=HTMLResponse)
async def index():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f: return f.read()
    return "Файл index.html не найден"

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
    if not CHANNEL_ID: return {"ok": False, "message": "Задание временно недоступно"}
    d = await request.json()
    try:
        m = await bot.get_chat_member(CHANNEL_ID, int(d['id']))
        if m.status in ["member", "administrator", "creator"]:
            async with async_session() as session:
                u = await session.get(User, int(d['id']))
                if u and u.task_sub == 0:
                    u.balance += 10000 
                    u.task_sub = 1
                    await session.commit()
                    return {"ok": True, "message": "Подписка подтверждена! +10,000"}
    except: pass
    return {"ok": False, "message": "Вы не подписаны!"}

@app.post("/check_reklama")
async def check_reklama(request: Request):
    if not REKLAMA_CHANNEL_ID: return {"ok": False, "message": "Задание временно недоступно"}
    d = await request.json()
    try:
        m = await bot.get_chat_member(REKLAMA_CHANNEL_ID, int(d['id']))
        if m.status in ["member", "administrator", "creator"]:
            async with async_session() as session:
                u = await session.get(User, int(d['id']))
                if u and u.task_reklama == 0:
                    u.balance += 10000 
                    u.task_reklama = 1
                    await session.commit()
                    return {"ok": True, "message": "Бонус получен! +10,000"}
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
            if ref_id and ref_id != m.from_user.id:
                ref_user = await session.get(User, ref_id)
                if ref_user:
                    ref_user.balance += 5000
                    if ref_user.referrer_id:
                        grand_ref = await session.get(User, ref_user.referrer_id)
                        if grand_ref: grand_ref.balance += 1000
            await session.commit()
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="💸 ИГРАТЬ", web_app=types.WebAppInfo(url=APP_URL))]])
    await m.answer(f"🔥 Добро пожаловать в Fenix Tap!", reply_markup=kb)

@app.post(WEBHOOK_PATH)
async def wh(r: Request):
    data = await r.json()
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot, update)
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
    return {"ok": False, "message": "Бонус раз в 24 часа"}

@app.post("/create_invoice")
async def create_invoice(request: Request):
    d = await request.json()
    p = {"pack_light": ["⚡ Start (+8/s)", 100], "pack_ext": ["🔥 Pro (+25/s)", 300]}.get(d['type'])
    link = await bot.create_invoice_link(title=p[0], description="Boost", payload=f"buy_{d['type']}_{d['id']}", provider_token="", currency="XTR", prices=[LabeledPrice(label=p[0], amount=p[1])])
    return {"link": link}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
        
