import os
import sqlite3
import requests
import re
from datetime import datetime
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
    username TEXT,
    phone TEXT,
    score INTEGER DEFAULT 0,
    status TEXT DEFAULT 'new'
)
""")

conn.commit()

# ===== СИСТЕМНЫЙ ПРОМПТ =====

SYSTEM_PROMPT = """
Ты — HR-бот компании.
Твоя задача — оценить кандидата.

Правила:
1. Веди естественный диалог.
2. Выясни опыт, мотивацию, готовность.
3. Оцени кандидата по шкале 0–10.
4. В КОНЦЕ ответа добавь метку вида:
[SCORE:7]

Не объясняй балл пользователю.
Пиши метку только один раз в конце.
"""

# ===== УТИЛИТЫ =====

def send_message(chat_id, text):
    requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={"chat_id": chat_id, "text": text}
    )

def notify_admin(text):
    send_message(ADMIN_ID, text)

def extract_score(text):
    match = re.search(r"\[SCORE:(\d+)\]", text)
    if match:
        return int(match.group(1))
    return None

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
        send_message(chat_id,
                     "Здравствуйте! 👋\n\n"
                     "Расскажите немного о своём опыте работы.")
        return {"ok": True}

    # ===== AI =====

    response = groq.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ],
        max_tokens=400,
    )

    ai_reply = response.choices[0].message.content

    score = extract_score(ai_reply)

    clean_reply = re.sub(r"\[SCORE:\d+\]", "", ai_reply).strip()

    send_message(chat_id, clean_reply)

    if score is not None:
        cursor.execute(
            "UPDATE users SET score = ? WHERE user_id = ?",
            (score, user_id)
        )
        conn.commit()

        # ✅ ГОРЯЧИЙ
        if score >= 7:
            cursor.execute(
                "UPDATE users SET status = 'approved' WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()

            send_message(chat_id,
                         "✅ Вы нам подходите!\n\n"
                         "Свяжитесь с менеджером:\n"
                         "Артём Викторович\n"
                         "📞 +7 919 888 3009")

            notify_admin(
                f"🔥 ГОРЯЧИЙ кандидат\n"
                f"Имя: {first_name}\n"
                f"Username: @{username}\n"
                f"ID: {user_id}\n"
                f"Score: {score}"
            )

        # ⚠ Средний
        elif 4 <= score <= 6:
            notify_admin(
                f"⚠ Средний кандидат\n"
                f"Имя: {first_name}\n"
                f"ID: {user_id}\n"
                f"Score: {score}"
            )

        # ❌ Слабый
        else:
            cursor.execute(
                "UPDATE users SET status = 'rejected' WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()

            notify_admin(
                f"❌ Слабый кандидат\n"
                f"Имя: {first_name}\n"
                f"ID: {user_id}\n"
                f"Score: {score}"
            )

    return {"ok": True}
