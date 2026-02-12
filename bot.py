import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiohttp import web

# Твой актуальный токен и полная ссылка на игру
API_TOKEN = '8377110375:AAEVrLv1nt_6EuduX6QEbAvi0iG7vh6PxWA'
GAME_URL = 'https://nikopsa.github.io'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Код для обхода ошибки порта на Render
async def handle(request):
    return web.Response(text="Bot is running")

@dp.message(Command("start"))
async def start(m: types.Message):
    builder = ReplyKeyboardBuilder()
    # Кнопка Mini App
    builder.row(types.KeyboardButton(
        text="Играть 🎮", 
        web_app=types.WebAppInfo(url=GAME_URL))
    )
    builder.row(
        types.KeyboardButton(text="Баланс 💰"),
        types.KeyboardButton(text="Энергия ⚡")
    )
    await m.answer(
        "Бот Василий готов! 🚀\nЖми 'Играть', чтобы открыть тапалку.", 
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

@dp.message(lambda message: message.text == "Баланс 💰")
async def show_balance(message: types.Message):
    await message.answer("💰 Ваш баланс: 0")

async def main():
    # Запуск сервера для порта 10000
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    asyncio.create_task(site.start())
    # Запуск бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
