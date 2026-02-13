import os
import telebot
from telebot import types
from flask import Flask
from threading import Thread

# --- 1. ОБМАНКА ДЛЯ ВЕБ-СЕРВИСА (RENDER) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    # Подхватываем порт от Render
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- 2. ЛОГИКА БОТА ---
# Твой токен
TOKEN = '8377110375:AAHm15GWZEY4nmeRkFOqUEUToH_9NwcjMdE'
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.InlineKeyboardMarkup()
    
    # Твоя ссылка на игру (GitHub Pages)
    game_url = "https://nikopsa.github.io"
    
    web_app = types.WebAppInfo(game_url)
    btn = types.InlineKeyboardButton("🚀 ИГРАТЬ В SUPER-KLIKER", web_app=web_app)
    markup.add(btn)
    
    bot.send_message(
        message.chat.id, 
        f"Привет, {message.from_user.first_name}!\n\nЖми кнопку ниже, чтобы начать тапать:", 
        reply_markup=markup
    )

# --- 3. ЗАПУСК ---
if __name__ == '__main__':
    keep_alive() # Запуск веб-сервера
    print("Бот успешно запущен!")
    # ИСПРАВЛЕНО: Добавлен True в конец
    bot.polling(none_stop=True, skip_pending=True)
