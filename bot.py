import os
import sqlite3
import requests
from fastapi import FastAPI, Request

app = FastAPI()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

ADMIN_ID = 6288084946

# ===== БАЗА =====

conn = sqlite3.connect("recruit.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS forms (
    user_id INTEGER PRIMARY KEY,
    step INTEGER DEFAULT 0,
    fio TEXT,
    birth TEXT,
    city TEXT,
    license TEXT,
    experience TEXT,
    specialization TEXT,
    start_date TEXT,
    phone TEXT
)
""")

conn.commit()

# ===== ВАКАНСИИ =====

VACANCIES = [
    "Крановщик",
    "Водитель (кат. C или D)",
    "Электрик",
    "Повар",
    "Каменщик",
    "Экскаваторщик",
    "Газоэлектросварщик"
]

# ===== УТИЛИТЫ =====

def send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(f"{TELEGRAM_API}/sendMessage", json=payload)

def notify_admin(text):
    send_message(ADMIN_ID, text)

def get_user(user_id):
    cursor.execute("SELECT step FROM forms WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO forms (user_id) VALUES (?)", (user_id,))
        conn.commit()
        return 0
    return row[0]

def update_field(user_id, field, value):
    cursor.execute(f"UPDATE forms SET {field} = ? WHERE user_id = ?", (value, user_id))
    conn.commit()

def set_step(user_id, step):
    cursor.execute("UPDATE forms SET step = ? WHERE user_id = ?", (step, user_id))
    conn.commit()

# ===== ГЛАВНОЕ МЕНЮ =====

def main_menu():
    return {
        "keyboard": [
            ["📝 Начать анкету"],
            ["📞 Связаться с менеджером"],
            ["🏢 О компании"]
        ],
        "resize_keyboard": True
    }

# ===== WEBHOOK =====

@app.post("/")
async def webhook(request: Request):
    data = await request.json()

    if "message" not in data:
        return {"ok": True}

    msg = data["message"]
    chat_id = msg["chat"]["id"]
    user_id = msg["from"]["id"]
    text = msg.get("text", "")

    step = get_user(user_id)

    # ===== ПЕРВОЕ СООБЩЕНИЕ =====
    if step == 0 and text not in ["📝 Начать анкету"]:
        send_message(
            chat_id,
            "Здравствуйте! 👋\n\n"
            "Мы поможем вам трудоустроиться.\n\n"
            "Выберите действие:",
            main_menu()
        )
        return {"ok": True}

    # ===== О КОМПАНИИ =====
    if text == "🏢 О компании":
        send_message(
            chat_id,
            "🏢 ООО «Маркетинг‑технолоджи»\n\n"
            "Работаем с 2015 года в сфере рекрутинга и подбора персонала.\n"
            "Сотрудничаем с крупными работодателями по всей России.\n\n"
            "Мы помогаем кандидатам быстро найти работу, а компаниям — сотрудников.",
            main_menu()
        )
        return {"ok": True}

    # ===== СВЯЗЬ С МЕНЕДЖЕРОМ =====
    if text == "📞 Связаться с менеджером":
        send_message(
            chat_id,
            "📞 Контакт менеджера:\n\n"
            "Иван Иванов\n"
            "Телефон: +7 (999) 123‑45‑67\n"
            "Telegram: @manager_username",
            main_menu()
        )
        return {"ok": True}

    # ===== НАЧАТЬ АНКЕТУ =====
    if text == "📝 Начать анкету":
        keyboard = {"keyboard": [[v] for v in VACANCIES], "resize_keyboard": True}
        send_message(chat_id, "Выберите вакансию:", keyboard)
        set_step(user_id, 1)
        return {"ok": True}

    # ===== АНКЕТА =====
    if step == 1:
        update_field(user_id, "specialization", text)
        send_message(chat_id, "Введите ФИО:")
        set_step(user_id, 2)
        return {"ok": True}

    if step == 2:
        update_field(user_id, "fio", text)
        send_message(chat_id, "Дата рождения (дд.мм.гггг):")
        set_step(user_id, 3)
        return {"ok": True}

    if step == 3:
        update_field(user_id, "birth", text)
        send_message(chat_id, "Город проживания:")
        set_step(user_id, 4)
        return {"ok": True}

    if step == 4:
        update_field(user_id, "city", text)
        send_message(chat_id, "Есть водительское удостоверение? (да/нет)")
        set_step(user_id, 5)
        return {"ok": True}

    if step == 5:
        update_field(user_id, "license", text)
        send_message(chat_id, "Опыт работы:")
        set_step(user_id, 6)
        return {"ok": True}

    if step == 6:
        update_field(user_id, "experience", text)
        send_message(chat_id, "Когда готовы приступить к работе?")
        set_step(user_id, 7)
        return {"ok": True}

    if step == 7:
        update_field(user_id, "start_date", text)
        send_message(chat_id, "Введите контактный телефон:")
        set_step(user_id, 8)
        return {"ok": True}

    if step == 8:
        update_field(user_id, "phone", text)

        cursor.execute("""
        SELECT fio, birth, city, license, experience, specialization, start_date, phone
        FROM forms WHERE user_id = ?
        """, (user_id,))
        form = cursor.fetchone()

        text_admin = (
            "📋 Новая анкета:\n\n"
            f"Вакансия: {form[5]}\n"
            f"ФИО: {form[0]}\n"
            f"Дата рождения: {form[1]}\n"
            f"Город: {form[2]}\n"
            f"Права: {form[3]}\n"
            f"Опыт: {form[4]}\n"
            f"Готов приступить: {form[6]}\n"
            f"Телефон: {form[7]}\n"
            f"User ID: {user_id}"
        )

        notify_admin(text_admin)

        send_message(
            chat_id,
            "✅ Спасибо! Ваша анкета отправлена менеджеру.\n"
            "С вами свяжутся в ближайшее время.",
            main_menu()
        )

        set_step(user_id, 0)
        return {"ok": True}

    return {"ok": True}
