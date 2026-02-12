import asyncio
import random
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiohttp import web

# Твой токен
TOKEN = '8377110375:AAHoZfiYoow9it_2SsIYNsR0cE_Jwd9jKyU'
# Ссылка СТРОГО такая (не меняй её вручную!)
URL = f'https://nikopsa.github.io{random.randint(1, 999999)}'

bot = Bot(token=TOKEN)
dp = Dispatcher()

async def handle(request):
    return web.Response(text="БОТ В СЕТИ")

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    kb = [[types.KeyboardButton(text="ЗАПУСТИТЬ МОНЕТУ 💰", web_app=types.WebAppInfo(url=URL))]]
    markup = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await m.answer("Лучший Тап готов! 🚀\nЖми на кнопку ниже, чтобы начать:", reply_markup=markup)

async def main():
    logging.basicConfig(level=logging.INFO)
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', 10000).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
