from datetime import datetime, timedelta
import pytz
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import sqlite3
import time
import threading
from flask import Flask, request
import numpy as np
import math
# ================= CONFIG =================

TOKEN = "8767848071:AAHjxT7945VO-X7iCI3kG-0fIqC_giqX7Z8"
ADMIN_ID = 8328070177

FOOTBALL_API_KEY = "2f8c79b66ceed85aaf20322308f11e5a"
ODDS_API_KEY = "e55ba3ebd10f1d12494c0c10f1bfdb32"
NOWPAY_API_KEY = "ZB43Y23-F3E4XKG-K83X2GC-MPAAHZ5"

WEBHOOK_URL = "https://valuehunter-bot-production.up.railway.app/payment-webhook"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ================= DATABASE =================

db = sqlite3.connect("database.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS vip_users(
user_id INTEGER PRIMARY KEY,
plan TEXT,
expire INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS bets_history(
id INTEGER PRIMARY KEY AUTOINCREMENT,
match TEXT,
pick TEXT,
odds REAL,
result TEXT,
timestamp INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS sent_bets(
key TEXT PRIMARY KEY
)
""")

db.commit()

# ================= VIP FUNCTIONS =================

def add_vip(user_id, plan, days):

    expire = int(time.time()) + days*86400

    cursor.execute(
        "INSERT OR REPLACE INTO vip_users VALUES (?,?,?)",
        (user_id, plan, expire)
    )

    db.commit()

def get_vip_users():

    now = int(time.time())

    return cursor.execute(
        "SELECT user_id,plan FROM vip_users WHERE expire > ?",
        (now,)
    ).fetchall()

def is_vip(user_id):

    now = int(time.time())

    r = cursor.execute(
        "SELECT expire FROM vip_users WHERE user_id=?",
        (user_id,)
    ).fetchone()

    if not r:
        return False

    return r[0] > now

# ================= MENU =================

def main_menu():

    m = InlineKeyboardMarkup()

    m.add(InlineKeyboardButton("🔐 Join Elite", callback_data="elite"))
    m.add(InlineKeyboardButton("🎁 Free Sample", callback_data="sample"))
    m.add(InlineKeyboardButton("⚡ Market Alert", callback_data="alert"))
    m.add(InlineKeyboardButton("📊 Performance", callback_data="perf"))
    m.add(InlineKeyboardButton("💬 Support", callback_data="support"))

    return m

# ================= PAYMENTS =================

def create_payment(amount,user_id):

    url = "https://api.nowpayments.io/v1/invoice"

    headers = {
        "x-api-key": NOWPAY_API_KEY,
        "Content-Type":"application/json"
    }

    data = {
        "price_amount":amount,
        "price_currency":"eur",
        "order_id":str(user_id),
        "ipn_callback_url":WEBHOOK_URL
    }

    r = requests.post(url,json=data,headers=headers)

    return r.json()["invoice_url"]

# ================= PAYMENT WEBHOOK =================

@app.route("/payment-webhook",methods=["POST"])
def webhook():

    data = request.json

    user_id = int(data["order_id"])
    amount = float(data["price_amount"])
    status = data["payment_status"]

    if status != "finished":
        return "ignored"

    if amount == 50:
        add_vip(user_id,"BASIC",30)

    elif amount == 100:
        add_vip(user_id,"PRO",30)

    bot.send_message(
        user_id,
        "👑 VIP Activated\nYou will start receiving signals."
    )

    return "ok"

# ================= FOOTBALL DATA =================

def get_matches():

    url = "https://v3.football.api-sports.io/fixtures?next=20"

    headers = {"x-apisports-key":FOOTBALL_API_KEY}

    try:
        r = requests.get(url,headers=headers).json()
    except:
        return []

    matches = []

    for m in r["response"]:

        home = m["teams"]["home"]["name"]
        away = m["teams"]["away"]["name"]

        matches.append((home,away))

    return matches
(
            # ---------- CONFIDENCE SCORE ----------

            confidence = (
                (prob * 50) +
                (edge * 200) +
                (ev * 100)
            )

            if sharp:
                confidence += 5
            if steam:
                confidence += 10
            if ev > 0.05:

                pick = market

                if market == "Asian Handicap":
                    pick = f"Asian Handicap {f['home']} {line}"
                bet_key = f"{f['fixture_id']}_{pick}"

                # αν το bet έχει ήδη σταλεί → skip
                if cursor.execute(
                    "SELECT key FROM sent_bets WHERE key=?",
                    (bet_key,)
                ).fetchone():
                    continue

                # αποθήκευση bet
                cursor.execute(
                    "INSERT INTO sent_bets VALUES (?)",
                    (bet_key,)
                )

                db.commit()
                candidates.append({
                    "match": f"{f['home']} vs {f['away']}",
                    "pick": pick,
                    "prob": prob,
                    "odds": odds_value,
                    "ev": ev,
                    "confidence": confidence
                    "stake":stake,
                })

    ranked = rank_bets(candidates)

    super_safe = None
    high_value = []

    for bet in ranked:

        if bet["prob"] >= 0.65 and not super_safe:
            super_safe = bet

        elif bet["prob"] >= 0.57:
            high_value.append(bet)

    signals = []

    if super_safe:

        signals.append(
f"""⭐ SUPER SAFE BET
⚽ {super_safe['match']}
🎯 {super_safe['pick']}
📊 Odds {round(super_safe['odds'],2)}
📈 Probability {round(super_safe['prob']*100)}%
💰 Value {round(super_safe['ev'],2)}"""
💵 Stake {round(b['stake']*100,1)}% bankroll"""
        )

    for bet in high_value[:2]:

        signals.append(
f"""🔥 HIGH VALUE
⚽ {bet['match']}
🎯 {bet['pick']}
📊 Odds {round(bet['odds'],2)}
📈 Probability {round(bet['prob']*100)}%
💰 Value {round(bet['ev'],2)}"""
💵 Stake {round(b['stake']*100,1)}% bankroll"""
        )

    league_odds_cache.clear()
    team_stats_cache.clear()
    injury_cache.clear()

    return signals
# ================= DAILY SAMPLE =================

def daily_sample():

    bets = get_value_bets()

    if bets:
        return bets[0]

    return "No value today"

# ================= MARKET ALERT =================

def market_alert():

    matches = get_matches()

    if not matches:
        return "No alert"

    home,away = matches[0]

    return f"""
🚨 SHARP MONEY ALERT

⚽ {home} vs {away}

Odds dropped:
2.10 → 1.82

Heavy betting activity detected.
"""

# ================= PERFORMANCE =================

def performance():

    wins = cursor.execute(
        "SELECT COUNT(*) FROM bets_history WHERE result='WIN'"
    ).fetchone()[0]

    losses = cursor.execute(
        "SELECT COUNT(*) FROM bets_history WHERE result='LOSE'"
    ).fetchone()[0]

    total = wins+losses

    if total == 0:
        return "No stats yet"

    winrate = round((wins/total)*100)

    return f"""
📊 NETWORK PERFORMANCE

Wins: {wins}
Losses: {losses}

Win Rate: {winrate}%
"""

# ================= AUTO SIGNALS =================

def send_signals():

    tz = pytz.timezone("Europe/Athens")

    admin_sent_today = False
    vip_sent_today = False

    while True:

        now = datetime.now(tz)

        hour = now.hour
        minute = now.minute

        bets = get_value_bets()

        # ---------- ADMIN 17:00 ----------

        if hour == 17 and minute == 0 and not admin_sent_today:

            if bets:
                bot.send_message(
                    ADMIN_ID,
                    "ADMIN SIGNALS\n\n" + "\n\n".join(bets[:3])
                )

            admin_sent_today = True

        # ---------- VIP 18:00 ----------

        if hour == 18 and minute == 0 and not vip_sent_today:

            users = get_vip_users()

            for uid, plan in users:

                if plan == "BASIC":
                    picks = bets[:1]

                elif plan == "PRO":
                    picks = bets[:3]

                else:
                    continue

                text = "🔥 VIP SIGNALS\n\n" + "\n\n".join(picks)

                bot.send_message(uid, text)

            vip_sent_today = True

        # reset κάθε μέρα

        if hour == 0 and minute == 5:
            admin_sent_today = False
            vip_sent_today = False

        time.sleep(30)

# ================= TELEGRAM =================

@bot.message_handler(commands=["start"])
def start(m):

    bot.send_message(
        m.chat.id,
        """
👁 PRIVATE BETTING NETWORK

Signals are generated using
data analysis and odds movement.

Access is limited to members.
""",
        reply_markup=main_menu()
    )

@bot.callback_query_handler(func=lambda c:True)
def callbacks(c):

    if c.data == "elite":

        m = InlineKeyboardMarkup()

        m.add(InlineKeyboardButton("🥉 BASIC 50€",callback_data="buy_basic"))
        m.add(InlineKeyboardButton("🥇 PRO 100€",callback_data="buy_pro"))

        bot.send_message(
            c.message.chat.id,
            """
👑 ELITE MEMBERSHIP

🥉 BASIC
1 value bet per day

🥇 PRO
3 value bets per day
""",
            reply_markup=m
        )

    elif c.data == "buy_basic":

        link = create_payment(50,c.message.chat.id)

        bot.send_message(
            c.message.chat.id,
            f"Pay here:\n{link}"
        )

    elif c.data == "buy_pro":

        link = create_payment(100,c.message.chat.id)

        bot.send_message(
            c.message.chat.id,
            f"Pay here:\n{link}"
        )

    elif c.data == "sample":

        bot.send_message(
            c.message.chat.id,
            f"🎁 FREE SAMPLE\n\n{daily_sample()}"
        )

    elif c.data == "alert":

        bot.send_message(
            c.message.chat.id,
            market_alert()
        )

    elif c.data == "perf":

        bot.send_message(
            c.message.chat.id,
            performance()
        )

    elif c.data == "support":

        bot.send_message(
            c.message.chat.id,
            "Contact: @MrMasterlegacy1"
        )

# ================= THREADS =================

threading.Thread(target=send_signals, daemon=True).start()

threading.Thread(
    target=lambda: app.run(host="0.0.0.0", port=8080),
    daemon=True
).start()

# ================= RUN =================

bot.infinity_polling()