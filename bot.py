import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# Токен и ССЫЛКА (исправлена на полную с /my-tap-bot/)
API_TOKEN = '8377110375:AAEVrLv1nt_6EuduX6QEbAvi0iG7vh6PxWA'
GAME_URL = 'https://nikopsa.github.io'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(m: types.Message):
    builder = ReplyKeyboardBuilder()
    # Кнопка для запуска Mini App (твоя монета)
    builder.row(types.KeyboardButton(
        text="Играть 🎮", 
        web_app=types.WebAppInfo(url=GAME_URL))
    )
    # Кнопки нижнего меню
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
    await message.answer("💰 Ваш баланс: 0\n\nЗарабатывайте монеты, нажимая на золотую кнопку!")

async def main():
    print("Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
