import os
import random
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Инициализация бота (токен берется из настроек Render)
bot = telebot.TeleBot(os.getenv("BOT_TOKEN"))

# Данные администратора
ADMIN_ID = 8448501815  # Твой точный ID
ADMIN_USERNAME = "@qisoco"

# Глобальные настройки бота в оперативной памяти
RESPONSE_CHANCE = 30  # Дефолтный шанс ответа в чатах (в процентах)

# Базы данных в памяти сервера
chat_histories = {}  # История сообщений для каждого чата отдельно
users_db = set()     # Список ID пользователей для рассылки

# Веб-сервер для прохождения проверки портов на Render
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Advanced Talk Bot is running perfectly!")

def run_health_check():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()


# ================= АДМИН-ФУНКЦИЯ: РАССЫЛКА =================

@bot.message_handler(commands=['Rassil'])
def admin_broadcast(message):
    # Строгая проверка по ID
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ У вас нет прав администратора для выполнения рассылки.")
        return

    # Вырезаем команду из текста, оставляя только сообщение для рассылки
    text_to_send = message.text.replace('/Rassil', '').strip()
    
    if not text_to_send:
        bot.reply_to(message, "❌ Ошибка! Использование: `/Rassil Текст вашей рассылки`")
        return

    if not users_db:
        bot.reply_to(message, "⚠ База пользователей пуста. Никто ещё не запускал бота в личке.")
        return

    bot.reply_to(message, f"📢 Начинаю рассылку для {len(users_db)} пользователей...")
    
    success_count = 0
    for user_id in list(users_db):
        try:
            bot.send_message(user_id, text_to_send)
            success_count += 1
        except Exception as e:
            print(f"Ошибка отправки пользователю {user_id}: {e}")
            
    bot.send_message(message.chat.id, f"✅ Рассылка завершена!\nУспешно отправлено: *{success_count}/{len(users_db)}*", parse_mode="Markdown")


# ================= ИНТЕРФЕЙС В ЛИЧКЕ (МЕНЮ И НАСТРОЙКИ) =================

def get_main_menu():
    markup = InlineKeyboardMarkup()
    btn_stats = InlineKeyboardButton(text="📊 Статистика", callback_data="bot_stats")
    btn_chance = InlineKeyboardButton(text="⚙ Шанс ответа", callback_data="bot_chance_menu")
    markup.row(btn_stats, btn_chance)
    return markup

@bot.message_handler(commands=['start'], func=lambda msg: msg.chat.type == 'private')
def private_start(message):
    # Сохраняем пользователя в базу рассылки
    users_db.add(message.chat.id)
    
    welcome_text = (
        f"Привет! Я твой продвинутый разговорный бот. 🤖\n\n"
        f"Добавь меня в групповые чаты, и я буду учиться общаться на основе ваших сообщений.\n\n"
        f"👑 *Администратор:* {ADMIN_USERNAME}\n"
        f"⚙ *Шанс ответа в чатах:* `{RESPONSE_CHANCE}%`"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=get_main_menu())

@bot.callback_query_handler(func=lambda call: call.data == "to_menu")
def back_to_menu(call):
    welcome_text = (
        f"Привет! Я твой продвинутый разговорный бот. 🤖\n\n"
        f"👑 *Администратор:* {ADMIN_USERNAME}\n"
        f"⚙ *Шанс ответа в чатах:* `{RESPONSE_CHANCE}%`"
    )
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=welcome_text, parse_mode="Markdown", reply_markup=get_main_menu())

@bot.callback_query_handler(func=lambda call: call.data == "bot_stats")
def show_stats(call):
    stats_text = (
        f"📊 *Статистика системы:*\n\n"
        f"• Активных чатов в кэше: `{len(chat_histories)}`\n"
        f"• Пользователей в базе рассылки: `{len(users_db)}`"
    )
    markup = InlineKeyboardMarkup([[InlineKeyboardButton(text="⬅ Назад", callback_data="to_menu")]])
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=stats_text, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "bot_chance_menu")
def show_chance_menu(call):
    text = f"⚙ *Настройка частоты ответов:*\n\nТекущий шанс: `{RESPONSE_CHANCE}%`\nВыбери новый шанс из вариантов ниже:"
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton(text="10%", callback_data="set_ch_10"),
        InlineKeyboardButton(text="30%", callback_data="set_ch_30"),
        InlineKeyboardButton(text="50%", callback_data="set_ch_50")
    )
    markup.row(InlineKeyboardButton(text="70%", callback_data="set_ch_70"), InlineKeyboardButton(text="100%", callback_data="set_ch_100"))
    markup.add(InlineKeyboardButton(text="⬅ Назад", callback_data="to_menu"))
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('set_ch_'))
def set_chance(call):
    global RESPONSE_CHANCE
    new_chance = int(call.data.split('_')[2])
    RESPONSE_CHANCE = new_chance
    show_chance_menu(call)


# ================= РАБОТА В ЧАТАХ (ОБУЧЕНИЕ И РАЗГОВОРЫ) =================

@bot.message_handler(commands=['сброс', 'reset'], func=lambda msg: msg.chat.type in ['group', 'supergroup'])
def reset_chat_db(message):
    """Сброс памяти конкретного чата (для админов группы или тебя)."""
    chat_member = bot.get_chat_member(message.chat.id, message.from_user.id)
    if chat_member.status in ['creator', 'administrator'] or message.from_user.id == ADMIN_ID:
        if message.chat.id in chat_histories:
            chat_histories[message.chat.id] = []
        bot.reply_to(message, "🧹 Память этого чата успешно очищена. Я всё забыл!")
    else:
        bot.reply_to(message, "❌ Сбрасывать базу данных могут только администраторы чата.")

@bot.message_handler(content_types=['text'], func=lambda msg: msg.chat.type in ['group', 'supergroup'])
def chat_talking(message):
    if message.text.startswith('/'):
        return

    chat_id = message.chat.id
    text = message.text.strip()

    # Дефолтные фразы для старта нового чата
    if chat_id not in chat_histories:
        chat_histories[chat_id] = ["Привет всем!", "Что делаете?", "Жиза", "Понятно", "Интересно..."]

    # Самообучение бота
    if len(text) > 1 and text not in chat_histories[chat_id]:
        chat_histories[chat_id].append(text)
        if len(chat_histories[chat_id]) > 1500:  # Ограничение памяти на один чат
            chat_histories[chat_id].pop(0)

    # Проверка рандома на ответ
    if random.random() * 100 > RESPONSE_CHANCE:
        return

    response = random.choice(chat_histories[chat_id])
    
    # Небольшая задержка перед отправкой для реалистичности
    threading.Timer(1.2, lambda: bot.send_message(chat_id, response)).start()


if __name__ == "__main__":
    # Запуск фонового веб-сервера для деплоя на Render
    threading.Thread(target=run_health_check, daemon=True).start()
    
    print(f"Бот успешно запущен. Администратор: {ADMIN_USERNAME}")
    bot.infinity_polling()
    
