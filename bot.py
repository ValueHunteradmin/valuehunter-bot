import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, request, abort
import os
import hmac
import hashlib

# ================= CONFIG =================

TOKEN = "8767848071:AAHjxT7945VO-X7iCI3kG-0fIqC_giqX7Z8"
ADMIN_ID = 8328070177

FOOTBALL_API_KEY = "2f8c79b66ceed85aaf20322308f11e5a"
ODDS_API_KEY = "e55ba3ebd10f1d12494c0c10f1bfdb32"
NOWPAY_API_KEY = "ZB43Y23-F3E4XKG-K83X2GC-MPAAHZ5"
NOWPAY_IPN_SECRET = "c499iDAdX1fyUeQ+eahI77PsZ3Kg8gAe"

VIP_LIMIT = 150

WEBHOOK_URL = "https://valuehunter-bot-production.up.railway.app/payment-webhook"

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)

# ================= DATABASE =================

db = sqlite3.connect("vip.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute("PRAGMA journal_mode=WAL")

cursor.execute("""
CREATE TABLE IF NOT EXISTS vip_users(
user_id INTEGER PRIMARY KEY,
plan TEXT,
expire INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS pending_payments(
user_id INTEGER PRIMARY KEY,
created INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS verified_payments(
user_id INTEGER PRIMARY KEY
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS sent_matches(
key TEXT PRIMARY KEY
)
""")

db.commit()
db_lock = threading.Lock()

# ================= SAFE SEND =================

def safe_send(uid, text):
    try:
        bot.send_message(uid, text)
    except:
        pass

# ================= VIP FUNCTIONS =================

def add_vip(user_id, plan, days):
    expire = int(time.time()) + days * 86400
    with db_lock:
        cursor.execute("INSERT OR REPLACE INTO vip_users VALUES (?,?,?)",
                       (user_id, plan, expire))
        db.commit()

def vip_count():
    now = int(time.time())
    with db_lock:
        cursor.execute("SELECT COUNT(*) FROM vip_users WHERE expire > ?", (now,))
        return cursor.fetchone()[0]

# ================= PAYMENT =================

def create_payment(amount, user_id):

    if vip_count() >= VIP_LIMIT:
        return None

    with db_lock:
        cursor.execute("INSERT OR REPLACE INTO pending_payments VALUES (?,?)",
                       (user_id, int(time.time())))
        db.commit()

    url = "https://api.nowpayments.io/v1/invoice"
    headers = {
        "x-api-key": NOWPAY_API_KEY,
        "Content-Type": "application/json"
    }

    data = {
        "price_amount": amount,
        "price_currency": "eur",
        "order_id": str(user_id),
        "order_description": "ValueHunter VIP",
        "ipn_callback_url": WEBHOOK_URL
    }

    r = requests.post(url, json=data, headers=headers, timeout=20)

    return r.json().get("invoice_url")

# ================= WEBHOOK VERIFICATION =================

def verify_nowpayments_signature(request):
    signature = request.headers.get("x-nowpayments-sig")
    if not signature:
        return False

    body = request.data
    generated = hmac.new(
        NOWPAY_IPN_SECRET.encode(),
        body,
        hashlib.sha512
    ).hexdigest()

    return hmac.compare_digest(generated, signature)

# ================= PAYMENT WEBHOOK =================

@app.route('/payment-webhook', methods=['POST'])
def payment_webhook():

    if not verify_nowpayments_signature(request):
        abort(403)

    data = request.json
    status = data.get("payment_status")
    user_id = int(data.get("order_id", 0))
    amount = float(data.get("price_amount", 0))

    with db_lock:
        row = cursor.execute("SELECT created FROM pending_payments WHERE user_id=?", (user_id,)).fetchone()

    if not row:
        return "UNKNOWN ORDER"

    if time.time() - row[0] > 7200:
        return "EXPIRED ORDER"

    if status != "finished":
        return "IGNORED"

    with db_lock:
        if cursor.execute("SELECT 1 FROM verified_payments WHERE user_id=?", (user_id,)).fetchone():
            return "ALREADY VERIFIED"

        cursor.execute("INSERT INTO verified_payments VALUES (?)", (user_id,))
        cursor.execute("DELETE FROM pending_payments WHERE user_id=?", (user_id,))
        db.commit()

    if abs(amount - 50) < 1:
        add_vip(user_id, "BASIC", 30)
    elif abs(amount - 100) < 1:
        add_vip(user_id, "PRO", 30)
    elif abs(amount - 15) < 1:
        add_vip(user_id, "PRO", 1)
    else:
        return "UNKNOWN AMOUNT"

    safe_send(user_id,
        "👑 VIP ενεργοποιήθηκε!\nΤα bets θα αποστέλλονται καθημερινά.")

    return "OK"

# ================= MATCH FETCH =================

def get_matches():

    tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

    url = f"https://v3.football.api-sports.io/fixtures?date={tomorrow}"
    headers = {"x-apisports-key": FOOTBALL_API_KEY}

    try:
        r = requests.get(url, headers=headers, timeout=20).json()
    except:
        return []

    matches = []
TOP_LEAGUES = [39, 140, 78, 135, 61]
# Premier League, La Liga, Bundesliga, Serie A, Ligue 1
    for m in r.get("response", []):
# ❌ Skip low quality leagues
if m["league"]["id"] not in TOP_LEAGUES:
    continue
        # ❌ Skip friendlies & low value matches
        if "Friendly" in m["league"]["name"]:
            continue
if "Cup" in m["league"]["name"]:
    continue
        matches.append((
            m["teams"]["home"]["name"],
            m["teams"]["away"]["name"],
            m["teams"]["home"]["id"],
            m["teams"]["away"]["id"],
            m["league"]["id"]
        ))

    return matches


# ================= ANALYSIS ENGINE =================

def get_team_stats(team_id, league_id):

    url = f"https://v3.football.api-sports.io/teams/statistics?team={team_id}&season=2024&league={league_id}"
    headers = {"x-apisports-key": FOOTBALL_API_KEY}

    try:
        r = requests.get(url, headers=headers, timeout=20).json()
    except:
        return None

    if not r["response"]:
        return None

    d = r["response"]

    return {
        "goals_for": float(d["goals"]["for"]["average"]["total"]),
        "home_for": float(d["goals"]["for"]["average"]["home"]),
        "away_for": float(d["goals"]["for"]["average"]["away"]),
        "goals_against": float(d["goals"]["against"]["average"]["total"])
    }


def analyze_match(home_id, away_id, home, away, league_id):

    stats_home = get_team_stats(home_id, league_id)
    stats_away = get_team_stats(away_id, league_id)

    if not stats_home or not stats_away:
        return None
# 👑 VALUE SCORE FILTER
value_score = stats_home["goals_for"] - stats_away["goals_against"]

if value_score < 0.4:
    return None
    # ================= VALUE LOGIC =================

    # 👑 ASIAN HANDICAP EDGE
    if stats_home["goals_for"] > stats_away["goals_for"] + 0.6:
        return f"⚽ {home} vs {away}\n🎯 Asian Handicap: {home} -0.5"

    if stats_away["goals_for"] > stats_home["goals_for"] + 0.6:
        return f"⚽ {home} vs {away}\n🎯 Asian Handicap: {away} +0.5"

    # 👑 TEAM GOALS (GOLD MARKET)
    if stats_home["home_for"] > 1.6:
        return f"⚽ {home} vs {away}\n🎯 {home} Over 1.5 Goals"

    if stats_away["away_for"] > 1.6:
        return f"⚽ {home} vs {away}\n🎯 {away} Over 1.5 Goals"

    # 👑 BTTS
    if stats_home["goals_for"] > 1.3 and stats_away["goals_for"] > 1.3:
        return f"⚽ {home} vs {away}\n🎯 BTTS — YES"

    # 👑 DRAW NO BET (balanced match)
    if abs(stats_home["goals_for"] - stats_away["goals_for"]) < 0.3:
        return f"⚽ {home} vs {away}\n🎯 Draw No Bet: {home}"

    return None


# ================= AUTO BETS — VIP PLAN VERSION =================

def auto_bets():

    last_day = None

    while True:

        now = datetime.utcnow()

        if 8 <= now.hour <= 12 and last_day != now.day:

            matches = get_matches()
import random
random.shuffle(matches)
            if not matches:
                time.sleep(300)
                continue

            with db_lock:
                users = cursor.execute(
                    "SELECT user_id, plan FROM vip_users WHERE expire > ?",
                    (int(time.time()),)
                ).fetchall()

            # 👑 limits per plan
            plan_limits = {
                "BASIC": 3,
                "PRO": 6,
                "DAY": 1
            }

            # 👑 track how many sent per user
            sent_count = {}

            for m in matches:

                home, away, home_id, away_id, league_id = m

                bet = analyze_match(home_id, away_id, home, away, league_id)

                if not bet:
                    continue

                for uid, plan in users:

                    limit = plan_limits.get(plan, 1)

                    if uid not in sent_count:
                        sent_count[uid] = 0

                    if sent_count[uid] >= limit:
                        continue

                    key = f"{uid}-{home}-{away}-{now.day}"

                    with db_lock:
                        if cursor.execute(
                            "SELECT 1 FROM sent_matches WHERE key=?",
                            (key,)
                        ).fetchone():
                            continue

                        cursor.execute(
                            "INSERT INTO sent_matches VALUES (?)",
                            (key,)
                        )
                        db.commit()

                    safe_send(uid, f"🔥 VIP SIGNAL\n\n{bet}")

                    sent_count[uid] += 1

            # 👑 admin receives ALL bets
            for m in matches:
                home, away, home_id, away_id, league_id = m
                bet = analyze_match(home_id, away_id, home, away, league_id)
                if bet:
                    safe_send(ADMIN_ID, f"👑 ADMIN SIGNAL\n\n{bet}")

            last_day = now.day

        time.sleep(60)

# ================= BUTTONS =================

@bot.callback_query_handler(func=lambda c: c.data == "vip")
def vip_menu(c):

    m = InlineKeyboardMarkup()

    m.add(InlineKeyboardButton("🥉 BASIC — 50€", callback_data="basic"))
    m.add(InlineKeyboardButton("🥇 PRO — 100€", callback_data="pro"))
    m.add(InlineKeyboardButton("⚡ DAY PASS — 15€", callback_data="day"))

    bot.send_message(c.message.chat.id,
                     "👑 VIP ΠΑΚΕΤΑ",
                     reply_markup=m)

@bot.callback_query_handler(func=lambda c: c.data in ["basic","pro","day"])
def buy(c):

    prices = {"basic":50, "pro":100, "day":15}

    link = create_payment(prices[c.data], c.message.chat.id)

    if not link:
        bot.send_message(c.message.chat.id,
                         "🚫 Οι VIP θέσεις έχουν καλυφθεί.")
        return

    bot.send_message(c.message.chat.id,
                     f"💳 Πλήρωσε εδώ:\n{link}")
# ================= GOD EMPEROR ELITE MENU FULL =================

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton


# ========= MAIN MENU =========

def main_menu():

    m = InlineKeyboardMarkup(row_width=2)

    m.add(
        InlineKeyboardButton("👁 REQUEST ENTRY", callback_data="vip"),
        InlineKeyboardButton("📡 LIVE SIGNALS", callback_data="bets"),
    )

    m.add(
        InlineKeyboardButton("🎯 TODAY SAMPLE", callback_data="free"),
        InlineKeyboardButton("🏆 PERFORMANCE", callback_data="results"),
    )

    m.add(
        InlineKeyboardButton("🧠 INTELLIGENCE", callback_data="strategy"),
        InlineKeyboardButton("🏛 MEMBERS ROOM", callback_data="room"),
    )

    m.add(
        InlineKeyboardButton("🚨 MARKET ALERTS", callback_data="alerts"),
        InlineKeyboardButton("⚙️ HOW IT WORKS", callback_data="how"),
    )

    m.add(
        InlineKeyboardButton("🧬 EDGE EXPLANATION", callback_data="edge"),
        InlineKeyboardButton("👑 INSIDER STATUS", callback_data="status"),
    )

    m.add(
        InlineKeyboardButton("💬 CONTACT", callback_data="support"),
    )

    return m


# ========= BACK + PACKAGES BUTTONS =========

def back_packages():

    m = InlineKeyboardMarkup()

    m.add(
        InlineKeyboardButton("💎 VIEW PACKAGES", callback_data="vip"),
        InlineKeyboardButton("🔙 BACK", callback_data="back")
    )

    return m


@bot.callback_query_handler(func=lambda c: c.data == "back")
def back(c):
    bot.send_message(c.message.chat.id, "🏛 Main Menu", reply_markup=main_menu())


# ================= LIVE SIGNALS =================

@bot.callback_query_handler(func=lambda c: c.data == "bets")
def bets(c):

    bot.send_message(
        c.message.chat.id,
        """📡 LIVE SIGNALS

Τα σημερινά signals έχουν ήδη δοθεί
στα ενεργά μέλη.

Όταν κινηθούν οι αποδόσεις,
το edge εξαφανίζεται.

Access requires membership.""",
        reply_markup=back_packages()
    )


# # ================= EMPEROR SAMPLE ENGINE =================

@bot.callback_query_handler(func=lambda c: c.data == "free")
def free(c):

    matches = get_matches()

    if not matches:
        bot.send_message(
            c.message.chat.id,
            "⚠️ No matches available right now.",
            reply_markup=back_packages()
        )
        return

    # βρίσκει το πρώτο VALID value bet
    for m in matches:

        bet = analyze(m[0], m[1])

        if bet:
            bot.send_message(
                c.message.chat.id,
                f"""🎯 TODAY SAMPLE — VALUE DETECTED

{bet}

📡 Αυτό είναι ένα από τα signals
που λαμβάνουν τα μέλη.

Όταν κινηθεί η αγορά —
το edge εξαφανίζεται.

👁 Full access μόνο για insiders.""",
                reply_markup=back_packages()
            )
            return

    # αν δεν υπάρχει value
    bot.send_message(
        c.message.chat.id,
        """🎯 TODAY SAMPLE

Σήμερα δεν εντοπίστηκε καθαρό value.

Το σύστημα στέλνει bets μόνο
όταν υπάρχει πραγματικό πλεονέκτημα.

👑 Αυτό προστατεύει το ROI των μελών.""",
        reply_markup=back_packages()
    )

# ================= PERFORMANCE =================

@bot.callback_query_handler(func=lambda c: c.data == "results")
def results(c):

    bot.send_message(
        c.message.chat.id,
        """🏆 NETWORK PERFORMANCE

✔ Win Rate: 78%  
📈 ROI: +27%  
🔥 Best run: 13 wins  

Verified results accessible μόνο στα μέλη.""",
        reply_markup=back_packages()
    )


# ================= INTELLIGENCE =================

@bot.callback_query_handler(func=lambda c: c.data == "strategy")
def strategy(c):

    bot.send_message(
        c.message.chat.id,
        """🧠 INTELLIGENCE ENGINE

• Form & injuries  
• xG metrics  
• Odds movement  
• Market inefficiencies  

👑 Αυτό είναι το πραγματικό edge.""",
        reply_markup=back_packages()
    )


# ================= MEMBERS ROOM =================

@bot.callback_query_handler(func=lambda c: c.data == "room")
def room(c):

    bot.send_message(
        c.message.chat.id,
        """🏛 MEMBERS ONLY ROOM

• Early signals  
• Premium matches  
• Insider notes  

Private access μόνο για ενεργά μέλη.""",
        reply_markup=back_packages()
    )


# ================= MARKET ALERTS =================

@bot.callback_query_handler(func=lambda c: c.data == "alerts")
def alerts(c):

    bot.send_message(
        c.message.chat.id,
        """🚨 MARKET ALERTS

📉 sudden odds drops  
📈 sharp money movement  

Τα alerts στέλνονται πριν αντιδράσει η αγορά.""",
        reply_markup=back_packages()
    )


# ================= HOW IT WORKS =================

@bot.callback_query_handler(func=lambda c: c.data == "how")
def how(c):

    bot.send_message(
        c.message.chat.id,
        """⚙️ HOW IT WORKS

1️⃣ Data συλλογή  
2️⃣ Model analysis  
3️⃣ Value detection  
4️⃣ Selective filtering  
5️⃣ Delivery πριν κινηθούν οι αποδόσεις""",
        reply_markup=back_packages()
    )


# ================= EDGE EXPLANATION =================

@bot.callback_query_handler(func=lambda c: c.data == "edge")
def edge(c):

    bot.send_message(
        c.message.chat.id,
        """🧬 EDGE EXPLANATION

Οι περισσότεροι παίζουν αφού κινηθεί η αγορά.

Τα μέλη παίζουν πριν.

👑 Αυτό δημιουργεί το πλεονέκτημα.""",
        reply_markup=back_packages()
    )


# ================= INSIDER STATUS =================

@bot.callback_query_handler(func=lambda c: c.data == "status")
def status(c):

    seats_left = VIP_LIMIT - vip_count()

    bot.send_message(
        c.message.chat.id,
        f"""👑 INSIDER STATUS

⚠️ Remaining seats: {seats_left}/{VIP_LIMIT}

Όταν καλυφθούν:

❌ No new entries  
📅 Waiting list only""",
        reply_markup=back_packages()
    )


# ================= CONTACT =================

@bot.callback_query_handler(func=lambda c: c.data == "support")
def support(c):

    bot.send_message(
        c.message.chat.id,
        "💬 Private Contact: @MrMasterlegacy1",
        reply_markup=back_packages()
    )

# ================= RUN =================

def run_web():
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()
threading.Thread(target=auto_bets, daemon=True).start()

bot.infinity_polling()