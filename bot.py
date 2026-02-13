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
    # Render сам назначит порт
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- 2. НАСТРОЙКА БОТА ---
# ТВОЙ НОВЫЙ ТОКЕН:
TOKEN = '8377110375:AAG3GmbEpQGyIcfzyOByu6qPUPVbxhYpPSg'
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.InlineKeyboardMarkup()
    
    # Ссылка на твою игру (GitHub Pages)
    game_url = "https://nikopsa.github.io"
    
    web_app = types.WebAppInfo(game_url)
    btn = types.InlineKeyboardButton("🚀 ИГРАТЬ В SUPER-KLIKER", web_app=web_app)
    markup.add(btn)
    
    bot.send_message(
        message.chat.id, 
        f"Привет, {message.from_user.first_name}!\n\nЖми кнопку ниже, чтобы запустить игру:", 
        reply_markup=markup
    )

# --- 3. ЗАПУСК БОТА ---
if __name__ == '__main__':
    keep_alive() # Запуск обманки для порта
    print("Бот запущен с новым токеном!")
    # skip_pending=True гарантированно уберет ошибку 409
    bot.polling(none_stop=True, skip_pending=True)
