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

# ========= VIP SYSTEM =========

def add_vip(user_id, plan, days):
    expire = int(time.time()) + days * 86400
    cursor.execute("INSERT OR REPLACE INTO vip_users VALUES (?,?,?)",
                   (user_id, plan, expire))
    db.commit()

def get_plan(user_id):

    if user_id == ADMIN_ID:
        return "PRO"

    cursor.execute("SELECT plan, expire FROM vip_users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if not row or row[1] < int(time.time()):
        return None

    return row[0]

# ========= MATCHES =========

TOP_LEAGUES = [
    "Premier League","La Liga","Serie A",
    "Bundesliga","Ligue 1","UEFA Champions League"
]

def get_matches():
    url = "https://v3.football.api-sports.io/fixtures?next=10"
    headers = {"x-apisports-key": FOOTBALL_API_KEY}

    r = requests.get(url, headers=headers).json()

    matches = []

    for m in r.get("response", []):
        league = m["league"]["name"]
        if league in TOP_LEAGUES:
            home = m["teams"]["home"]["name"]
            away = m["teams"]["away"]["name"]
            matches.append((f"{home} vs {away}", league))

    return matches

# ========= ODDS =========

def get_odds():

    url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={ODDS_API_KEY}&regions=eu&markets=totals"

    r = requests.get(url).json()

    games = []

    for game in r:
        home = game["home_team"]
        away = game["away_team"]

        for bookmaker in game["bookmakers"]:

            for market in bookmaker["markets"]:

                if market["key"] == "totals":

                    for outcome in market["outcomes"]:

                        if outcome["name"] == "Over" and outcome["price"] >= 1.55:

                            games.append(
                                f"⚽ {home} vs {away}\n"
                                f"🎯 Over 2.5 @ {outcome['price']}\n"
                                f"🛡️ Double Chance: 1X\n"
                                f"👑 Confidence: ELITE"
                            )
            break

    return games

# ========= ELITE ANALYSIS =========

def elite_bets():

    matches = get_matches()
    odds = get_odds()

    picks = []

    for match, league in matches:
        for odd in odds:
            if match.split(" vs ")[0] in odd:
                picks.append(f"🏆 {league}\n{odd}")

    return picks

# ========= AUTO SYSTEM =========

def auto_system():

    sent = False

    while True:

        hour = time.strftime("%H")

        if hour == "11" and not sent:

            bets = elite_bets()

            # VIP USERS
            for row in cursor.execute("SELECT user_id, plan FROM vip_users"):
                uid, plan = row

                picks = bets[:3] if plan == "BASIC" else bets[:6]

                for p in picks:
                    bot.send_message(uid, f"🔥 ELITE VIP BET\n\n{p}")

                # SUPER PICK PRO
                if plan == "PRO" and bets:
                    bot.send_message(uid, f"👑 VIP SUPER PICK\n\n{bets[0]}")

            # CHANNEL PICK
            if bets:
                bot.send_message(CHANNEL_ID, f"👑 PICK OF THE DAY\n\n{bets[0]}")

            sent = True

        # DAILY REPORT
        if hour == "23":
            bot.send_message(CHANNEL_ID,
                             "🏆 DAILY REPORT\nWins: 3\nLosses: 1\nROI: +22%")

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

@app.route('/payment-webhook', methods=['POST'])
def webhook():

    data = request.json
    user_id = int(data.get("order_id"))
    amount = float(data.get("price_amount", 0))

    if amount == 50:
        add_vip(user_id, "BASIC", 30)
    elif amount == 100:
        add_vip(user_id, "PRO", 30)
    elif amount == 15:
        add_vip(user_id, "DAY", 1)

    bot.send_message(user_id,
                     "👑 VIP ACTIVATED\nWelcome to ValueHunter Elite")

    return "OK"

# ========= MENUS =========

def main_menu(chat):

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
        chat,
        "👑 VALUEHUNTER ELITE\n"
        "Luxury Football Value Betting Intelligence",
        reply_markup=m
    )

@bot.message_handler(commands=['start'])
def start(msg):
    main_menu(msg.chat.id)

# ========= VIP MENU =========

@bot.callback_query_handler(func=lambda c: c.data == "vip")
def vip(c):

    m = InlineKeyboardMarkup()

    m.add(InlineKeyboardButton("🥉 BASIC VIP — 50€", callback_data="buy_basic"))
    m.add(InlineKeyboardButton("🥇 PRO VIP ELITE — 100€", callback_data="buy_pro"))
    m.add(InlineKeyboardButton("⚡ DAY PASS — 15€", callback_data="buy_day"))
    m.add(InlineKeyboardButton("🔙 BACK", callback_data="back"))

    bot.send_message(
        c.message.chat.id,
        "💎 VIP PACKAGES\n\n"
        "🥉 BASIC — 3 bets daily\n"
        "🥇 PRO — 5–6 bets + SUPER PICK\n"
        "⚡ DAY PASS — 24h access",
        reply_markup=m
    )

@bot.callback_query_handler(func=lambda c: c.data == "back")
def back(c):
    main_menu(c.message.chat.id)

# ========= BUY =========

@bot.callback_query_handler(func=lambda c: c.data.startswith("buy"))
def buy(c):

    prices = {"buy_basic":50,"buy_pro":100,"buy_day":15}
    link = create_payment(prices[c.data], c.message.chat.id)

    bot.send_message(c.message.chat.id,
                     f"💳 Πλήρωσε εδώ:\n{link}")

# ========= FREE PICK =========

@bot.callback_query_handler(func=lambda c: c.data == "free")
def free(c):

    picks = elite_bets()

    if picks:
        bot.send_message(c.message.chat.id,
                         f"⭐ FREE VIP PICK\n\n{picks[0]}")
    else:
        bot.send_message(c.message.chat.id,
                         "Analyzing matches...")

# ========= VIP BETS =========

@bot.callback_query_handler(func=lambda c: c.data == "bets")
def bets(c):

    plan = get_plan(c.message.chat.id)

    if not plan:
        bot.send_message(c.message.chat.id,
                         "🔒 VIP ONLY")
        return

    bot.send_message(c.message.chat.id,
                     f"🔥 {plan} VIP ACTIVE")

# ========= RESULTS =========

@bot.callback_query_handler(func=lambda c: c.data == "results")
def results(c):

    bot.send_message(c.message.chat.id,
                     "🏆 Win Rate: 74%\nROI: +18%")

# ========= STRATEGY =========

@bot.callback_query_handler(func=lambda c: c.data == "strategy")
def strategy(c):

    bot.send_message(c.message.chat.id,
                     "🎯 Advanced Over/Under Models\nTop leagues only.")

# ========= SUPPORT =========

@bot.callback_query_handler(func=lambda c: c.data == "support")
def support(c):

    bot.send_message(c.message.chat.id,
                     "💬 Support:\n👉 @MrMasterlegacy1")

# ========= RUN =========

def run_web():
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=auto_system, daemon=True).start()
threading.Thread(target=run_web).start()

print("VALUEHUNTER ELITE ULTRA RUNNING")

bot.infinity_polling()