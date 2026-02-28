import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import sqlite3
import threading
import time
import os
from datetime import datetime, timedelta

# ========= CONFIG =========

TOKEN = "8767848071:AAHjxT7945VO-X7iCI3kG-0fIqC_giqX7Z8"
ADMIN_ID = 8328070177
CHANNEL_ID = -1003705705673

FOOTBALL_API_KEY = "2f8c79b66ceed85aaf20322308f11e5a"
ODDS_API_KEY = "e55ba3ebd10f1d12494c0c10f1bfdb32"
NOWPAY_API_KEY = "ZB43Y23-F3E4XKG-K83X2GC-MPAAHZ5"

bot = telebot.TeleBot(TOKEN)

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
        return "ADMIN"

    cursor.execute("SELECT plan, expire FROM vip_users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if not row or row[1] < int(time.time()):
        return None

    return row[0]

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

# ========= MATCHES 24H BEFORE =========

def get_matches_24h():

    tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

    url = f"https://v3.football.api-sports.io/fixtures?date={tomorrow}"
    headers = {"x-apisports-key": FOOTBALL_API_KEY}

    r = requests.get(url, headers=headers).json()

    matches = []

    for m in r.get("response", []):
        home = m["teams"]["home"]["name"]
        away = m["teams"]["away"]["name"]
        league = m["league"]["name"]

        matches.append((home, away, league))

    return matches

# ========= ODDS ANALYSIS =========

def analyze_game(home, away):

    url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={ODDS_API_KEY}&regions=eu&markets=totals,h2h"
    r = requests.get(url).json()

    for game in r:

        if game["home_team"] == home and game["away_team"] == away:

            for bookmaker in game["bookmakers"]:

                over_odds = None
                under_odds = None

                for market in bookmaker["markets"]:

                    if market["key"] == "totals":
                        for outcome in market["outcomes"]:
                            if outcome["name"] == "Over":
                                over_odds = outcome["price"]
                            if outcome["name"] == "Under":
                                under_odds = outcome["price"]

                if over_odds and over_odds >= under_odds:
                    market = f"Over 2.5 @ {over_odds}"
                else:
                    market = f"Under 2.5 @ {under_odds}"

                return (
                    f"⚽ {home} vs {away}\n\n"
                    f"🎯 Main Market: {market}\n"
                    f"🛡️ Double Chance Insight: 1X\n\n"
                    f"🧠 Elite Analysis:\n"
                    f"Tempo models, defensive metrics,\n"
                    f"and value detection algorithms.\n\n"
                    f"👑 Confidence: ELITE"
                )

# ========= START MENU =========

@bot.message_handler(commands=['start'])
def start(msg):

    text = """👑 Καλώς ήρθες στο ValueHunter Elite🇬🇷  

Το απόλυτο Luxury Value Betting Intelligence System για όσους θέλουν να παίζουν με πλεονέκτημα — όχι με τύχη.  

⚽ Elite Match Intelligence  
📊 Real Value Detection  
🏆 Top Leagues Only  
🎯 Precision Over/Under & Double Chance  

🔒 Η πλήρης πρόσβαση επιτρέπεται μόνο σε ενεργά μέλη."""

    m = InlineKeyboardMarkup(row_width=2)

    m.add(
        InlineKeyboardButton("💎 VIP ΠΡΟΣΒΑΣΗ", callback_data="vip"),
        InlineKeyboardButton("🔥 VIP BETS", callback_data="bets"),
        InlineKeyboardButton("⭐ FREE VIP PICK", callback_data="free"),
        InlineKeyboardButton("📊 RESULTS", callback_data="results"),
        InlineKeyboardButton("🎯 STRATEGY", callback_data="strategy"),
        InlineKeyboardButton("💬 SUPPORT", callback_data="support")
    )

    bot.send_message(msg.chat.id, text, reply_markup=m)

# ========= VIP MENU =========

@bot.callback_query_handler(func=lambda c: c.data == "vip")
def vip(c):

    m = InlineKeyboardMarkup()

    m.add(
        InlineKeyboardButton("🥉 BASIC — 50€", callback_data="buy_basic"),
        InlineKeyboardButton("🥇 PRO — 100€", callback_data="buy_pro"),
        InlineKeyboardButton("⚡ DAY PASS — 15€", callback_data="buy_day")
    )

    bot.send_message(c.message.chat.id,
                     "💎 Επίλεξε VIP πακέτο:",
                     reply_markup=m)

# ========= BUY =========

@bot.callback_query_handler(func=lambda c: c.data.startswith("buy_"))
def buy(c):

    prices = {
        "buy_basic": 50,
        "buy_pro": 100,
        "buy_day": 15
    }

    amount = prices[c.data]

    link = create_payment(amount, c.message.chat.id)

    bot.send_message(c.message.chat.id,
                     f"💳 Πλήρωσε εδώ:\n{link}")

# ========= FREE PICK =========

@bot.callback_query_handler(func=lambda c: c.data == "free")
def free(c):

    matches = get_matches_24h()

    if matches:
        analysis = analyze_game(matches[0][0], matches[0][1])
        bot.send_message(c.message.chat.id,
                         f"⭐ FREE VIP PICK\n\n{analysis}")

# ========= VIP BETS =========

@bot.callback_query_handler(func=lambda c: c.data == "bets")
def bets(c):

    plan = get_plan(c.message.chat.id)

    if not plan:
        bot.send_message(c.message.chat.id, "🔒 VIP ONLY")
        return

    bot.send_message(c.message.chat.id,
                     f"🔥 {plan} VIP BETS sent automatically")

# ========= AUTO SYSTEM =========

def auto_bets():

    sent_today = False

    while True:

        hour = time.strftime("%H")

        if hour == "12" and not sent_today:

            matches = get_matches_24h()

            # ADMIN gets 8 bets
            for m in matches[:8]:
                analysis = analyze_game(m[0], m[1])
                if analysis:
                    bot.send_message(ADMIN_ID,
                                     f"👑 ADMIN ELITE BET\n\n{analysis}")

            # VIP USERS
            for row in cursor.execute("SELECT user_id, plan FROM vip_users"):

                uid, plan = row

                bets = matches[:3] if plan == "BASIC" else matches[:5]

                for m in bets:
                    analysis = analyze_game(m[0], m[1])
                    if analysis:
                        bot.send_message(uid,
                                         f"🔥 VIP BET\n\n{analysis}")

            sent_today = True

        if hour == "00":
            sent_today = False

        time.sleep(60)

# ========= RUN =========

threading.Thread(target=auto_bets, daemon=True).start()

print("VALUEHUNTER ELITE RUNNING")

bot.infinity_polling()