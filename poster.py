import os
import requests
import json

# ---------- Секреты ----------
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]
DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]

# ---------- Генерация поста через DeepSeek ----------
def generate_post():
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    system_prompt = """Ты — редактор Telegram-канала «О как».
Твоя задача: найти и описать одну необычную, проверяемую историю (странный факт, забытое изобретение, наука, культура, религия, курьёз).
Правила:
- Факт должен быть точным, не выдумывай.
- Не обобщай сведения о целых народах.
- Если информация спорная — напиши «утверждается» и предложи не публиковать без проверки.
- Стиль: жёсткий, короткие формулировки, максимум 3-4 предложения в абзаце, никаких комплиментов, лести, мотивационных фраз. Простые слова, как умный человек рассказывает другу.
- Структура:
  1. Заголовок-вопрос или интрига (до 70 символов).
  2. Неожиданный факт.
  3. Простое объяснение.
  4. Короткая шутка или образ.
  5. Доказательство (источник, дата, страна, ссылка).
  6. Фраза в конце, вызывающая комментарии (без лести).
- Подпись в конце: «О как»
- Длина текста: 600–900 знаков.
- Главный критерий: «Захочет ли человек переслать это другу или рассказать за столом?»"""

    user_prompt = "Найди и опиши одну необычную историю для канала «О как» по заданной структуре. Укажи источник, дату, страну."

    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 1200
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        raise Exception(f"DeepSeek error: {response.text}")
    return response.json()["choices"][0]["message"]["content"].strip()

# ---------- Отправка в Telegram ----------
def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }
    r = requests.post(url, json=payload)
    if r.status_code != 200:
        raise Exception(f"Telegram error: {r.text}")

# ---------- Главный блок ----------
if __name__ == "__main__":
    post = generate_post()
    print("Сгенерирован пост:\n", post)
    send_to_telegram(post)
    print("Пост отправлен в канал")
