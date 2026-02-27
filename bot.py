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
API_KEY = "2f8c79b66ceed85aaf20322308f11e5a"
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

    if not row:
        return None

    if row[1] < int(time.time()):
        return None

    return row[0]

# ========= API FOOTBALL =========

def get_matches():
    url = "https://v3.football.api-sports.io/fixtures?next=5"
    headers = {"x-apisports-key": API_KEY}

    r = requests.get(url, headers=headers).json()

    matches = []

    for m in r.get("response", []):
        home = m["teams"]["home"]["name"]
        away = m["teams"]["away"]["name"]
        matches.append(f"{home} vs {away}")

    return matches

# ========= CREATE PAYMENT =========

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

# ========= MENU =========

@bot.message_handler(commands=['start'])
def start(msg):

    m = InlineKeyboardMarkup(row_width=2)

    m.add(
        InlineKeyboardButton("💎 VIP", callback_data="vip"),
        InlineKeyboardButton("🔥 VIP BETS", callback_data="bets"),
        InlineKeyboardButton("⭐ FREE PICK", callback_data="free"),
        InlineKeyboardButton("🏆 RESULTS", callback_data="results"),
        InlineKeyboardButton("🎯 STRATEGY", callback_data="strategy"),
        InlineKeyboardButton("💬 SUPPORT", callback_data="support")
    )

    bot.send_message(
        msg.chat.id,
        "👑 ValueHunter Elite\nPremium Football Value Betting System",
        reply_markup=m
    )

# ========= VIP MENU =========

@bot.callback_query_handler(func=lambda c: c.data == "vip")
def vip(c):

    m = InlineKeyboardMarkup()

    m.add(
        InlineKeyboardButton("🥉 BASIC — 50€", callback_data="buy_basic"),
        InlineKeyboardButton("🥇 PRO — 100€", callback_data="buy_pro"),
        InlineKeyboardButton("⚡ DAY PASS — 15€", callback_data="buy_day")
    )

    bot.send_message(
        c.message.chat.id,
        "💎 Επίλεξε πακέτο:",
        reply_markup=m
    )

# ========= BUY HANDLERS =========

@bot.callback_query_handler(func=lambda c: c.data.startswith("buy_"))
def buy(c):

    prices = {
        "buy_basic": 50,
        "buy_pro": 100,
        "buy_day": 15
    }

    amount = prices[c.data]

    link = create_payment(amount, c.message.chat.id)

    bot.send_message(
        c.message.chat.id,
        f"💳 Πλήρωσε εδώ:\n{link}"
    )

# ========= FREE PICK =========

@bot.callback_query_handler(func=lambda c: c.data == "free")
def free(c):

    matches = get_matches()

    if not matches:
        bot.send_message(c.message.chat.id, "No matches")
        return

    bot.send_message(
        c.message.chat.id,
        f"⭐ FREE PICK\n\n⚽ {matches[0]}\n🎯 Over 2.5 Goals\n👑 HIGH CONFIDENCE"
    )

# ========= VIP BETS =========

@bot.callback_query_handler(func=lambda c: c.data == "bets")
def bets(c):

    plan = get_plan(c.message.chat.id)

    if not plan:
        bot.send_message(c.message.chat.id, "🔒 VIP ONLY")
        return

    bot.send_message(c.message.chat.id, f"🔥 {plan} VIP BETS sent daily")

# ========= OTHER =========

@bot.callback_query_handler(func=lambda c: c.data == "results")
def results(c):
    bot.send_message(c.message.chat.id, "🏆 Win Rate: 75%")

@bot.callback_query_handler(func=lambda c: c.data == "strategy")
def strategy(c):
    bot.send_message(c.message.chat.id, "🎯 Value Betting Strategy")

@bot.callback_query_handler(func=lambda c: c.data == "support")
def support(c):
    bot.send_message(c.message.chat.id, "@MrMasterlegacy1")

# ========= AUTO BETS =========

def auto_bets():

    sent = False

    while True:

        hour = time.strftime("%H")

        if hour == "12" and not sent:

            matches = get_matches()

            for row in cursor.execute("SELECT user_id, plan FROM vip_users"):

                uid, plan = row

                bets = matches[:3] if plan == "BASIC" else matches[:5]

                for match in bets:
                    bot.send_message(uid, f"🔥 VIP BET\n⚽ {match}")

            for match in matches[:3]:
                bot.send_message(CHANNEL_ID, f"🔥 CHANNEL BET\n⚽ {match}")

            sent = True

        if hour == "00":
            sent = False

        time.sleep(60)

# ========= PAYMENT WEBHOOK =========

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

    bot.send_message(user_id, "👑 VIP ενεργοποιήθηκε!")

    return "OK"

# ========= RUN =========

def run_web():
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=auto_bets, daemon=True).start()
threading.Thread(target=run_web).start()

print("ValueHunter Elite Running...")

bot.infinity_polling()