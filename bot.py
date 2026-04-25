import os
import sqlite3
import requests
from fastapi import FastAPI, Request
from groq import Groq

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
    username TEXT
)
""")

conn.commit()

# ===== ИНФОРМАЦИЯ О КОМПАНИИ =====

COMPANY_INFO = (
    "🏢 ООО «Маркетинг‑технолоджи»\n\n"
    "Работаем с 2015 года в сфере рекрутинга и подбора персонала.\n\n"
    "✅ Зарплата от 260 000 руб.\n"
    "✅ Социальный пакет\n"
    "✅ Полная поддержка государства\n"
    "✅ Официальное трудоустройство\n\n"
    "Подбираем сотрудников по всей России."
)

JOB_BENEFITS = (
    "💼 Условия работы:\n\n"
    "• Зарплата от 260 000 руб.\n"
    "• Социальный пакет\n"
    "• Государственная поддержка\n"
    "• Официальное оформление\n"
    "• Возможность карьерного роста"
)

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

def notify_admin(text):
    send_message(ADMIN_ID, text)

# ===== СИСТЕМНЫЙ ПРОМПТ =====

SYSTEM_PROMPT = """
Ты — HR-бот компании «Маркетинг-технолоджи».

Веди живой диалог с кандидатом:
- интересуйся его опытом
- рассказывай об условиях работы
- подчёркивай зарплату от 260 000 руб.
- упоминай социальный пакет и поддержку

Будь уверенным, но не навязчивым.
Отвечай на русском языке.
"""

# ===== WEBHOOK =====

@app.post("/")
async def webhook(request: Request):
    data = await request.json()

    if "message" not in data:
        return {"ok": True}

    message = data["message"]
    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]
    first_name = message["from"].get("first_name", "")
    username = message["from"].get("username", "")
    text = message.get("text", "")

    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, first_name, username) VALUES (?, ?, ?)",
        (user_id, first_name, username)
    )
    conn.commit()

    # ===== СТАРТ =====
    if text == "/start":
        send_message(
            chat_id,
            f"Здравствуйте, {first_name}! 👋\n\n"
            "Мы предлагаем стабильную работу с высокой оплатой.\n"
            "Зарплата от 260 000 руб. + соцпакет.\n\n"
            "Выберите пункт меню:",
            main_menu()
        )
        return {"ok": True}

    # ===== КНОПКИ =====

    if text == "🏢 О компании":
        send_message(chat_id, COMPANY_INFO, main_menu())
        return {"ok": True}

    if text == "💰 Условия":
        send_message(chat_id, JOB_BENEFITS, main_menu())
        return {"ok": True}

    if text == "📞 Связаться с менеджером":
        send_message(chat_id, MANAGER_CONTACT, main_menu())
        notify_admin(
            f"📞 Кандидат запросил менеджера:\n"
            f"{first_name} (@{username})\nID: {user_id}"
        )
        return {"ok": True}

    if text == "💼 Вакансии":
        send_message(
            chat_id,
            "Открытые вакансии:\n\n"
            "• Крановщик\n"
            "• Водитель (кат. C или D)\n"
            "• Электрик\n"
            "• Повар\n"
            "• Каменщик\n"
            "• Экскаваторщик\n"
            "• Газоэлектросварщик\n\n"
            "• Оператор БПЛА\n\n"
            "Какая вакансия вас интересует?",
            main_menu()
        )
        return {"ok": True}

    # ===== AI ДИАЛОГ =====

    try:
        response = groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            max_tokens=500,
        )

        reply = response.choices[0].message.content
        send_message(chat_id, reply, main_menu())

    except Exception:
        send_message(chat_id, "⚠ Произошла ошибка. Попробуйте позже.", main_menu())

    return {"ok": True}
