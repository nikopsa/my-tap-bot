import os
import telebot
from telebot import types
from flask import Flask
from threading import Thread

# --- 1. ОБМАНКА ДЛЯ RENDER (ЧТОБЫ НЕ ВЫЛЕТАЛО) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    # Render сам назначит порт, мы его просто используем
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- 2. НАСТРОЙКА БОТА ---
# Твой рабочий токен
TOKEN = '8377110375:AAHm15GWZEY4nmeRkFOqUEUToH_9NwcjMdE'
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    # Создаем кнопку-меню
    markup = types.InlineKeyboardMarkup()
    
    # ССЫЛКА НА ТВОЮ ИГРУ (GitHub Pages)
    # Замени ТВОЙ_ЛОГИН на свой реальный ник на GitHub
    game_url = "https://nikopsa.github.io"
    
    web_app = types.WebAppInfo(game_url)
    btn = types.InlineKeyboardButton("🚀 ЗАПУСТИТЬ SUPER-KLIKER", web_app=web_app)
    markup.add(btn)
    
    bot.send_message(
        message.chat.id, 
        f"Привет, {message.from_user.first_name}!\n\nДобро пожаловать в SuPer-KLikEr. Жми кнопку ниже и начни тапать!", 
        reply_markup=markup
    )

# --- 3. ЗАПУСК ВСЕЙ СИСТЕМЫ ---
if __name__ == '__main__':
    keep_alive() # Стартуем веб-сервер
    print("Бот запущен и готов к работе на Render!")
    # skip_pending=True чтобы бот не захлебнулся от старых сообщений
    bot.polling(none_stop=True, skip_pending=True)
