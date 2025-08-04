import os, json, subprocess, requests
from datetime import datetime
from flask import Flask, request

TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT = os.getenv("TELEGRAM_CHAT")
API_URL = "https://store.steampowered.com/api/featuredcategories/?l=english"
STATE_FILE = "last_notified.json"
LANG_FILE = "lang_settings.json"

messages = {
    "tr": {
        "found": "🎮 *Steam'de yeni ücretsiz oyun(lar) bulundu\\!*",
        "none": "⏰ *{time} tarihinde ücretsiz oyun bulunamadı\\.*"
    },
    "az": {
        "found": "🎮 *Steam-də yeni pulsuz oyun(lar) tapıldı\\!*",
        "none": "⏰ *{time} tarixində pulsuz oyun tapılmadı\\.*"
    },
    "en": {
        "found": "🎮 *New free game\\(s\\) on Steam\\!*",
        "none": "⏰ *No free games found at {time}\\.*"
    }
}

def load_json(file, default):
    if not os.path.exists(file):
        save_json(file, default)
        git_commit([file], f"Create {file}")
        return default
    return json.load(open(file))

def save_json(file, data):
    json.dump(data, open(file, "w"), ensure_ascii=False)

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
    git_commit([LANG_FILE], f"Update language for {chat} to {lang}")

def git_commit(files, message):
    try:
        subprocess.run(["git", "config", "user.email", "github-actions@users.noreply.github.com"], check=True)
        subprocess.run(["git", "config", "user.name", "github-actions"], check=True)
        subprocess.run(["git", "add"] + files, check=True)
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if status.stdout.strip() == "":
            print("No changes to commit.")
            return
        subprocess.run(["git", "commit", "-m", message], check=True)
        subprocess.run(["git", "push", "-u", "origin", "HEAD"], check=True)
        print("Commit & push successful.")
    except subprocess.CalledProcessError as e:
        print("Git commit error:", e)

def notify_free_games():
    last_notified = load_json(STATE_FILE, [])
    data = requests.get(API_URL).json()
    free_games = [g for g in data["specials"]["items"] if g.get("discount_percent") == 100]
    new_games = [g for g in free_games if g["id"] not in last_notified]
    lang = get_lang(TG_CHAT)

    if new_games:
        message_lines = [messages[lang]["found"]]
        for game in new_games:
            name = escape_md(game["name"])
            url = f"https://store.steampowered.com/app/{game['id']}/"
            message_lines.append(f"• [{name}]({url})")
        message = "\n".join(message_lines)
        last_notified.extend(g["id"] for g in new_games)
        save_json(STATE_FILE, last_notified)
        git_commit([STATE_FILE], "Update last_notified.json")
    else:
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        message = messages[lang]["none"].format(time=escape_md(now))

    requests.get(
        f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
        params={
            "chat_id": TG_CHAT,
            "text": message,
            "parse_mode": "MarkdownV2",
            "disable_web_page_preview": True
        }
    )

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
        if new_lang in messages.keys():
            set_lang(chat, new_lang)
            reply = f"Dil değiştirildi: {new_lang.upper()}"
        else:
            reply = "Geçerli diller: tr, az, en"

        requests.get(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            params={"chat_id": chat, "text": reply}
        )
    return {"ok": True}
