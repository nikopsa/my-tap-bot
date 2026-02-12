import asyncio, random
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiohttp import web

TOKEN = '8377110375:AAEMr2VfEfrXGOvKAxexADGOrDfVcEQH7Mk'

bot = Bot(token=TOKEN)
dp = Dispatcher()

async def handle(r): return web.Response(text="OK")

@dp.message(Command("start"))
async def s(m: types.Message):
    # Генерация уникальной ссылки для пробива кэша
    ver = random.randint(1, 99999)
    url = f'https://nikopsa.github.io{ver}'
    kb = [[types.KeyboardButton(text="ИГРАТЬ 💰", web_app=types.WebAppInfo(url=url))]]
    await m.answer("Жми кнопку, кэш очищен!", reply_markup=types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))

async def main():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', 10000).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
