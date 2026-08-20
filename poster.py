import os
import re
import json
import random
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from dateutil import parser

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

# Актуальная модель Groq
GROQ_MODEL = "openai/gpt-oss-120b"

USED_FILE = "used_items.json"
DEDUP_WINDOW_DAYS = 30
SIMILARITY_THRESHOLD = 0.45

STOPWORDS = {
    "a", "an", "the", "of", "in", "on", "at", "to", "for", "and", "or", "is", "are",
    "was", "were", "this", "that", "with", "from", "it", "its", "as", "be", "has",
    "have", "after", "before", "new", "first", "how", "why", "what", "who", "when",
    "where", "into", "over", "than", "then", "just", "more", "most"
}

POLITICAL_MARKERS = [
    "president", "senator", "congress", "governor", "mayor", "minister",
    "parliament", "election", "white house", "supreme court",
    "президент", "сенатор", "парламент", "министр", "выборы", "конгресс",
    "кремль", "губернатор"
]

RSS_SOURCES_FILE = "rss_sources.json"


# ---------- ДЕДУПЛИКАЦИЯ ----------

def normalize_title(title):
    title = (title or "").lower()
    title = re.sub(r'[^a-zа-яё0-9\s]', ' ', title)
    words = [w for w in title.split() if w not in STOPWORDS and len(w) > 2]
    return " ".join(sorted(set(words)))


def load_used_items():
    if not os.path.exists(USED_FILE):
        return []
    try:
        with open(USED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    cutoff = datetime.utcnow() - timedelta(days=DEDUP_WINDOW_DAYS)
    fresh = []
    for item in data:
        try:
            if parser.parse(item["date"]).replace(tzinfo=None) >= cutoff:
                fresh.append(item)
        except Exception:
            continue
    return fresh


def save_used_items(items):
    with open(USED_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def is_duplicate(title, link, used_items):
    norm_link = (link or "").split("?")[0].rstrip("/")
    new_words = set(normalize_title(title).split())
    for item in used_items:
        old_link = (item.get("link") or "").split("?")[0].rstrip("/")
        if norm_link and old_link and norm_link == old_link:
            return True
        old_words = set(item.get("norm", "").split())
        if new_words and old_words:
            overlap = len(new_words & old_words) / len(new_words | old_words)
            if overlap >= SIMILARITY_THRESHOLD:
                return True
    return False


def mark_used(title, link, used_items):
    used_items.append({
        "title": title,
        "link": link,
        "norm": normalize_title(title),
        "date": datetime.utcnow().isoformat()
    })
    save_used_items(used_items)


def is_political(title, description):
    text = f"{title} {description}".lower()
    return any(marker in text for marker in POLITICAL_MARKERS)


# ---------- ПАРСИНГ RSS ----------

def parse_rss():
    try:
        with open(RSS_SOURCES_FILE, "r", encoding="utf-8") as f:
            sources = json.load(f)["sources"]
    except Exception as e:
        print(f"{RSS_SOURCES_FILE} not found or invalid: {e}")
        return []

    all_items = []
    cutoff_date = datetime.utcnow() - timedelta(days=3)

    for source in sources:
        try:
            resp = requests.get(source["url"], timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            root = ET.fromstring(resp.content)

            items = root.findall(".//item")
            if not items:
                items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

            for item in items:
                title_el = item.find("title")
                link_el = item.find("link")
                desc_el = item.find("description")
                if desc_el is None:
                    desc_el = item.find("{http://www.w3.org/2005/Atom}summary")

                title = title_el.text if title_el is not None else ""
                link = link_el.text if link_el is not None else (
                    link_el.get("href") if link_el is not None else ""
                )
                desc = desc_el.text if desc_el is not None and desc_el.text else ""

                pub_date_str = ""
                pub_el = item.find("pubDate")
                if pub_el is not None:
                    pub_date_str = pub_el.text
                else:
                    updated_el = item.find("{http://www.w3.org/2005/Atom}updated")
                    if updated_el is not None:
                        pub_date_str = updated_el.text

                if pub_date_str:
                    try:
                        pub_date = parser.parse(pub_date_str).replace(tzinfo=None)
                        if pub_date < cutoff_date:
                            continue
                    except Exception:
                        pass

                if not title or not link:
                    continue

                all_items.append({
                    "title": title.strip(),
                    "link": link.strip(),
                    "description": re.sub(r'<[^>]+>', '', desc).strip()[:500],
                    "source": source["name"],
                    "topic": source.get("topic", "")
                })
        except Exception as e:
            print(f"Failed to parse {source.get('name', source.get('url'))}: {e}")

    return all_items


# ---------- ВЫБОР ЛУЧШЕГО МИФА ----------

def myth_score(item):
    score = 0
    title = item.get("title") or ""
    if re.search(r'\d', title):
        score += 2
    if "?" in title:
        score += 2
    wow_words = ["strange", "bizarre", "unusual", "incredible", "mystery", "myth",
                 "hidden", "secret", "revealed", "surprising", "rare", "ancient"]
    for word in wow_words:
        if word.lower() in title.lower():
            score += 3
            break
    if 40 <= len(title) <= 90:
        score += 2
    return score


def select_best_myth(news_list, used_items):
    if not news_list:
        return None

    candidates = []
    for item in news_list:
        if is_duplicate(item["title"], item["link"], used_items):
            continue
        if is_political(item["title"], item["description"]):
            print(f"Пропущено (политический маркер): {item['title'][:80]}")
            continue
        candidates.append(item)

    if not candidates:
        print("Нет подходящих кандидатов (всё дубли или отфильтровано).")
        return None

    scored = [(myth_score(item), item) for item in candidates]
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_item = scored[0]
    print(f"Выбран миф (score {best_score}): {best_item['title'][:100]}")
    return best_item if best_score >= 3 else None


# ---------- ГЕНЕРАЦИЯ ПОСТА ----------

def generate_post(news_item):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    real_context = (
        f"Real news: {news_item['title']}. Source: {news_item['source']}. "
        f"Link: {news_item['link']}. Description: {news_item['description'][:300]}"
    )

    system_prompt = f"""Ты — редактор Telegram-канала «О как».
{real_context}
Напиши пост (600–900 знаков) на русском языке. Разоблачи миф или расскажи удивительный факт.
Формат:
- Миф: одно предложение
- Факт: опровержение с источником
- Ирония или гипотеза: короткий вопрос
Подпись: «О как»
Не добавляй лишних заголовков и пояснений."""

    data = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Напиши пост."}
        ],
        "temperature": 0.5,
        "max_tokens": 2000
    }

    response = requests.post(url, headers=headers, json=data, timeout=30)
    if response.status_code != 200:
        raise Exception(f"Groq error: {response.text}")

    content = response.json()["choices"][0]["message"]["content"].strip()
    print("Raw Groq response content:", repr(content))

    if not content or len(content) < 50:
        print("Пустой ответ от Groq.")
        return None

    # Проверка на русский язык
    russian_chars = len(re.findall(r'[а-яёА-ЯЁ]', content))
    total_chars = len(re.sub(r'\s', '', content))
    if total_chars == 0 or russian_chars / total_chars < 0.5:
        print("Пост отклонён: меньше 50% русских букв.")
        return None

    # Убираем повторяющиеся "О как" и добавляем одну подпись
    content = re.sub(r'(?i)(\s*О как\s*[!.]?\s*)+$', '', content).rstrip()
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
    r = requests.post(url, json=payload, timeout=15)
    if r.status_code != 200:
        raise Exception(f"Telegram error: {r.text}")


if __name__ == "__main__":
    try:
        used_items = load_used_items()
        all_news = parse_rss()
        print(f"Найдено кандидатов из RSS: {len(all_news)}")

        best_myth = select_best_myth(all_news, used_items)
        if best_myth is None:
            print("Подходящий миф не найден. Пост не публикуется.")
        else:
            post = generate_post(best_myth)
            if post is None:
                print("Пост не опубликован (не прошёл проверку).")
            else:
                print("Сгенерирован пост:\n", post)
                send_to_telegram(post)
                mark_used(best_myth["title"], best_myth["link"], used_items)
                print("Пост отправлен, отпечаток сохранён в used_items.json")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
