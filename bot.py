import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import sqlite3
import threading
import time
import os

# ====== CONFIG ======

TOKEN = "8767848071:AAHjxT7945VO-X7iCI3kG-0fIqC_giqX7Z8"
ADMIN_ID = 8328070177
CHANNEL_ID = -1003705705673
API_KEY = "2f8c79b66ceed85aaf20322308f11e5a"

bot = telebot.TeleBot(TOKEN)

# ===== DATABASE =====

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

# ===== VIP CHECK =====

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

# ===== API FOOTBALL =====

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

# ===== START MENU =====

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

# ===== VIP MENU =====

@bot.callback_query_handler(func=lambda c: c.data == "vip")
def vip(c):
    bot.send_message(
        c.message.chat.id,
        "💎 VIP Plans\n\n🥉 BASIC — 50€\n🥇 PRO — 100€\n⚡ DAY PASS — 15€"
    )

# ===== FREE PICK =====

@bot.callback_query_handler(func=lambda c: c.data == "free")
def free(c):

    matches = get_matches()

    if not matches:
        bot.send_message(c.message.chat.id, "No matches found")
        return

    bot.send_message(
        c.message.chat.id,
        f"⭐ FREE PICK\n\n⚽ {matches[0]}\n🎯 Over 2.5 Goals\n👑 HIGH CONFIDENCE"
    )

# ===== VIP BETS =====

@bot.callback_query_handler(func=lambda c: c.data == "bets")
def bets(c):

    plan = get_plan(c.message.chat.id)

    if not plan:
        bot.send_message(c.message.chat.id, "🔒 VIP ONLY")
        return

    bot.send_message(c.message.chat.id, f"🔥 {plan} VIP BETS sent daily")

# ===== OTHER BUTTONS =====

@bot.callback_query_handler(func=lambda c: c.data == "results")
def results(c):
    bot.send_message(c.message.chat.id, "🏆 Win Rate: 75%")

@bot.callback_query_handler(func=lambda c: c.data == "strategy")
def strategy(c):
    bot.send_message(c.message.chat.id, "🎯 Value Betting Strategy")

@bot.callback_query_handler(func=lambda c: c.data == "support")
def support(c):
    bot.send_message(c.message.chat.id, "@MrMasterlegacy1")

# ===== AUTO BETS =====

def auto_bets():

    sent_today = False

    while True:

        hour = time.strftime("%H")

        if hour == "12" and not sent_today:

            matches = get_matches()

            for row in cursor.execute("SELECT user_id, plan FROM vip_users"):

                uid, plan = row

                bets = matches[:3] if plan == "BASIC" else matches[:5]

                for match in bets:
                    bot.send_message(uid, f"🔥 VIP BET\n⚽ {match}")

            # SEND TO CHANNEL
            for match in matches[:3]:
                bot.send_message(CHANNEL_ID, f"🔥 CHANNEL BET\n⚽ {match}")

            sent_today = True

        if hour == "00":
            sent_today = False

        time.sleep(60)

threading.Thread(target=auto_bets, daemon=True).start()

print("ValueHunter Running...")

bot.infinity_polling()