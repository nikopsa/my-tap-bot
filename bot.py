import os
import telebot
from flask import Flask
from threading import Thread

# --- ОБМАНКА ДЛЯ RENDER (WEB-СЕРВЕР) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    # Render передает PORT автоматически, мы его подхватываем
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- ЛОГИКА ТВОЕГО БОТА ---
TOKEN = '8377110375:AAHm15GWZEY4nmeRkFOqUEUToH_9NwcjMdE'
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "🚀 SuPer-KLikEr ожил! Ты в деле.")

# --- ЗАПУСК ---
if __name__ == '__main__':
    keep_alive() # Запускаем веб-сервер, чтобы Render не ругался
    print("Бот успешно запущен!")
    bot.polling(none_stop=True, skip_pending=True)
