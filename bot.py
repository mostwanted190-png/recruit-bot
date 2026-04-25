import os
import sqlite3
import requests
from datetime import datetime
from fastapi import FastAPI, Request
from groq import Groq

app = FastAPI()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
groq = Groq(api_key=GROQ_API_KEY)

ADMIN_ID = 6288084946

MANAGER_CONTACT = "Ваш менеджер: Иван Иванов\nТелефон: +7 (999) 123-45-67\nTelegram: @manager"

# ===== БАЗА =====

conn = sqlite3.connect("recruit.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS candidates (
    user_id INTEGER PRIMARY KEY,
    first_name TEXT,
    username TEXT,
    status TEXT DEFAULT 'new',
    messages_count INTEGER DEFAULT 0,
    created_at TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    role TEXT,
    content TEXT,
    created_at TEXT
)
""")

conn.commit()

# ===== СИСТЕМНЫЙ ПРОМПТ =====

SYSTEM_PROMPT = """
Ты — умный HR-бот компании. Твоя задача — вести диалог с кандидатом.

Правила:
1. Веди естественный, дружелюбный диалог.
2. Задавай вопросы по одному.
3. Выясни:
   - Имя
   - Опыт работы
   - Какую должность ищет
   - Город проживания
   - Готовность к графику
   - Мотивацию

4. Когда соберёшь достаточно информации, оцени кандидата.

5. Если кандидат подходит — в самом конце ответа добавь метку: [APPROVED]
6. Если кандидат явно не подходит — добавь метку: [REJECTED]
7. Если нужно ещё информации — просто продолжай диалог.

8. Метки [APPROVED] и [REJECTED] пиши ТОЛЬКО в самом конце.
9. Не показывай метки кандидату в тексте сообщения.

Отвечай на русском языке.
"""

# ===== УТИЛИТЫ =====

def send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(f"{TELEGRAM_API}/sendMessage", json=payload)

def notify_admin(text):
    send_message(ADMIN_ID, text)

def get_candidate(user_id):
    cursor.execute("SELECT status FROM candidates WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if not result:
        return None
    return result[0]

def save_history(user_id, role, content):
    cursor.execute(
        "INSERT INTO history (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (user_id, role, content, datetime.now().isoformat())
    )
    conn.commit()

def get_history(user_id, limit=10):
    cursor.execute(
        "SELECT role, content FROM history WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit)
    )
    rows = cursor.fetchall()
    return [{"role": r, "content": c} for r, c in reversed(rows)]

# ===== ГЛАВНОЕ МЕНЮ =====

def main_menu():
    return {
        "keyboard": [
            ["📋 Вакансии", "📞 Контакты"],
            ["❓ О компании"]
        ],
        "resize_keyboard": True
    }

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

    # Регистрация нового кандидата
    status = get_candidate(user_id)
    if status is None:
        cursor.execute(
            "INSERT INTO candidates (user_id, first_name, username, created_at) VALUES (?, ?, ?, ?)",
            (user_id, first_name, username, datetime.now().isoformat())
        )
        conn.commit()
        status = "new"

        notify_admin(
            f"👤 Новый кандидат!\n"
            f"Имя: {first_name}\n"
            f"Username: @{username}\n"
            f"ID: {user_id}"
        )

    # Если уже одобрен
    if status == "approved":
        send_message(chat_id,
                     f"✅ Вы уже прошли отбор!\n\n{MANAGER_CONTACT}")
        return {"ok": True}

    # Если отклонён
    if status == "rejected":
        send_message(chat_id,
                     "К сожалению, сейчас мы не можем предложить вам подходящую позицию.\n"
                     "Попробуйте позже!")
        return {"ok": True}

    # Команда /start
    if text == "/start":
        send_message(chat_id,
                     f"Здравствуйте, {first_name}! 👋\n\n"
                     "Я HR-бот компании.\n"
                     "Помогу вам найти подходящую вакансию.\n\n"
                     "Расскажите о себе или выберите пункт меню.",
                     main_menu())
        return {"ok": True}

    # Кнопки меню
    if text == "📋 Вакансии":
        send_message(chat_id,
                     "📋 Открытые вакансии:\n\n"
                     "1. Менеджер по продажам\n"
                     "2. Специалист поддержки\n"
                     "3. Маркетолог\n\n"
                     "Напишите, какая вакансия вас интересует.",
                     main_menu())
        return {"ok": True}

    if text == "📞 Контакты":
        send_message(chat_id,
                     "📞 Наши контакты:\n\n"
                     "Сайт: example.com\n"
                     "Email: hr@example.com",
                     main_menu())
        return {"ok": True}

    if text == "❓ О компании":
        send_message(chat_id,
                     "🏢 Мы — стабильная компания.\n"
                     "Работаем с 2010 года.\n"
                     "Ищем талантливых сотрудников!",
                     main_menu())
        return {"ok": True}

    # ===== АДМИН =====

    if text == "/admin" and user_id == ADMIN_ID:
        cursor.execute("SELECT COUNT(*) FROM candidates")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM candidates WHERE status = 'approved'")
        approved = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM candidates WHERE status = 'rejected'")
        rejected = cursor.fetchone()[0]

        send_message(chat_id,
                     f"⚙ Админ-панель:\n\n"
                     f"👥 Всего: {total}\n"
                     f"✅ Одобрено: {approved}\n"
                     f"❌ Отклонено: {rejected}\n\n"
                     f"/candidates — список кандидатов")
        return {"ok": True}

    if text == "/candidates" and user_id == ADMIN_ID:
        cursor.execute(
            "SELECT user_id, first_name, username, status FROM candidates ORDER BY rowid DESC LIMIT 20"
        )
        rows = cursor.fetchall()
        result = "👥 Кандидаты:\n\n"
        for r in rows:
            result += f"ID:{r[0]} | {r[1]} | @{r[2]} | {r[3]}\n"
        send_message(chat_id, result)
        return {"ok": True}

    # ===== AI ДИАЛОГ =====

    save_history(user_id, "user", text)
    history = get_history(user_id)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    try:
        response = groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=400,
            temperature=0.7,
        )

        ai_reply = response.choices[0].message.content

        # Проверяем решение ИИ
        if "[APPROVED]" in ai_reply:
            clean_reply = ai_reply.replace("[APPROVED]", "").strip()
            save_history(user_id, "assistant", clean_reply)

            cursor.execute("UPDATE candidates SET status = 'approved' WHERE user_id = ?", (user_id,))
            conn.commit()

            send_message(chat_id, clean_reply)
            send_message(chat_id, f"✅ Вы нам подходите!\n\n{MANAGER_CONTACT}")

            notify_admin(
                f"✅ Кандидат одобрен!\n"
                f"Имя: {first_name}\n"
                f"Username: @{username}\n"
                f"ID: {user_id}"
            )

        elif "[REJECTED]" in ai_reply:
            clean_reply = ai_reply.replace("[REJECTED]", "").strip()
            save_history(user_id, "assistant", clean_reply)

            cursor.execute("UPDATE candidates SET status = 'rejected' WHERE user_id = ?", (user_id,))
            conn.commit()

            send_message(chat_id, clean_reply)

            notify_admin(
                f"❌ Кандидат отклонён!\n"
                f"Имя: {first_name}\n"
                f"Username: @{username}\n"
                f"ID: {user_id}"
            )

        else:
            clean_reply = ai_reply.replace("[CONTINUE]", "").strip()
            save_history(user_id, "assistant", clean_reply)
            send_message(chat_id, clean_reply, main_menu())

        cursor.execute(
            "UPDATE candidates SET messages_count = messages_count + 1 WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()

    except Exception as e:
        send_message(chat_id, "⚠ Ошибка. Попробуйте позже.")

    return {"ok": True}
