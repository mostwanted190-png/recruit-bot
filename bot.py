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

    if text == "/start":
        keyboard = {"keyboard": [[v] for v in VACANCIES], "resize_keyboard": True}
        send_message(chat_id, "Выберите вакансию:", keyboard)
        set_step(user_id, 1)
        return {"ok": True}

    # ===== ШАГ 1: ВАКАНСИЯ =====
    if step == 1:
        update_field(user_id, "specialization", text)
        send_message(chat_id, "Введите ФИО:")
        set_step(user_id, 2)
        return {"ok": True}

    # ===== ШАГ 2: ФИО =====
    if step == 2:
        update_field(user_id, "fio", text)
        send_message(chat_id, "Дата рождения (дд.мм.гггг):")
        set_step(user_id, 3)
        return {"ok": True}

    # ===== ШАГ 3: ДАТА РОЖДЕНИЯ =====
    if step == 3:
        update_field(user_id, "birth", text)
        send_message(chat_id, "Город проживания:")
        set_step(user_id, 4)
        return {"ok": True}

    # ===== ШАГ 4: ГОРОД =====
    if step == 4:
        update_field(user_id, "city", text)
        send_message(chat_id, "Есть водительское удостоверение? (да/нет)")
        set_step(user_id, 5)
        return {"ok": True}

    # ===== ШАГ 5: ПРАВА =====
    if step == 5:
        update_field(user_id, "license", text)
        send_message(chat_id, "Опыт работы (лет и где работали):")
        set_step(user_id, 6)
        return {"ok": True}

    # ===== ШАГ 6: ОПЫТ =====
    if step == 6:
        update_field(user_id, "experience", text)
        send_message(chat_id, "Когда готовы приступить к работе?")
        set_step(user_id, 7)
        return {"ok": True}

    # ===== ШАГ 7: ДАТА ВЫХОДА =====
    if step == 7:
        update_field(user_id, "start_date", text)
        send_message(chat_id, "Введите контактный телефон:")
        set_step(user_id, 8)
        return {"ok": True}

    # ===== ШАГ 8: ТЕЛЕФОН =====
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

        send_message(chat_id, "✅ Спасибо! Ваша анкета отправлена менеджеру.")
        set_step(user_id, 0)
        return {"ok": True}

    return {"ok": True}
