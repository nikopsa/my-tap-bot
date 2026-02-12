import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder

API_TOKEN = '8377110375:AAEVrLv1nt_6EuduX6QEbAvi0iG7vh6PxWA'
GAME_URL = 'https://nikopsa.github.io'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(m: types.Message):
    builder = ReplyKeyboardBuilder()
    builder.row(types.KeyboardButton(text="Играть 🎮", web_app=types.WebAppInfo(url=GAME_URL)))
    builder.row(types.KeyboardButton(text="Баланс 💰"), types.KeyboardButton(text="Энергия ⚡"))
    await m.answer("Super Tap готов! 🚀", reply_markup=builder.as_markup(resize_keyboard=True))

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
