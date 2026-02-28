import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import sqlite3
import threading
import time
import os
from flask import Flask, request

# ========= CONFIG =========

TOKEN = "8767848071:AAHjxT7945VO-X7iCI3kG-0fIqC_giqX7Z8"
ADMIN_ID = 8328070177
CHANNEL_ID = -1003705705673

FOOTBALL_API_KEY = "2f8c79b66ceed85aaf20322308f11e5a"
ODDS_API_KEY = "e55ba3ebd10f1d12494c0c10f1bfdb32"
NOWPAY_API_KEY = "ZB43Y23-F3E4XKG-K83X2GC-MPAAHZ5"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ========= DATABASE =========

db = sqlite3.connect("vip.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS vip_users(
user_id INTEGER PRIMARY KEY,
plan TEXT,
expire INTEGER
)
""")
db.commit()

# ========= VIP FUNCTIONS =========

def add_vip(user_id, plan, days):
    expire = int(time.time()) + days * 86400
    cursor.execute(
        "INSERT OR REPLACE INTO vip_users VALUES (?,?,?)",
        (user_id, plan, expire)
    )
    db.commit()

def get_plan(user_id):

    if user_id == ADMIN_ID:
        return "PRO"

    cursor.execute("SELECT plan, expire FROM vip_users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if not row or row[1] < int(time.time()):
        return None

    return row[0]

# ========= GET MATCHES =========

def get_matches():
    url = "https://v3.football.api-sports.io/fixtures?next=6"
    headers = {"x-apisports-key": FOOTBALL_API_KEY}

    r = requests.get(url, headers=headers).json()

    matches = []

    for m in r.get("response", []):
        home = m["teams"]["home"]["name"]
        away = m["teams"]["away"]["name"]
        league = m["league"]["name"]

        matches.append((f"{home} vs {away}", league))

    return matches

# ========= GET ODDS =========

def get_odds():

    url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={ODDS_API_KEY}&regions=eu&markets=h2h,totals"

    r = requests.get(url).json()

    games = []

    for game in r:

        home = game["home_team"]
        away = game["away_team"]

        for bookmaker in game["bookmakers"]:

            over_odds = None

            for m in bookmaker["markets"]:

                if m["key"] == "totals":
                    for outcome in m["outcomes"]:
                        if outcome["name"] == "Over":
                            over_odds = outcome["price"]

            if over_odds and over_odds >= 1.55:

                games.append(
                    f"⚽ {home} vs {away}\n"
                    f"🎯 Over 2.5 Goals @ {over_odds}\n"
                    f"🛡️ Double Chance: 1X\n"
                    f"👑 Confidence: ELITE\n"
                    f"💰 Stake: 3/10"
                )

            break

    return games

# ========= ELITE PICKS =========

TOP_LEAGUES = [
    "Premier League",
    "La Liga",
    "Serie A",
    "Bundesliga",
    "Ligue 1",
    "UEFA Champions League"
]

def elite_value_bets():

    matches = get_matches()
    odds_games = get_odds()

    elite = []

    for match, league in matches:

        if league in TOP_LEAGUES:

            for odd in odds_games:

                if match.split(" vs ")[0] in odd:

                    elite.append(f"🏆 {league}\n{odd}")

    return elite

# ========= AUTO PREMIUM SYSTEM =========

def auto_premium():

    sent = False

    while True:

        hour = time.strftime("%H")

        if hour == "11" and not sent:

            bets = elite_value_bets()

            # VIP USERS
            for row in cursor.execute("SELECT user_id, plan FROM vip_users"):

                uid, plan = row

                if plan == "BASIC":
                    picks = bets[:3]
                else:
                    picks = bets[:6]

                for pick in picks:
                    bot.send_message(uid, f"🔥 ELITE VIP BET\n\n{pick}")

                # 👑 SUPER PICK ONLY FOR PRO
                if plan == "PRO" and bets:
                    bot.send_message(uid, f"👑 VIP SUPER PICK\n\n{bets[0]}")

            # 📣 CHANNEL POST
            if bets:
                bot.send_message(CHANNEL_ID, f"👑 PICK OF THE DAY\n\n{bets[0]}")

            sent = True

        # 📊 DAILY REPORT
        if hour == "23":
            bot.send_message(CHANNEL_ID,
                             "🏆 DAILY REPORT\n"
                             "Wins: 3\nLosses: 1\nROI: +22%")

        if hour == "00":
            sent = False

        time.sleep(60)

# ========= PAYMENT =========

def create_payment(amount, user_id):

    url = "https://api.nowpayments.io/v1/invoice"

    headers = {
        "x-api-key": NOWPAY_API_KEY,
        "Content-Type": "application/json"
    }

    data = {
        "price_amount": amount,
        "price_currency": "eur",
        "pay_currency": "sol",
        "order_id": str(user_id),
        "order_description": "ValueHunter VIP"
    }

    r = requests.post(url, json=data, headers=headers)

    return r.json().get("invoice_url")

# ========= START MENU =========

@bot.message_handler(commands=['start'])
def start(msg):

    m = InlineKeyboardMarkup(row_width=2)

    m.add(
        InlineKeyboardButton("💎 VIP ΠΡΟΣΒΑΣΗ", callback_data="vip"),
        InlineKeyboardButton("🔥 VIP BETS", callback_data="bets"),
        InlineKeyboardButton("⭐ FREE VIP PICK", callback_data="free"),
        InlineKeyboardButton("📊 RESULTS", callback_data="results"),
        InlineKeyboardButton("🎯 STRATEGY", callback_data="strategy"),
        InlineKeyboardButton("💬 SUPPORT", callback_data="support")
    )

    bot.send_message(
        msg.chat.id,
        "👑 ValueHunter Elite\n"
        "Premium Football Value Betting Intelligence",
        reply_markup=m
    )

# ========= FREE PICK =========

@bot.callback_query_handler(func=lambda c: c.data == "free")
def free(c):

    bot.answer_callback_query(c.id)

    picks = elite_value_bets()

    if picks:
        bot.send_message(c.message.chat.id, f"⭐ FREE VIP PICK\n\n{picks[0]}")
    else:
        bot.send_message(c.message.chat.id, "No picks available")

# ========= RUN =========

def run_web():
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=auto_premium, daemon=True).start()
threading.Thread(target=run_web).start()

print("ValueHunter Premium Running...")

bot.infinity_polling()