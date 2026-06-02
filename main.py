import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Бот автоматически возьмет токен из настроек Render
bot = telebot.TeleBot(os.getenv("BOT_TOKEN"))

# Ссылка на создателя/владельца (замени 'твой_юзернейм' на свой ник без @)
# Например: 'https://t.me/durov'
OWNER_LINK = "https://t.me/longer9829" 

# Наша база товаров (id, название, цена, описание)
PRODUCTS = {
    "1": {"name": "Худи 'Regards DLC'", "price": "2500 руб.", "desc": "Ограниченная серия, размер L. Отличное качество."},
    "2": {"name": "Кепка 'Relict'", "price": "1200 руб.", "desc": "Черная кепка с фирменным логотипом."},
    "3": {"name": "Стикерпак Minecraft", "price": "300 руб.", "desc": "Набор виниловых стикеров, не выцветают."}
}

# Веб-сервер для прохождения проверки Render (чтобы бот не падал)
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Shop Bot is running!")

def run_health_check():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# Главное меню в виде инлайн-кнопок
def get_main_menu():
    markup = InlineKeyboardMarkup()
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
