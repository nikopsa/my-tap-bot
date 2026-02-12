# -*- coding: utf-8 -*-
import asyncio, logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

API_TOKEN = '8377110375:AAG6xPo3eqYfMwqXxuqwpjkGJlsj57gSefU'
GAME_URL = 'https://nikopsa.github.io'

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(m: types.Message):
    kb = [[types.KeyboardButton(text="Играть 🎮", web_app=types.WebAppInfo(url=GAME_URL))]]
    markup = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await m.answer("Super Tap запущен! 🚀", reply_markup=markup)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
