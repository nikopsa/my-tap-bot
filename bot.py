import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiohttp import web

# Твой актуальный токен
TOKEN = '8377110375:AAHoZfiYoow9it_2SsIYNsR0cE_Jwd9jKyU'
# ПРЯМАЯ ССЫЛКА (так как index.html лежит рядом с bot.py)
URL = 'https://nikopsa.github.io'

bot = Bot(token=TOKEN)
dp = Dispatcher()

async def handle(request):
    return web.Response(text="LIVE")

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    kb = [[types.KeyboardButton(text="Играть 🎮", web_app=types.WebAppInfo(url=URL))]]
    markup = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await m.answer("Бот Василий готов! Жми играть 🚀", reply_markup=markup)

async def main():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', 10000).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
