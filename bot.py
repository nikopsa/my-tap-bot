import os
import logging
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from fastapi.responses import HTMLResponse

# ТВОИ НАСТРОЙКИ
TOKEN = "8377110375:AAG3GmbEpQGyIcfzyOByu6qPUPVbxhYpPSg"
BASE_URL = "https://my-tap-bot.onrender.com"

# Настройка логирования (чтобы видеть ошибки в Render)
logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

# 1. ОБРАБОТКА КОМАНД БОТА
@dp.message()
async def start_handler(message: types.Message):
    # Создаем кнопку, которая открывает Mini App
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔥 ИГРАТЬ В FENIX TAP 🔥", 
            web_app=WebAppInfo(url=BASE_URL)
        )]
    ])
    await message.answer(
        f"Привет, {message.from_user.first_name}!\nНажми кнопку ниже, чтобы запустить игру:", 
        reply_markup=markup
    )

# 2. ПРИЕМ СООБЩЕНИЙ ОТ TELEGRAM (WEBHOOK)
@app.post("/webhook")
async def telegram_webhook(request: Request):
    update = types.Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)

# 3. УСТАНОВКА WEBHOOK ПРИ ЗАПУСКЕ СЕРВЕРА
@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(f"{BASE_URL}/webhook")
    logging.info("Webhook set successfully")

# 4. ОТОБРАЖЕНИЕ ИГРЫ (INDEX.HTML)
@app.get("/", response_class=HTMLResponse)
async def index():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>Ошибка: Файл index.html не найден в репозитории!</h1>"
