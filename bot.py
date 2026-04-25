import os
import sqlite3
import requests
from fastapi import FastAPI, Request
from groq import Groq
from datetime import datetime

app = FastAPI()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
groq = Groq(api_key=GROQ_API_KEY)

ADMIN_ID = 6288084946

# ===== БАЗА =====

conn = sqlite3.connect("dialog_bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    first_name TEXT,
    username TEXT,
    phone TEXT
)
""")

conn.commit()

# ===== ТЕКСТЫ =====

COMPANY_INFO = (
    "🏢 ООО «Маркетинг‑технолоджи»\n\n"
    "Работаем с 2015 года в сфере рекрутинга и подбора персонала.\n"
    "Сотрудничаем с крупными работодателями."
)

CONDITIONS_INFO = (
    "💰 Условия работы:\n\n"
    "✅ Зарплата от 260 000 руб.\n"
    "✅ Социальный пакет\n"
    "✅ Полная поддержка государства\n"
    "✅ Горячее 3‑разовое питание\n"
    "✅ Комфортное размещение в центре города (во время обучения)\n"
    "✅ Проводится обучение от 2 месяцев"
)   "✅ УВБД"

MANAGER_CONTACT = (
    "📞 Связаться с менеджером:\n\n"
    "Артём Викторович\n"
    "Телефон: +7 919 888 3009"
)

# ===== МЕНЮ =====

def main_menu():
    return {
        "keyboard": [
            ["💼 Вакансии", "🏢 О компании"],
            ["💰 Условия", "📞 Связаться с менеджером"]
        ],
        "resize_keyboard": True
    }

# ===== УТИЛИТЫ =====

def send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(f"{TELEGRAM_API}/sendMessage", json=payload)

def notify_admin(user_id, first_name, username):
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    text = (
        f"📞 Кандидат запросил менеджера\n\n"
        f"🕒 {now}\n"
        f"Имя: {first_name}\n"
        f"Username: @{username}\n"
        f"ID: {user_id}"
    )
    send_message(ADMIN_ID, text)

# ===== WEBHOOK =====

@app.post("/")
async def webhook(request: Request):
    data = await request.json()

    if "message" not in data:
        return {"ok": True}

    msg = data["message"]
    chat_id = msg["chat"]["id"]
    user_id = msg["from"]["id"]
    first_name = msg["from"].get("first_name", "")
    username = msg["from"].get("username", "")
    text = msg.get("text", "")

    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, first_name, username) VALUES (?, ?, ?)",
        (user_id, first_name, username)
    )
    conn.commit()

    if text == "/start":
        send_message(
            chat_id,
            f"Здравствуйте, {first_name}! 👋\n\n"
            "Я HR‑бот компании.\n"
            "Помогу вам разобраться с вакансиями.",
            main_menu()
        )
        return {"ok": True}

    if text == "🏢 О компании":
        send_message(chat_id, COMPANY_INFO, main_menu())
        return {"ok": True}

    if text == "💰 Условия":
        send_message(chat_id, CONDITIONS_INFO, main_menu())
        return {"ok": True}

    if text == "📞 Связаться с менеджером":
        send_message(chat_id, MANAGER_CONTACT, main_menu())
        notify_admin(user_id, first_name, username)
        return {"ok": True}

    if text == "💼 Вакансии":
        send_message(
            chat_id,
            "Открытые вакансии:\n"
            "• Крановщик\n"
            "• Водитель (кат. C или D)\n"
            "• Электрик\n"
            "• Повар\n"
            "• Каменщик\n"
            "• Экскаваторщик\n"
            "• Газоэлектросварщик\n\n"
            "• Оператор БПЛА"
            "Расскажите о своём опыте.",
            main_menu()
        )
        return {"ok": True}

    # ===== AI ДИАЛОГ =====

    try:
        response = groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Ты HR-бот. Веди живой диалог, помогай кандидату."},
                {"role": "user", "content": text}
            ],
            max_tokens=400,
        )

        reply = response.choices[0].message.content
        send_message(chat_id, reply, main_menu())

    except Exception:
        send_message(chat_id, "⚠ Произошла ошибка. Попробуйте позже.", main_menu())

    return {"ok": True}
