import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# Твой токен и настройки
API_TOKEN = '8377110375:AAHrAOLQOvAKOanxJFccT5V7ofiK1-TWvTk'
GAME_URL = 'https://nikopsa.github.io'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    builder = ReplyKeyboardBuilder()
    
    # Главная кнопка запуска игры
    builder.row(types.KeyboardButton(
        text="Играть 🎮", 
        web_app=types.WebAppInfo(url=GAME_URL))
    )
    
    # Кнопки меню
    builder.row(
        types.KeyboardButton(text="Баланс 💰"),
        types.KeyboardButton(text="Энергия ⚡")
    )
    
    await message.answer(
        "Василий, добро пожаловать в Super Tap! 🚀\n\n"
        "Нажимай на кнопку ниже, чтобы запустить игру.",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

@dp.message(lambda message: message.text == "Баланс 💰")
async def show_balance(message: types.Message):
    await message.answer("💰 Ваш баланс: 0\n\nЗарабатывайте монеты в игре!")

@dp.message(lambda message: message.text == "Энергия ⚡")
async def show_energy(message: types.Message):
    await message.answer("⚡ Энергия: 100/100\n\nВосстанавливается со временем.")

async def main():
    print("Бот запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
