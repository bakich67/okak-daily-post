import os
import requests
import json
import random

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

CALL_TO_ACTIONS = [
    "А вы бы поступили так же? Напишите в комментариях.",
    "Как думаете, кто здесь неправ?",
    "Было ли у вас что-то похожее?",
    "Отправьте это тому, кто точно скажет: «О как!»",
    "Подпишитесь, чтобы не пропускать необычные истории.",
    "Хотите ещё такие случаи? Поставьте реакцию 👍",
    "Сохраните, чтобы показать друзьям."
]

def generate_post():
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    cta = random.choice(CALL_TO_ACTIONS)
    banned_phrases = [
        "Бонсай-кацуши", "кость", "череп", "вырезал себе", "отрезал себе",
        "Некрополис", "скептик", "фантом", "призрак", "потусторонний",
        "после смерти", "загробн", "Васильева", "Блэр", "самооперация",
        "сам себе", "сделал сам себе операцию"
    ]
    mandatory_sources = ["wikipedia", "britannica", "nature", "science", "bbc", "reuters", "ap", "nasa", "smithsonian", "history"]

    system_prompt = f"""Ты — редактор Telegram-канала «О как».
Твоя задача: Найти и описать одну необычную, РЕАЛЬНУЮ, проверяемую историю.
Ты имеешь дело с источниками, которым можно верить. 
НИ В КОЕМ СЛУЧАЕ не выдумывай учёных, врачей, книги и статьи.
Ты можешь использовать ТОЛЬКО факты, подтверждённые авторитетными источниками: Wikipedia, Britannica, Nature, Science, BBC, Reuters, AP News, NASA, Smithsonian, History Channel.
Если история не подтверждена такими источниками — НЕ ПИШИ пост.
Если не можешь найти реальную историю из надёжного источника — верни "Нет подходящей истории".
ЖЁСТКИЕ ПРАВИЛА:
- Факт должен быть точным. НИКАКИХ выдумок.
- Не обобщай сведения о целых народах.
- Если информация хоть немного сомнительная — НЕ ПИШИ пост. Лучше промолчать, чем соврать.
- Стиль: жёсткий, короткие формулировки, максимум 3-4 предложения в абзаце, никаких комплиментов, лести, мотивационных фраз. Простые слова, как умный человек рассказывает другу.
- Источник ОБЯЗАТЕЛЕН: реальная книга, статья, исследование с автором и годом. НИКАКИХ выдуманных книг.
- Ты пишешь СВЯЗНЫЙ текст, а не список. Никаких "Заголовок:", "Факт:", "Объяснение:" — просто рассказ.
- Структура внутри текста:
  1. Первое предложение — интрига или вопрос.
  2. Дальше — неожиданный факт и простое объяснение.
  3. Короткая шутка или живой образ.
  4. Доказательство (источник, дата, страна, ссылка).
  5. В конце — ОДИН призыв к действию: «{cta}»
  6. Подпись: «О как»
- Длина текста: 600–900 знаков.
- Главный критерий: «Захочет ли человек переслать это другу или рассказать за столом?»
- ЕСЛИ НЕТ ПОДХОДЯЩЕЙ НОВОСТИ — верни пустой ответ (ничего не пиши)."""

    user_prompt = "Найди РЕАЛЬНУЮ необычную историю для канала «О как». Проверь источник. Если история выдумана или источник ненадёжен — не пиши ничего."

    data = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.5,
        "max_tokens": 1200
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        raise Exception(f"Groq error: {response.text}")
    content = response.json()["choices"][0]["message"]["content"].strip()

    if not content or len(content) < 50 or "нечего" in content.lower():
        print("Нет подходящей новости. Пост не публикуется.")
        return None

    if not any(src in content.lower() for src in mandatory_sources):
        print("Пост отклонён: нет ссылки на авторитетный источник.")
        return None

    for phrase in banned_phrases:
        if phrase.lower() in content.lower():
            print(f"Пост отклонён: содержит запрещённую тему '{phrase}'.")
            return None

    if not content.endswith("О как"):
        content = content.rstrip() + "\n\nО как"
    return content

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    r = requests.post(url, json=payload)
    if r.status_code != 200:
        raise Exception(f"Telegram error: {r.text}")

if __name__ == "__main__":
    post = generate_post()
    if post is None:
        print("Пост не опубликован: нет проверенной истории.")
    else:
        print("Сгенерирован пост:\n", post)
        send_to_telegram(post)
        print("Пост отправлен в канал")
