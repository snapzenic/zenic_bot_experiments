import os, json, requests
from flask import Flask, request

TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT = os.getenv("TELEGRAM_CHAT")
API_URL = "https://store.steampowered.com/api/featuredcategories/?l=english"
STATE_FILE = "last_notified.json"
LANG_FILE = "lang_settings.json"

messages = {
    "tr": "🎮 *Steam'de yeni ücretsiz oyun(lar) bulundu\\!*",
    "az": "🎮 *Steam-də yeni pulsuz oyun(lar) tapıldı\\!*",
    "en": "🎮 *New free game\\(s\\) on Steam\\!*"
}

def load_json(file, default):
    return json.load(open(file)) if os.path.exists(file) else default

def save_json(file, data):
    json.dump(data, open(file, "w"))

def escape_md(text):
    for ch in "_*[]()~`>#+-=|{}.!" :
        text = text.replace(ch, f"\\{ch}")
    return text

def get_lang(chat):
    langs = load_json(LANG_FILE, {})
    return langs.get(str(chat), "tr")

def set_lang(chat, lang):
    langs = load_json(LANG_FILE, {})
    langs[str(chat)] = lang
    save_json(LANG_FILE, langs)

def notify_free_games():
    last_notified = load_json(STATE_FILE, [])
    data = requests.get(API_URL).json()
    free_games = [g for g in data["specials"]["items"] if g.get("discount_percent") == 100]
    new_games = [g for g in free_games if g["id"] not in last_notified]

    if new_games:
        lang = get_lang(TG_CHAT)
        message_lines = [messages.get(lang, messages["tr"])]
        for game in new_games:
            name = escape_md(game["name"])
            url = f"https://store.steampowered.com/app/{game['id']}/"
            message_lines.append(f"• [{name}]({url})")
        message = "\n".join(message_lines)

        requests.get(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            params={
                "chat_id": TG_CHAT,
                "text": message,
                "parse_mode": "MarkdownV2",
                "disable_web_page_preview": True
            }
        )

        last_notified.extend(g["id"] for g in new_games)
        save_json(STATE_FILE, last_notified)
    else:
        print("No new free games.")

if os.getenv("GITHUB_ACTIONS"):
    notify_free_games()

app = Flask(__name__)

@app.route(f"/{TG_TOKEN}", methods=["POST"])
def webhook():
    data = request.json
    chat = data["message"]["chat"].get("username") or data["message"]["chat"]["id"]
    text = data["message"].get("text", "")

    if text.startswith("/lang "):
        new_lang = text.split(" ", 1)[1].strip().lower()
        if new_lang in ["tr", "az", "en"]:
            set_lang(chat, new_lang)
            reply = f"Dil değiştirildi: {new_lang.upper()}"
        else:
            reply = "Geçerli diller: tr, az, en"

        requests.get(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            params={"chat_id": chat, "text": reply}
        )
    return {"ok": True}
