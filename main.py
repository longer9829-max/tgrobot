import os
import random
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Инициализация бота
bot = telebot.TeleBot(os.getenv("BOT_TOKEN"))

# Данные администратора
ADMIN_ID = 8448501815  # Твой точный ID
ADMIN_USERNAME = "@qisoco"

# Глобальные настройки бота в памяти
RESPONSE_CHANCE = 30  # Дефолтный шанс ответа в чатах (в процентах)

# Базы данных в оперативной памяти сервера
chat_histories = {}  # История сообщений для каждого чата отдельно
users_db = set()     # Список ID пользователей, запустивших бота (для рассылки)

# Веб-сервер для прохождения проверки портов на Render
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Advanced Talk Bot is running!")

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
    # Автоматически сохраняем пользователя в базу рассылки
    users_db.add(message.chat.id)
    
    welcome_text = (
        f"Привет! Я твой продвинутый разговорный бот. 🤖\n\n"
        f"Учись общаться со мной в групповых чатах, а здесь ты можешь посмотреть текущее состояние системы.\n\n"
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
    # Возвращаем в меню управления шансом с обновленным значением
    show_chance_menu(call)


# ================= РАБОТА В ЧАТАХ (ОБУЧЕНИЕ И РАЗГОВОРЫ) =================

@bot.message_handler(commands=['сброс', 'reset'], func=lambda msg: msg.chat.type in ['group', 'supergroup'])
def reset_chat_db(message):
    """Сброс накопленной памяти конкретного чата (только для админов группы)."""
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

    # Инициализация базового набора слов, если чат новый
    if chat_id not in chat_histories:
        chat_histories[chat_id] = ["Привет всем!", "Что делаете?", "Жиза", "Понятно", "Интересно..."]

    # Процесс самообучения
    if len(text) > 1 and text not in chat_histories[chat_id]:
        chat_histories[chat_id].append(text)
        if len(chat_histories[chat_id]) > 1500:  # Лимит кэша на чат
            chat_histories[chat_id].pop(0)

    # Проверка шанса на отправку реплики
    if random.random() * 100 > RESPONSE_CHANCE:
        return

    response = random.choice(chat_histories[chat_id])
    
    # Имитация задержки перед отправкой для естественности (1.2 сек)
    threading.Timer(1.2, lambda: bot.send_message(chat_id, response)).start()


if __name__ == "__main__":
    # Запуск фонового веб-сервера для успешного деплоя на Render
    threading.Thread(target=run_health_check, daemon=True).start()
    
    print(f"Бот запущен. Администратор: {ADMIN_USERNAME} ({ADMIN_ID})")
    bot.infinity_polling()
    for prod_id, prod_data in PRODUCTS.items():
        # Создаем кнопку для каждого товара
        button = InlineKeyboardButton(
            text=f"🛍️ {prod_data['name']} — {prod_data['price']}", 
            callback_data=f"view_{prod_id}"
        )
        markup.add(button)
    return markup

# Команда /start
@bot.message_handler(commands=['start'])
def start_cmd(message):
    text = "Добро пожаловать в наш магазин! 🏪\n\nВыведи список товаров ниже и выбери то, что тебе понравилось:"
    bot.send_message(message.chat.id, text, reply_markup=get_main_menu())

# Обработка нажатий на кнопки товаров
@bot.callback_query_handler(func=lambda call: call.data.startswith('view_'))
def view_product(call):
    product_id = call.data.split('_')[1]
    product = PRODUCTS.get(product_id)
    
    if product:
        text = (
            f"📦 *{product['name']}*\n"
            f"💰 *Цена:* {product['price']}\n"
            f"📝 *Описание:* {product['desc']}\n\n"
            f"Чтобы приобрести вещь, нажмите на кнопку ниже и обсудите детали сделки с владельцем."
        )
        
        # Создаем кнопку покупки со ссылкой на владельца
        buy_markup = InlineKeyboardMarkup()
        buy_button = InlineKeyboardButton(text="💬 Написать владельцу для покупки", url=OWNER_LINK)
        back_button = InlineKeyboardButton(text="⬅️ Назад к товарам", callback_data="back_to_list")
        buy_markup.add(buy_button)
        buy_markup.add(back_button)
        
        bot.edit_message_text(
            chat_id=call.message.chat.id, 
            message_id=call.message.message_id, 
            text=text, 
            parse_mode="Markdown", 
            reply_markup=buy_markup
        )

# Кнопка возврата в меню
@bot.callback_query_handler(func=lambda call: call.data == "back_to_list")
def back_to_list(call):
    text = "Выбери товар из списка:"
    bot.edit_message_text(
        chat_id=call.message.chat.id, 
        message_id=call.message.message_id, 
        text=text, 
        reply_markup=get_main_menu()
    )

if __name__ == "__main__":
    # Запуск веб-сервера для Render
    threading.Thread(target=run_health_check, daemon=True).start()
    
    print("Бот-магазин запущен...")
    bot.infinity_polling()
