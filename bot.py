import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import threading
import time
import sqlite3
from flask import Flask, request
import os

# ================= CONFIG =================

TOKEN = "8767848071:AAHjxT7945VO-X7iCI3kG-0fIqC_giqX7Z8"
ADMIN_CHANNEL_ID = -1003705705673
API_KEY = "2f8c79b66ceed85aaf20322308f11e5a"
NOWPAY_API_KEY = "ZB43Y23-F3E4XKG-K83X2GC-MPAAHZ5"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ================= DATABASE =================

db = sqlite3.connect("vip.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS vip_users (
    user_id INTEGER PRIMARY KEY,
    plan TEXT,
    expire_date INTEGER
)
""")
db.commit()

# ================= VIP FUNCTIONS =================

def add_vip(user_id, plan, days):
    expire = int(time.time()) + days * 86400
    cursor.execute(
        "INSERT OR REPLACE INTO vip_users VALUES (?,?,?)",
        (user_id, plan, expire)
    )
    db.commit()

def get_plan(user_id):
    cursor.execute("SELECT plan, expire_date FROM vip_users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if not row:
        return None

    if row[1] < int(time.time()):
        cursor.execute("DELETE FROM vip_users WHERE user_id=?", (user_id,))
        db.commit()
        return None

    return row[0]

# ================= REAL MATCHES (API-SPORTS) =================

def get_matches():
    try:
        url = "https://v3.football.api-sports.io/fixtures?next=6"
        headers = {
            "x-apisports-key": API_KEY
        }

        r = requests.get(url, headers=headers)
        data = r.json()

        matches = []

        if "response" not in data:
            return []

        for m in data["response"]:
            home = m["teams"]["home"]["name"]
            away = m["teams"]["away"]["name"]
            matches.append(f"{home} vs {away}")

        return matches

    except:
        return []

# ================= PAYMENTS =================

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

# ================= MENU =================

@bot.message_handler(commands=['start'])
def start(message):

    m = InlineKeyboardMarkup(row_width=2)

    m.add(
        InlineKeyboardButton("💎 VIP", callback_data="vip"),
        InlineKeyboardButton("🔥 BETS", callback_data="bets"),
        InlineKeyboardButton("⭐ FREE PICK", callback_data="free"),
        InlineKeyboardButton("📊 RESULTS", callback_data="results"),
        InlineKeyboardButton("🎯 STRATEGY", callback_data="strategy"),
        InlineKeyboardButton("💬 SUPPORT", callback_data="support")
    )

    bot.send_message(
        message.chat.id,
        "👑 ValueHunter Elite\nPremium football value betting system.",
        reply_markup=m
    )

# ================= FREE PICK (REAL MATCH) =================

@bot.callback_query_handler(func=lambda c: c.data == "free")
def free(c):

    matches = get_matches()

    if not matches:
        bot.send_message(c.message.chat.id, "No matches available")
        return

    match = matches[0]

    bot.send_message(
        c.message.chat.id,
        f"⭐ FREE VIP PICK\n\n"
        f"⚽ {match}\n"
        f"🎯 Pick: Over 2.5 Goals\n"
        f"👑 Confidence: HIGH\n\n"
        f"Για πλήρη πρόσβαση ενεργοποίησε VIP 👑"
    )

# ================= VIP MENU =================

@bot.callback_query_handler(func=lambda c: c.data == "vip")
def vip(c):

    m = InlineKeyboardMarkup()

    m.add(
        InlineKeyboardButton("🥉 BASIC — 50€", callback_data="basic"),
        InlineKeyboardButton("🥇 PRO — 100€", callback_data="pro"),
        InlineKeyboardButton("⚡ DAY PASS — 15€", callback_data="day")
    )

    bot.send_message(c.message.chat.id, "Choose plan:", reply_markup=m)

# ================= PAYMENT BUTTONS =================

@bot.callback_query_handler(func=lambda c: c.data in ["basic","pro","day"])
def pay(c):

    plans = {
        "basic": (50, "BASIC", 30),
        "pro": (100, "PRO", 30),
        "day": (15, "DAY", 1)
    }

    price, plan, days = plans[c.data]

    link = create_payment(price, c.message.chat.id)

    bot.send_message(
        c.message.chat.id,
        f"💳 Pay here:\n{link}\n\nPlan: {plan}"
    )

# ================= VIP LOCK =================

@bot.callback_query_handler(func=lambda c: c.data == "bets")
def bets(c):

    plan = get_plan(c.message.chat.id)

    if not plan:
        bot.send_message(c.message.chat.id, "🔒 VIP ONLY")
        return

    bot.send_message(c.message.chat.id, f"🔥 {plan} VIP BETS sent daily")

# ================= SUPPORT =================

@bot.callback_query_handler(func=lambda c: c.data == "support")
def support(c):
    bot.send_message(c.message.chat.id, "@MrMasterlegacy1")

# ================= AUTO BETS =================

def auto_bets():

    sent = False

    while True:

        hour = time.strftime("%H")

        if hour == "12" and not sent:

            matches = get_matches()

            for row in cursor.execute("SELECT user_id, plan FROM vip_users"):

                uid, plan = row

                if plan == "BASIC":
                    bets = matches[:3]
                else:
                    bets = matches[:6]

                for match in bets:
                    bot.send_message(uid, f"🔥 VIP BET\n⚽ {match}")

            sent = True

        if hour == "00":
            sent = False

        time.sleep(60)

# ================= PAYMENT WEBHOOK =================

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

# ================= RUN =================

def run_web():
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web).start()
threading.Thread(target=auto_bets).start()

print("ValueHunter GOD MODE Running...")

bot.infinity_polling()