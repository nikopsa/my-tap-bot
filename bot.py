import asyncio, random, os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiohttp import web

TOKEN = '8377110375:AAEMr2VfEfrXGOvKAxexADGOrDfVcEQH7Mk'
PORT = int(os.environ.get("PORT", 10000)) # Render сам даст нужный порт

bot = Bot(token=TOKEN)
dp = Dispatcher()

async def handle(request): return web.Response(text="Bot is running")

@dp.message(Command("start"))
async def s(m: types.Message):
    ver = random.randint(1, 99999)
    url = f'https://nikopsa.github.io{ver}' 
    kb = [[types.KeyboardButton(text="ИГРАТЬ 💰", web_app=types.WebAppInfo(url=url))]]
    await m.answer("Жми кнопку!", reply_markup=types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))

async def main():
    # Запускаем микро-сервер, чтобы Render не ругался
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
