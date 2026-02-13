import os
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from fastapi.responses import HTMLResponse

# Данные твоего бота
TOKEN = "8377110375:AAG3GmbEpQGyIcfzyOByu6qPUPVbxhYpPSg"
BASE_URL = "https://my-tap-bot.onrender.com"

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

# Ответ бота на любое сообщение: присылает кнопку игры
@dp.message()
async def send_game_button(message: types.Message):
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Начать тапать! 🔥", web_app=WebAppInfo(url=BASE_URL))]
    ])
    await message.answer("Привет! Нажимай на кнопку и заходи в игру:", reply_markup=markup)

# Прием обновлений от Telegram (Webhook)
@app.post("/webhook")
async def handle_webhook(request: Request):
    update = types.Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)

# Установка связи с Telegram при запуске
@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(f"{BASE_URL}/webhook")

# Отдача страницы с игрой (самый простой вариант)
@app.get("/", response_class=HTMLResponse)
async def game_page():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()
