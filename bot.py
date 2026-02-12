import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder

API_TOKEN = '8377110375:AAG6xPo3eqYfMwqXxuqwpjkGJlsj57gSefU'
GAME_URL = 'https://nikopsa.github.io'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    builder = ReplyKeyboardBuilder()
    builder.row(types.KeyboardButton(text="Играть 🎮", web_app=types.WebAppInfo(url=GAME_URL)))
    builder.row(types.KeyboardButton(text="Баланс 💰"), types.KeyboardButton(text="Энергия ⚡"))
    await message.answer("Василий, Super Tap готов! 🚀\n\nЖми 'Играть'.", reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(lambda message: message.text == "Баланс 💰")
async def show_balance(message: types.Message):
    await message.answer("💰 Баланс: 0")

async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

