import os
import random
import threading
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Инициализация бота
bot = telebot.TeleBot(os.getenv("BOT_TOKEN"))

# Данные администратора
ADMIN_ID = 8448501815  # Твой ID
ADMIN_USERNAME = "@qisoco"

# Настройки (в памяти)
RESPONSE_CHANCE = 30  # Дефолтный шанс ответа в чатах

# Базы данных
chat_histories = {}  # История сообщений для каждого чата отдельно
users_db = set()     # Список ID пользователей для рассылки

# Веб-сервер для Render
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Smart Talk Bot is running!")

def run_health_check():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# Очистка текста от мусора для анализа ключевых слов
def tokenize(text):
    text = text.lower()
    words = re.findall(r'[а-яёa-z0-9]+', text)
    return [w for w in words if len(w) > 2] # Берем слова длиннее 2 букв

# Хитрый алгоритм выбора «умного» ответа
def find_best_reply(user_text, history):
    user_words = tokenize(user_text)
    
    # Если человек написал что-то слишком короткое, даем случайный ответ
    if not user_words:
        return random.choice(history)

    best_match = None
    max_overlap = 0
    candidates = []

    # Ищем в истории фразу, в которой есть совпадения по словам
    for phrase in history:
        if phrase.lower() == user_text.lower():
            continue # Не повторяем в точности то же самое сообщение
            
        phrase_words = tokenize(phrase)
        # Находим общие слова
        overlap = len(set(user_words) & set(phrase_words))
        
        if overlap > max_overlap:
            max_overlap = overlap
            candidates = [phrase]
        elif overlap == max_overlap and overlap > 0:
            candidates.append(phrase)

    # Если нашли фразы в тему — выбираем из них рандомно
    if candidates and max_overlap > 0:
        return random.choice(candidates)
        
    # Если совпадений вообще нет, выбираем фразу, которая звучит как реакция
    reactions = [p for p in history if len(p) < 40] # Короткие реплики для поддержания разговора
    return random.choice(reactions) if reactions else random.choice(history)


# ================= АДМИН-ФУНКЦИИ В ЧАТАХ =================

@bot.message_handler(commands=['chance'], func=lambda msg: msg.chat.type in ['group', 'supergroup'])
def change_chance_inline(message):
    """Изменение шанса ответа прямо из чата."""
    if message.from_user.id != ADMIN_ID:
        return

    global RESPONSE_CHANCE
    try:
        args = message.text.split()
        if len(args) > 1:
            new_chance = int(args[1])
            if 0 <= new_chance <= 100:
                RESPONSE_CHANCE = new_chance
                bot.reply_to(message, f"⚙ Шанс ответа бота для всех чатов изменен на `{RESPONSE_CHANCE}%`")
            else:
                bot.reply_to(message, "❌ Шанс должен быть от 0 до 100")
    except ValueError:
        bot.reply_to(message, "❌ Пример использования: `/chance 40`")

@bot.message_handler(commands=['status'])
def server_status(message):
    """Быстрый чек статуса для админа."""
    if message.from_user.id != ADMIN_ID:
        return
        
    status_text = (
        f"⚙ *Статус Бота:*\n"
        f"• Шанс ответа: `{RESPONSE_CHANCE}%`\n"
        f"• Чатов в памяти: `{len(chat_histories)}`\n"
        f"• Юзеров в рассылке: `{len(users_db)}`"
    )
    bot.reply_to(message, status_text, parse_mode="Markdown")

@bot.message_handler(commands=['Rassil'])
def admin_broadcast(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ У вас нет прав администратора.")
        return

    text_to_send = message.text.replace('/Rassil', '').strip()
    if not text_to_send:
        bot.reply_to(message, "❌ Использование: `/Rassil Текст`")
        return

    if not users_db:
        bot.reply_to(message, "⚠ База пользователей пуста.")
        return

    bot.reply_to(message, f"📢 Рассылаю сообщение для {len(users_db)} человек...")
    success_count = 0
    for user_id in list(users_db):
        try:
            bot.send_message(user_id, text_to_send)
            success_count += 1
        except Exception:
            pass
            
    bot.send_message(message.chat.id, f"✅ Успешно отправлено: *{success_count}/{len(users_db)}*", parse_mode="Markdown")


# ================= ИНТЕРФЕЙС В ЛИЧКЕ =================

def get_main_menu():
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton(text="📊 Статистика", callback_data="bot_stats"))
    return markup

@bot.message_handler(commands=['start'], func=lambda msg: msg.chat.type == 'private')
def private_start(message):
    users_db.add(message.chat.id)
    welcome_text = (
        f"Привет! Я твой прокачанный разговорный бот. 🤖\n\n"
        f"Теперь я анализирую контекст беседы и стараюсь отвечать в тему!\n\n"
        f"👑 *Администратор:* {ADMIN_USERNAME}"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=get_main_menu())

@bot.callback_query_handler(func=lambda call: call.data == "bot_stats")
def show_stats(call):
    stats_text = f"📊 *Активных чатов в кэше:* `{len(chat_histories)}`"
    markup = InlineKeyboardMarkup([[InlineKeyboardButton(text="⬅ Назад", callback_data="to_menu")]])
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=stats_text, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "to_menu")
def back_to_menu(call):
    welcome_text = f"Привет! Я твой прокачанный разговорный бот. 🤖\n\n👑 *Администратор:* {ADMIN_USERNAME}"
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=welcome_text, parse_mode="Markdown", reply_markup=get_main_menu())


# ================= РАБОТА В ЧАТАХ =================

@bot.message_handler(commands=['сброс', 'reset'], func=lambda msg: msg.chat.type in ['group', 'supergroup'])
def reset_chat_db(message):
    chat_member = bot.get_chat_member(message.chat.id, message.from_user.id)
    if chat_member.status in ['creator', 'administrator'] or message.from_user.id == ADMIN_ID:
        if message.chat.id in chat_histories:
            chat_histories[message.chat.id] = []
        bot.reply_to(message, "🧹 Память чата очищена!")

@bot.message_handler(content_types=['text'], func=lambda msg: msg.chat.type in ['group', 'supergroup'])
def chat_talking(message):
    if message.text.startswith('/'):
        return

    chat_id = message.chat.id
    text = message.text.strip()

    # Стартовая база, если чат видит бота впервые
    if chat_id not in chat_histories:
        chat_histories[chat_id] = [
            "Привет всем!", "Что делаете?", "Жиза", "Понятно", "Интересно...", 
            "Ну такое", "Ахах, согл", "Капец", "Да ладно вам", "Реально"
        ]

    # Обучение (запоминаем оригинальные реплики участников)
    if len(text) > 1 and text not in chat_histories[chat_id]:
        chat_histories[chat_id].append(text)
        if len(chat_histories[chat_id]) > 2000:
            chat_histories[chat_id].pop(0)

    # Проверка шанса на ответ
    if random.random() * 100 > RESPONSE_CHANCE:
        return

    # Находим самый адекватный ответ по совпадению слов
    response = find_best_reply(text, chat_histories[chat_id])
    
    # Задержка для реализма
    threading.Timer(1.1, lambda: bot.send_message(chat_id, response)).start()


if __name__ == "__main__":
    threading.Thread(target=run_health_check, daemon=True).start()
    print(f"Умный бот запущен под управлением {ADMIN_USERNAME}")
    bot.infinity_polling()
    
