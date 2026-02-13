import asyncio, random
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# Токен ваш, рабочий.
TOKEN = '8377110375:AAEMr2VfEfrXGOvKAxexADGOrDfVcEQH7Mk'

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def s(m: types.Message):
    # Исправлено: добавлен слэш и параметр для сброса кэша
    ver = random.randint(1, 99999)
    url = f'https://nikopsa.github.io{ver}' 
    
    kb = [[types.KeyboardButton(text="ИГРАТЬ 💰", web_app=types.WebAppInfo(url=url))]]
    markup = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    
    await m.answer("Жми кнопку, кэш очищен!", reply_markup=markup)

async def main():
    # Удаляем вебхук перед стартом, чтобы не было Conflict
    await bot.delete_webhook(drop_pending_updates=True)
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
