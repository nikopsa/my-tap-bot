import os
from flask import Flask
from threading import Thread
import telebot

# Создаем веб-сервер для обмана Render
app = Flask('')
@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- ТВОЯ ЛОГИКА БОТА ---
TOKEN = '8377110375:AAHm15GWZEY4nmeRkFOqUEUToH_9NwcjMdE'
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "SuPer-KLikEr запущен!")

if __name__ == '__main__':
    keep_alive() # Запускаем веб-сервер в фоне
    print("Бот погнал!")
    bot.polling(none_stop=True)
