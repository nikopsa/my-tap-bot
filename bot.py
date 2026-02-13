import telebot
from telebot import types

# Твой новый токен
TOKEN = '8377110375:AAHm15GWZEY4nmeRkFOqUEUToH_9NwcjMdE'
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    # Создаем кнопку для запуска Mini App
    markup = types.InlineKeyboardMarkup()
    
    # ВНИМАНИЕ: Замени ссылку ниже на свою, если у тебя есть сайт. 
    # Пока я ставлю заглушку, чтобы ты увидел, как это работает.
    web_app = types.WebAppInfo("https://yandex.ru") 
    
    btn = types.InlineKeyboardButton("🚀 Запустить SuPer-KLikEr", web_app=web_app)
    markup.add(btn)
    
    bot.send_message(
        message.chat.id, 
        f"Привет, {message.from_user.first_name}!\nНажимай кнопку ниже, чтобы начать игру:", 
        reply_markup=markup
    )
