import os
import random
import threading
import re
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Инициализация бота
bot = telebot.TeleBot(os.getenv("BOT_TOKEN"))

# Данные администратора
ADMIN_ID = 8448501815  # Твой точный ID
ADMIN_USERNAME = "@qisoco"

# Глобальные настройки
RESPONSE_CHANCE = 30  # Дефолтный шанс ответа

# Базы данных в памяти (сбросятся при перезапуске сервера)
chat_histories = {}    # Память фраз: {chat_id: [список фраз]}
chat_activity = {}     # Счетчик сообщений: {chat_id: {"title": имя, "count": число, "link": ссылка}}
user_reputation = {}   # Карма юзеров: {chat_id: {user_id: {"name": имя, "rep": число}}}
users_db = set()       # Юзеры в личке для рассылки

# Веб-сервер для Render
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Mega Talk Bot is ultra alive!")

def run_health_check():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()


# ================= УМНЫЙ ДВИЖОК ПОДБОРА СЛОВ И ОТВЕТОВ =================

def tokenize(text):
    text = text.lower()
    words = re.findall(r'[а-яёa-z0-9]+', text)
    return [w for w in words if len(w) > 2]

def generate_smart_reply(user_text, chat_id):
    history = chat_histories.get(chat_id, [])
    user_words = tokenize(user_text)
    
    # 1. Если это вопрос (есть "?" или вопросительные слова)
    if "?" in user_text or any(q in user_text.lower() for q in ["как", "почему", "зачем", "кто", "где", "когда", "что"]):
        question_replies = [
            "Да тут и думать нечего, всё очевидно.",
            "Секретная информация, не скажу.",
            "Потому что так надо, не задавай глупых вопросов.",
            "Честно? Мне похуй.",
            "Тут надо подумать, но мне лень.",
            "Спроси у кого попроще, я слишком умен для этого.",
            "100%, даже не сомневайся."
        ]
        # Пытаемся подмешать фразу из истории чата для контекста
        if history and random.random() > 0.4:
            return f"{random.choice(question_replies)} К тому же, как тут говорили: «{random.choice(history)}»"
        return random.choice(question_replies)

    # 2. Если обычный текст — ищем совпадения по ключевым словам
    if user_words and history:
        candidates = []
        max_overlap = 0
        for phrase in history:
            if phrase.lower() == user_text.lower():
                continue
            phrase_words = tokenize(phrase)
            overlap = len(set(user_words) & set(phrase_words))
            
            if overlap > max_overlap:
                max_overlap = overlap
                candidates = [phrase]
            elif overlap == max_overlap and overlap > 0:
                candidates.append(phrase)
        
        if candidates and max_overlap > 0:
            return random.choice(candidates)

    # 3. Базовый уверенный ответ, если зацепиться не за что
    base_phrases = [
        "Базару ноль, согласен.", "Ну и хуйню ты высрал, конечно.", "Жиза полнейшая",
        "Честно, звучит как бред.", "Реально? Ну ладно.", "Всё, завязывай с этим.",
        "Ахах, хорош!", "Ой, да ладно тебе придумывать."
    ]
    return random.choice(history) if history and random.random() > 0.5 else random.choice(base_phrases)


# ================= КОМАНДЫ И АДМИН-ФУНКЦИИ =================

@bot.message_handler(commands=['chance'], func=lambda msg: msg.chat.type in ['group', 'supergroup'])
def change_chance(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        new_chance = int(message.text.split()[1])
        if 0 <= new_chance <= 100:
            global RESPONSE_CHANCE
            RESPONSE_CHANCE = new_chance
            bot.reply_to(message, f"⚙ Шанс ответов изменен на `{RESPONSE_CHANCE}%`")
    except Exception:
        bot.reply_to(message, "❌ Юзай: `/chance 50`")

@bot.message_handler(commands=['status'])
def get_status(message):
    if message.from_user.id != ADMIN_ID: return
    status = (
        f"👑 *Панель управления qisoco:*\n\n"
        f"• Текущий шанс ответа: `{RESPONSE_CHANCE}%`\n"
        f"• Всего чатов в памяти: `{len(chat_histories)}`\n"
        f"• Юзеров в базе рассылки: `{len(users_db)}`"
    )
    bot.reply_to(message, status, parse_mode="Markdown")

@bot.message_handler(commands=['sueta'])
def make_sueta(message):
    """Команда для создания искусственного актива."""
    sueta_phrases = [
        "АЛО СУЕТУ НАВЕСТИ ОХОТА НАМ ⚡⚡", 
        "Чат засыпает, просыпается мафия! Чо притихли?", 
        "Эй, вы там живые вообще? 🤔", 
        "Срочный сбор! Сюда быстро!"
    ]
    bot.send_message(message.chat.id, random.choice(sueta_phrases))

@bot.message_handler(commands=['chats'])
def show_top_chats(message):
    """Вывод рейтинга активности чатов."""
    if not chat_activity:
        bot.reply_to(message, "📊 Бот ещё не накопил статистику по чатам.")
        return
    
    # Сортируем по количеству сообщений
    sorted_chats = sorted(chat_activity.values(), key=lambda x: x['count'], reverse=True)[:5]
    
    text = "📊 *Рейтинг активности чатов, где я общаюсь:*\n\n"
    for i, chat in enumerate(sorted_chats, 1):
        link_str = f"🔗 [Ссылка]({chat['link']})" if chat['link'] else "🔒 Приватная группа"
        text += f"{i}. *{chat['title']}* — Сообщений: `{chat['count']}` | {link_str}\n"
        
    bot.send_message(message.chat.id, text, parse_mode="Markdown", disable_web_page_preview=True)

@bot.message_handler(commands=['rating'], func=lambda msg: msg.chat.type in ['group', 'supergroup'])
def show_rep_rating(message):
    """Показать репутацию пользователей в конкретном чате."""
    chat_id = message.chat.id
    if chat_id not in user_reputation or not user_reputation[chat_id]:
        bot.reply_to(message, "🥇 В этом чате ещё никто не заслужил уважения (карма пуста).")
        return
        
    sorted_users = sorted(user_reputation[chat_id].values(), key=lambda x: x['rep'], reverse=True)[:10]
    text = "👑 *Товарищеский рейтинг репутации чата:*\n\n"
    for i, u in enumerate(sorted_users, 1):
        text += f"{i}. *{u['name']}* — Карма: `{u['rep']}`\n"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['Rassil'])
def admin_broadcast(message):
    if message.from_user.id != ADMIN_ID: return
    text_to_send = message.text.replace('/Rassil', '').strip()
    if not text_to_send: return
    
    bot.reply_to(message, f"📢 Запуск рассылки...")
    success = 0
    for u_id in list(users_db):
        try:
            bot.send_message(u_id, text_to_send)
            success += 1
        except Exception: pass
    bot.send_message(message.chat.id, f"✅ Отправлено: {success}/{len(users_db)}")


# ================= ИНТЕРФЕЙС В ЛИЧКЕ БОТА =================

def main_inline_menu():
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton(text="📊 Рейтинг чатов", callback_data="menu_chats"))
    markup.row(InlineKeyboardButton(text="ℹ Инфо о боте", callback_data="menu_info"))
    return markup

@bot.message_handler(commands=['start'], func=lambda msg: msg.chat.type == 'private')
def private_start(message):
    users_db.add(message.chat.id)
    text = f"Привет! Я твой кастомный супер-разговорный бот. 🤖\n\nЯ умею анализировать вопросы, вести рейтинг активности групп и подсчитывать карму участников чата!"
    bot.send_message(message.chat.id, text, reply_markup=main_inline_menu())

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    if call.data == "menu_chats":
        if not chat_activity:
            bot.edit_message_text("Статистика пока пуста.", call.message.chat.id, call.message.message_id, reply_markup=main_inline_menu())
            return
        sorted_chats = sorted(chat_activity.values(), key=lambda x: x['count'], reverse=True)[:5]
        text = "🔥 *Топ-5 активных чатов со мной:*\n\n"
        for i, chat in enumerate(sorted_chats, 1):
            text += f"{i}. {chat['title']} (`{chat['count']}` сообщений)\n"
        
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(text="⬅ Назад", callback_data="to_main")]])
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        
    elif call.data == "to_main":
        text = "Привет! Выбирай нужный раздел в меню ниже:"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=main_inline_menu())
        
    elif call.data == "menu_info":
        info = f"👤 *Админ:* {ADMIN_USERNAME}\n⚡ *Версия:* Ultra Custom 4.0\n⚙ Разработано специально для контроля суеты в чатах."
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(text="⬅ Назад", callback_data="to_main")]])
        bot.edit_message_text(info, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)


# ================= ОБРАБОТКА СУЕТЫ В ЧАТАХ =================

@bot.message_handler(content_types=['text'], func=lambda msg: msg.chat.type in ['group', 'supergroup'])
def chat_processor(message):
    chat_id = message.chat.id
    text = message.text.strip()
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "Аноним"

    # Инициализация структур для нового чата
    if chat_id not in chat_histories:
        chat_histories[chat_id] = ["Привет", "Жиза", "Погнали", "Ну ок", "Капец", "Реально"]
        
    # Считаем общую активность чата и пытаемся получить инвайт-ссылку
    if chat_id not in chat_activity:
        chat_link = None
        try:
            chat_info = bot.get_chat(chat_id)
            chat_link = chat_info.invite_link
        except Exception: pass
        chat_activity[chat_id] = {"title": message.chat.title, "count": 0, "link": chat_link}
    
    chat_activity[chat_id]["count"] += 1

    # Инициализация кармы для чата
    if chat_id not in user_reputation:
        user_reputation[chat_id] = {}

    # --- СИСТЕМА СОЦИАЛЬНОГО РЕЙТИНГА (+ / -) ---
    if message.reply_to_message and text in ["+", "-", "➕", "➖"]:
        target_user = message.reply_to_message.from_user
        if target_user.id == user_id:
            bot.reply_to(message, "❌ Нельзя изменять карму самому себе, фокусник!")
            return
            
        if target_user.id not in user_reputation[chat_id]:
            user_reputation[chat_id][target_user.id] = {"name": target_user.first_name, "rep": 0}
            
        if text in ["+", "➕"]:
            user_reputation[chat_id][target_user.id]["rep"] += 1
            bot.send_message(chat_id, f"👍 *{user_name}* поднял карму *{target_user.first_name}* (Всего: `{user_reputation[chat_id][target_user.id]['rep']}`)", parse_mode="Markdown")
        elif text in ["-", "➖"]:
            user_reputation[chat_id][target_user.id]["rep"] -= 1
            bot.send_message(chat_id, f"👎 *{user_name}* опустил карму *{target_user.first_name}* (Всего: `{user_reputation[chat_id][target_user.id]['rep']}`)", parse_mode="Markdown")
        return

    # Игнорируем команды для обучения фраз
    if text.startswith('/'): return

    # Обучение бота (запоминаем реплики людей)
    if len(text) > 1 and text not in chat_histories[chat_id]:
        chat_histories[chat_id].append(text)
        if len(chat_histories[chat_id]) > 2000:
            chat_histories[chat_id].pop(0)

    # Проверка шанса на ответ
    if random.random() * 100 > RESPONSE_CHANCE:
        return

    # Генерируем умный ответ на основе контекста
    response = generate_smart_reply(text, chat_id)
    
    # Натуральная задержка
    threading.Timer(1.0, lambda: bot.send_message(chat_id, response)).start()


# ================= ЗАПУСК С КОРРЕКЦИЕЙ ОШИБОК 409 =================

if __name__ == "__main__":
    threading.Thread(target=run_health_check, daemon=True).start()
    
    try:
        bot.remove_webhook()
        print("Старые сессии сброшены.")
    except Exception as e:
        print(f"Ошибка сброса вебхука: {e}")

    print(f"Мега-Бот успешно запущен. Хозяин: {ADMIN_USERNAME}")
    
    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            print(f"Конфликт или падение пуллинга, рестарт через 5 секунд... ({e})")
            time.sleep(5)
