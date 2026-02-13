import os
import telebot
from telebot import types
from flask import Flask
from threading import Thread

# --- 1. ОБМАНКА ДЛЯ RENDER ---
app = Flask('')

@app.route('/')
def home():
    return "SuPerKLikEr is alive!"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- 2. НАСТРОЙКА БОТА ---
# Твой актуальный токен
TOKEN = '8377110375:AAG3GmbEpQGyIcfzyOByu6qPUPVbxhYpPSg'
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.InlineKeyboardMarkup()
    
    # Ссылка на игру (БЕЗ ДЕФИСА, если ты сменил название репозитория)
    # Если репозиторий на GitHub всё еще называется "my-tap-bot", оставь ссылку как есть
    game_url = "https://nikopsa.github.io"
    
    web_app = types.WebAppInfo(game_url)
    btn = types.InlineKeyboardButton("🚀 ИГРАТЬ В SUPERKLIKER", web_app=web_app)
    markup.add(btn)
    
    bot.send_message(
        message.chat.id, 
        f"Привет, {message.from_user.first_name}!\n\nДобро пожаловать в SuPerKLikEr. Жми кнопку ниже:", 
        reply_markup=markup
    )

# --- 3. ЗАПУСК ---
if __name__ == '__main__':
    keep_alive()
    print("Бот SuPerKLikEr запущен!")
    try:
        bot.polling(none_stop=True, skip_pending=True)
    except Exception as e:
        print(f"Ошибка: {e}")
