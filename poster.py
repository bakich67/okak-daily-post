import os
import requests
import json
import random
import xml.etree.ElementTree as ET
from datetime import datetime
import re

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

banned_phrases = [
    "Бонсай-кацуши", "кость", "череп", "вырезал себе", "отрезал себе",
    "Некрополис", "скептик", "фантом", "призрак", "потусторонний",
    "после смерти", "загробн", "Васильева", "Блэр", "самооперация",
    "сам себе", "сделал сам себе операцию"
]

def parse_rss():
    try:
        with open("rss_sources.json", "r") as f:
            sources = json.load(f)["sources"]
    except:
        print("rss_sources.json not found.")
        return []

    all_news = []
    for source in sources:
        try:
            resp = requests.get(source["url"], timeout=10)
            root = ET.fromstring(resp.content)
            for item in root.findall(".//item"):
                title = item.find("title").text if item.find("title") is not None else ""
                link = item.find("link").text if item.find("link") is not None else ""
                desc_elem = item.find("description")
                desc = desc_elem.text if desc_elem is not None and desc_elem.text is not None else ""
                all_news.append({
                    "title": title,
                    "link": link,
                    "description": desc,
                    "source": source["name"],
                    "topic": source["topic"]
                })
        except Exception as e:
            print(f"Failed to parse {source['name']}: {e}")
    return all_news

def wow_score(item):
    score = 0
    title = item.get("title", "")
    if 40 <= len(title) <= 80:
        score += 3
    elif len(title) < 40:
        score += 1
    if re.search(r'\d', title):
        score += 2
    if "?" in title:
        score += 2
    wow_words = ["необычн", "странн", "удивительн", "шокирующ", "рекорд", "впервые", "тайна", "загадка", "феномен", "невероятн", "редк", "unique", "strange", "bizarre", "unusual", "incredible", "first ever", "mystery", "phenomenon"]
    for word in wow_words:
        if word.lower() in title.lower():
            score += 3
            break
    trusted = ["BBC", "Reuters", "Smithsonian", "Atlas Obscura", "History", "Science Daily", "NASA"]
    if any(t in item.get("source", "") for t in trusted):
        score += 2
    return score

def select_best_news(news_list):
    if not news_list:
        return None
    scored = [(wow_score(item), item) for item in news_list]
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_item = scored[0]
    print(f"Лучшая новость (score {best_score}): {best_item['title'][:100]}")
    return best_item if best_score >= 3 else None

def generate_post(news_item):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    cta = random.choice(CALL_TO_ACTIONS)
    real_context = f"Real news: {news_item['title']}. Source: {news_item['source']}. Link: {news_item['link']}. Description: {news_item['description'][:300]}"

    system_prompt = f"""Ты — редактор Telegram-канала «О как».
{real_context}
Напиши пост (600–900 знаков) на основе этой новости.
ЖЁСТКИЕ ПРАВИЛА:
- Факт должен быть точным. НИКАКИХ выдумок.
- Не обобщай сведения о целых народах.
- Стиль: жёсткий, короткие формулировки, максимум 3-4 предложения в абзаце, никаких комплиментов, лести, мотивационных фраз. Простые слова, как умный человек рассказывает другу.
- Ты пишешь СВЯЗНЫЙ текст, а не список. Никаких "Заголовок:", "Факт:", "Объяснение:" — просто рассказ.
- Структура внутри текста:
  1. Первое предложение — интрига или вопрос.
  2. Дальше — неожиданный факт и простое объяснение.
  3. Короткая шутка или живой образ.
  4. Доказательство (источник, дата, ссылка).
  5. В конце — ОДИН призыв к действию: «{cta}»
  6. Подпись: «О как»
- Главный критерий: «Захочет ли человек переслать это другу или рассказать за столом?»"""

    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Напиши пост для канала «О как» на основе предоставленной новости."}
        ],
        "temperature": 0.5,
        "max_tokens": 1200
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        raise Exception(f"Groq error: {response.text}")
    content = response.json()["choices"][0]["message"]["content"].strip()

    if not content or len(content) < 50:
        print("Пустой ответ от Groq.")
        return None

    for phrase in banned_phrases:
        if phrase.lower() in content.lower():
            print(f"Пост отклонён: содержит запрещённую тему '{phrase}'.")
            return None

    content = re.sub(r'\n*О как\s*$', '', content).rstrip()
    content = content + "\n\nО как"
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
    all_news = parse_rss()
    print(f"Найдено новостей из RSS: {len(all_news)}")
    best_news = select_best_news(all_news)
    if best_news is None:
        print("Нет новости с достаточным вау-эффектом. Пост не публикуется.")
    else:
        post = generate_post(best_news)
        if post is None:
            print("Пост не опубликован.")
        else:
            print("Сгенерирован пост:\n", post)
            send_to_telegram(post)
            print("Пост отправлен в канал")
