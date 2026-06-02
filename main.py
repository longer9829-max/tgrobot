import os
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import telebot
from google import genai

# Инициализация
bot = telebot.TeleBot(os.getenv("BOT_TOKEN"))
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
ai_client = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None

# Настройка системного промпта для ИИ
SYSTEM_INSTRUCTION = (
    "Ты — RELICT AI, продвинутый и полезный ИИ-помощник и модератор в Telegram-чате. "
    "Твоя цель — помогать пользователям, отвечать на их вопросы по делу, поддерживать общение "
    "и следить, чтобы в чате не было откровенного неадекватного спама. Общайся уверенно, дружелюбно, но без лишней воды."
)

# Хранилище для истории сообщений (чтобы делать выжимку чата)
chat_logs = {}

# Web-server для поддержания аптайма на Render
class WebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"RELICT AI Chatbot is alive!")

def run_server():
    port = int(os.getenv("PORT", 10000))
    HTTPServer(("0.0.0.0", port), WebHandler).serve_forever()

threading.Thread(target=run_server, daemon=True).start()


# ================= 1. ФУНКЦИЯ: ВЫЖИМКА ЧАТА (/summary) =================

@bot.message_handler(commands=['summary'])
def get_chat_summary(message):
    """ Делает краткую выжимку последних сообщений в группе """
    chat_id = message.chat.id
    
    if chat_id not in chat_logs or len(chat_logs[chat_id]) < 5:
        bot.reply_to(message, "📋 В памяти пока слишком мало сообщений для анализа. Пообщайтесь еще немного!")
        return

    status = bot.reply_to(message, "📥 _Анализирую контекст последних разговоров..._", parse_mode="Markdown")
    
    # Собираем лог в одну строку
    context_text = "\n".join(chat_logs[chat_id][-80:]) # Берем последние 80 реплик
    
    prompt = (
        f"Прочитай эту переписку из чата и сделай краткую, понятную выжимку на русском языке. "
        f"Напиши тезисно, какие главные темы обсуждались и к чему пришли. Вот текст:\n\n{context_text}"
    )
    
    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        bot.edit_message_text(f"📊 **Главное в чате за последнее время:**\n\n{response.text}", chat_id, status.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ Не удалось обработать лог: `{e}`", chat_id, status.message_id)


# ================= 2. ФУНКЦИЯ: ОТВЕТ НА ВОПРОСЫ (/ask) =================

@bot.message_handler(commands=['ask'])
def ask_ai(message):
    """ Прямой запрос к ИИ в чате """
    query = message.text.replace('/ask', '').strip()
    if not query:
        bot.reply_to(message, "🤔 Напиши вопрос после команды. Пример: `/ask как исправить ошибку в коде?`")
        return

    status = bot.reply_to(message, "⚡ _RELICT AI генерирует ответ..._", parse_mode="Markdown")

    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"{SYSTEM_INSTRUCTION}\n\nПользователь спрашивает: {query}"
        )
        bot.edit_message_text(f"🤖 **RELICT AI:**\n\n{response.text}", chat_id=message.chat.id, message_id=status.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ Ошибка нейросети: `{e}`", chat_id=message.chat.id, message_id=status.message_id)


# ================= 3. ПАССИВНЫЙ МОНИТОРИНГ И АВТООТВЕТЫ =================

@bot.message_handler(func=lambda msg: True, content_types=['text'])
def monitor_and_reply(message):
    chat_id = message.chat.id
    user_name = message.from_user.first_name or "User"
    text = message.text

    # Записываем сообщение в лог для команды /summary
    if chat_id not in chat_logs:
        chat_logs[chat_id] = []
    chat_logs[chat_id].append(f"{user_name}: {text}")
    
    # Ограничиваем размер лога, чтобы не забивать память (храним последние 150 сообщений)
    if len(chat_logs[chat_id]) > 150:
        chat_logs[chat_id].pop(0)

    # Умный автоответ, если бота тегнули, ответили на его сообщение или написали "ии,"
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.username == bot.get_me().username
    is_mentioned = f"@{bot.get_me().username}" in text or text.lower().startswith("ии,")

    if is_reply_to_bot or is_mentioned:
        cleaned_text = text.replace(f"@{bot.get_me().username}", "").replace("ии,", "").strip()
        if not cleaned_text:
            bot.reply_to(message, "Слушаю тебя. Задай свой вопрос!")
            return

        bot.send_chat_action(chat_id, 'typing')
        try:
            response = ai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=f"{SYSTEM_INSTRUCTION}\n\nКонтекст беседы: {user_name} говорит тебе: '{cleaned_text}'. Ответь ему."
            )
            bot.reply_to(message, response.text)
        except Exception as e:
            print(f"Ошибка ИИ: {e}")

# Запуск бота
if __name__ == "__main__":
    print("🚀 Полезный ИИ-Чатбот запущен!")
    bot.infinity_polling()
            
