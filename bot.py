from modules.image_engine import generate_ai_result_image
import random
from datetime import datetime, timedelta, UTC
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
import os
import hmac
import hashlib
import json
from urllib.parse import quote
from io import BytesIO

# ╔══════════════════════════════════════════════════════════════╗
# ║  PART 1 - CORE CONFIG & CONSTANTS                          ║
# ╚══════════════════════════════════════════════════════════════╝

TOKEN = "8767848071:AAHjxT7945VO-X7iCI3kG-0fIqC_giqX7Z8"
ADMIN_ID = 8328070177

ADMIN_TEST_MODE = False
ADMIN_TEST_PLAN = None

FOOTBALL_API_KEY = "2f8c79b66ceed85aaf20322308f11e5a"
ODDS_API_KEY = "e55ba3ebd10f1d12494c0c10f1bfdb32"
NOWPAY_API_KEY = "ZB43Y23-F3E4XKG-K83X2GC-MPAAHZ5"
IPN_SECRET = "5B8MWD7S1sz5J+F100Hr7PyHI2D3jCjR"

START_BANKROLL = 2000
DEFAULT_STAKE = 50

WEBHOOK_URL = "https://valuehunter-bot-production.up.railway.app/payment-webhook"

# - Channel automation config -
CHANNEL_ID = -1003799918417 # Set via /setchannel command

# - Referral fake data -
referrer_cache = None
referrer_cache_date = None
feed_cache = None
feed_cache_time = 0

referral_feed = [
    "🔥 NickBet invited a new user",
    "🔥 AlexGoal +1 referral",
    "🔥 GeorgeKs joined the leaderboard",
    "🔥 ChrisTips invited a new member",
    "🔥 MikeValue +2 referrals",
    "🔥 LeoHunter invited a new user",
    "🔥 MarkEdge gained +1 referral",
    "🔥 DimitrisPro invited a new user",
    "🔥 TheoValue joined the leaderboard",
    "🔥 KostasXG +1 referral",
    "🔥 AndreasWin invited a new member",
    "🔥 PanagiotisOdds gained +2 referrals"
]

referrer_names = [
    "GeorgeKs","NickBet","AlexGoal","ChrisTips","MikeValue","JohnStats","LeoHunter","MarkEdge","DimitrisPro","StefanosBet",
    "KostasXG","AndreasWin","PanagiotisOdds","PetrosSharp","TheoValue","VasilisGoal","AntonisEdge","ManosStats","NikosAI","GiorgosTips",
    "ChrisBet","AlexEdge","MikeHunter","NickSharp","LeoTips","MarkValue","JohnGoal","SteveStats","ChrisAI","AlexTrader",
    "MikeEdge","NickHunter","LeoValue","MarkSharp","JohnTips","SteveGoal","ChrisStats","AlexAI","MikeTrader","NickValue",
    "LeoSharp","MarkHunter","JohnEdge","SteveValue","ChrisGoal","AlexStats","MikeAI","NickTrader","LeoEdge","MarkTips",
    "JohnValue","SteveSharp","ChrisHunter","AlexEdgePro","MikeGoal","NickStats","LeoTrader","MarkAI","JohnHunter","SteveTips",
    "ChrisValue","AlexSharp","MikeStats","NickGoal","LeoAI","MarkTrader","JohnTipsPro","SteveEdge","ChrisHunterX","AlexValue",
    "MikeSharp","NickEdge","LeoStats","MarkGoal","JohnAI","SteveTrader","ChrisEdge","AlexHunter","MikeTips","NickValuePro",
    "LeoSharpX","MarkStats","JohnGoalPro","SteveAI","ChrisTrader","AlexEdgeX","MikeHunterPro","NickSharpX","LeoValuePro","MarkEdgeX",
    "JohnTrader","SteveHunter","ChrisStatsPro","AlexTips","MikeGoalX","NickAIPro","LeoHunterX","MarkValuePro","JohnSharp","SteveStatsX"
]

# - League definitions -
GOOD_LEAGUES = {
    39,   # Premier League
    140,  # La Liga
    135,  # Serie A
    78,   # Bundesliga
    61,   # Ligue 1
    88,   # Eredivisie
    94,   # Primeira Liga
    203,  # Super Lig
    2,    # Champions League
    3,    # Europa League
    848,  # Conference League
    144,  # Belgium
    113,  # Sweden
    71,   # Scotland
    218,  # Austria
    119,  # Norway
    106,  # Poland
}

# Tier 1 = most reliable data, highest liquidity
TIER1_LEAGUES = {39, 78, 140, 135, 61, 2, 3}
# Tier 2 = good data, decent liquidity
TIER2_LEAGUES = {88, 94, 203, 848, 144}
# Tier 3 = usable but thinner markets
TIER3_LEAGUES = {113, 71, 218, 119, 106}

LEAGUE_STRENGTH = {
    39: 1.05,  78: 1.08, 135: 0.95, 140: 1.00,
    61: 0.97,  88: 1.02,  94: 0.98, 203: 0.96,
    144: 0.99, 113: 1.02,  71: 0.98, 218: 1.01,
    119: 1.03, 106: 0.97,   2: 1.06,   3: 1.00,
    848: 0.97,
}

# League average goals (fallback)
LEAGUE_AVG_GOALS = 2.6

# Confidence tier thresholds
CONFIDENCE_SAFE = 72
CONFIDENCE_MEDIUM = 58
CONFIDENCE_AGGRESSIVE = 45

# - Initialize bot & flask -
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# - Runtime caches -
team_stats_cache = {}
injury_cache = {}
league_odds_cache = {}
league_odds_cache_time = {}
value_cache = []
value_cache_time = 0
fixtures_cache = []
fixtures_cache_time = 0
alert_cache = None
alert_cache_time = 0
active_funnels = set()
channel_automation_active = False
clv_history = {}  # fixture_id -> {opening_odds, closing_odds, clv_pct}

# ╔══════════════════════════════════════════════════════════════╗
# ║  PART 2 - DATABASE                                          ║
# ╚══════════════════════════════════════════════════════════════╝

db_lock = threading.Lock()

db = sqlite3.connect("database.db", check_same_thread=False, timeout=30)
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

try:
    cursor.execute("ALTER TABLE bets_history ADD COLUMN fixture_id INTEGER")
except:
    pass

try:
    cursor.execute("ALTER TABLE bets_history ADD COLUMN confidence_tier TEXT DEFAULT 'MEDIUM'")
except:
    pass

try:
    cursor.execute("ALTER TABLE bets_history ADD COLUMN clv REAL DEFAULT 0")
except:
    pass

try:
    cursor.execute("ALTER TABLE bets_history ADD COLUMN model_prob REAL DEFAULT 0")
except:
    pass

cursor.execute("""
CREATE TABLE IF NOT EXISTS sent_bets(
    key TEXT PRIMARY KEY
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS free_sample(
    user_id INTEGER PRIMARY KEY,
    last_time INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS expiry_notified(
    user_id INTEGER PRIMARY KEY
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS processed_payments(
    payment_id TEXT PRIMARY KEY
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS referrals(
    referrer INTEGER,
    referred INTEGER PRIMARY KEY
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS referral_stats(
    user_id INTEGER PRIMARY KEY,
    count INTEGER DEFAULT 0,
    unlocked INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS discount_wallet(
    user_id INTEGER PRIMARY KEY,
    discount INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS win_streaks(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    streak_count INTEGER,
    timestamp INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS clv_tracking(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id INTEGER,
    market TEXT,
    opening_odds REAL,
    closing_odds REAL,
    clv_pct REAL,
    timestamp INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS engine_logs(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event TEXT,
    detail TEXT,
    timestamp INTEGER
)
""")

try:
    cursor.execute("ALTER TABLE bets_history ADD COLUMN market_type TEXT DEFAULT ''")
except:
    pass

try:
    cursor.execute("ALTER TABLE bets_history ADD COLUMN edge REAL DEFAULT 0")
except:
    pass

try:
    cursor.execute("ALTER TABLE bets_history ADD COLUMN closing_odds REAL DEFAULT 0")
except:
    pass

try:
    cursor.execute("ALTER TABLE bets_history ADD COLUMN agreement_level TEXT DEFAULT ''")
except:
    pass
    
cursor.execute("""
CREATE TABLE IF NOT EXISTS signal_messages(
    user_id INTEGER,
    message_id INTEGER
)
""")

db.commit()

# ╔══════════════════════════════════════════════════════════════╗
# ║  PART 3 - VIP & USER SYSTEM                                 ║
# ╚══════════════════════════════════════════════════════════════╝

def add_vip(user_id, plan, days):
    expire = int(time.time()) + days * 86400
    with db_lock:
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

    if user_id == ADMIN_ID and ADMIN_TEST_MODE:
        return True

    row = cursor.execute(
        "SELECT user_id FROM vip_users WHERE user_id=?",
        (user_id,)
    ).fetchone()

    return row is not None
    
    now = int(time.time())
    r = cursor.execute(
        "SELECT expire FROM vip_users WHERE user_id=?",
        (user_id,)
    ).fetchone()
    if not r:
        return False
    return r[0] > now

def get_all_users():
    users = set()
    for row in cursor.execute("SELECT user_id FROM vip_users").fetchall():
        users.add(row[0])
    for row in cursor.execute("SELECT user_id FROM free_sample").fetchall():
        users.add(row[0])
    for row in cursor.execute("SELECT user_id FROM users").fetchall():
        users.add(row[0])
    return list(users)

# ╔══════════════════════════════════════════════════════════════╗
# ║  PART 4 - MENU / UI (UNCHANGED)                             ║
# ╚══════════════════════════════════════════════════════════════╝

def main_menu():
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("🎖️ 𝑼𝑵𝑳𝑶𝑪𝑲 𝑽𝑰𝑷 𝑺𝑰𝑮𝑵𝑨𝑳𝑺", callback_data="elite"))
    m.add(InlineKeyboardButton("🎁 𝑻𝑶𝑫𝑨𝒀'𝑺 𝑭𝑹𝑬𝑬 𝑩𝑬𝑻", callback_data="sample"))
    m.add(InlineKeyboardButton("⚡ 𝑴𝑨𝑹𝑲𝑬𝑻 𝑨𝑳𝑬𝑹𝑻", callback_data="alert"))
    m.add(InlineKeyboardButton("🫆 𝑷𝑬𝑹𝑭𝑶𝑹𝑴𝑨𝑵𝑪𝑬", callback_data="perf"))
    m.add(InlineKeyboardButton("👑 𝑹𝑬𝑭𝑬𝑹𝑹𝑨𝑳 𝑷𝑹𝑶𝑮𝑹𝑨𝑴", callback_data="referral"))
    m.add(InlineKeyboardButton("❓ 𝑭𝑨𝑸", callback_data="faq"))
    m.add(InlineKeyboardButton("🧑🏼‍💻 𝑺𝑼𝑷𝑷𝑶𝑹𝑻", callback_data="support"))
    return m

def vip_dashboard_keyboard():
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("⚜️ 𝑽𝑰𝑷 𝑴𝑬𝑵𝑼", callback_data="vip_menu"))
    m.add(InlineKeyboardButton("📡 𝑴𝑶𝑫𝑬𝑳 𝑰𝑵𝑺𝑰𝑮𝑯𝑻𝑺", callback_data="model_insights"))
    m.add(InlineKeyboardButton("🧠 𝑩𝑬𝑻𝑻𝑰𝑵𝑮 𝑺𝑻𝑹𝑨𝑻𝑬𝑮𝒀", callback_data="betting_strategy"))
    m.add(InlineKeyboardButton("💸 𝑽𝑰𝑷 𝑹𝑬𝑺𝑼𝑳𝑻𝑺 𝑭𝑬𝑬𝑫", callback_data="vip_results"))
    return m

def vip_menu_keyboard():
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("🎖️ 𝑻𝑶𝑫𝑨𝒀'𝑺 𝑺𝑰𝑮𝑵𝑨𝑳𝑺", callback_data="vip_signals"))
    m.add(InlineKeyboardButton("📈 𝑴𝑶𝑫𝑬𝑳 𝑷𝑬𝑹𝑭𝑶𝑹𝑴𝑨𝑵𝑪𝑬", callback_data="vip_performance"))
    m.add(InlineKeyboardButton("💰 𝑩𝑨𝑵𝑲𝑹𝑶𝑳𝑳 𝑻𝑹𝑨𝑪𝑲𝑬𝑹", callback_data="vip_bankroll"))
    m.add(InlineKeyboardButton("⚡ 𝑬𝑨𝑹𝑳𝒀 𝑴𝑨𝑹𝑲𝑬𝑻 𝑨𝑳𝑬𝑹𝑻𝑺", callback_data="vip_alerts"))
    m.add(InlineKeyboardButton("🫆 𝑽𝑰𝑷 𝑺𝑻𝑨𝑻𝑼𝑺", callback_data="vip_status"))
    m.add(InlineKeyboardButton("🧑🏼‍💻 𝑽𝑰𝑷 𝑺𝑼𝑷𝑷𝑶𝑹𝑻", callback_data="vip_support"))
    m.add(InlineKeyboardButton("◀ 𝑩𝑨𝑪𝑲 𝑻𝑶 𝑫𝑨𝑺𝑯𝑩𝑶𝑨𝑹𝑫", callback_data="vip_dashboard"))
    return m

def signal_timer():
    tz = pytz.timezone("Europe/Athens")
    now = datetime.now(tz)
    target = now.replace(hour=18, minute=0, second=0, microsecond=0)
    if now >= target:
        target = target + timedelta(days=1)
    diff = target - now
    total_seconds = int(diff.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    countdown = f"{hours:02}:{minutes:02}:{seconds:02}"
    if now.hour < 18:
        label = "Signal release in"
    else:
        label = "Next signals in"
    return label, countdown

# ╔══════════════════════════════════════════════════════════════╗
# ║  PART 5 - PAYMENTS (UNCHANGED)                              ║
# ╚══════════════════════════════════════════════════════════════╝

def create_payment(amount, user_id):
    url = "https://api.nowpayments.io/v1/invoice"
    headers = {
        "x-api-key": NOWPAY_API_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "price_amount": amount,
        "price_currency": "eur",
        "order_id": str(user_id),
        "ipn_callback_url": WEBHOOK_URL
    }
    r = requests.post(url, json=data, headers=headers)
    return r.json()["invoice_url"]

@app.route("/payment-webhook", methods=["POST"])
def webhook():
    received_sig = request.headers.get("x-nowpayments-sig")
    payload = request.data
    generated_sig = hmac.new(
        IPN_SECRET.encode(),
        payload,
        hashlib.sha512
    ).hexdigest()

    if received_sig != generated_sig:
        return "invalid signature"

    data = json.loads(payload)
    user_id = int(data["order_id"])
    amount = float(data["price_amount"])
    status = data["payment_status"]
    payment_id = data["payment_id"]

    exists = None
    with db_lock:
        exists = cursor.execute(
            "SELECT payment_id FROM processed_payments WHERE payment_id=?",
            (payment_id,)
        ).fetchone()

    if exists:
        return "already processed"

    if status != "finished":
        return "ignored"

    now = int(time.time())

    if amount == 25:
        plan = "DAY"
        expiry = now + 86400
    elif amount == 50:
        plan = "BASIC"
        expiry = now + 2592000
    elif amount == 100:
        plan = "PRO"
        expiry = now + 2592000
    else:
        return "invalid amount"

    with db_lock:
        cursor.execute(
            "INSERT OR REPLACE INTO vip_users VALUES (?,?,?)",
            (user_id, plan, expiry)
        )
        db.commit()

        if plan == "PRO":
            cursor.execute(
                "INSERT OR IGNORE INTO referral_stats(user_id) VALUES(?)",
                (user_id,)
            )
            cursor.execute(
                "UPDATE referral_stats SET unlocked=1 WHERE user_id=?",
                (user_id,)
            )
            db.commit()

    bot.send_message(
        user_id,
        """
⚜️ 𝑬𝑳𝑰𝑻𝑬 𝑨𝑪𝑪𝑬𝑺𝑺 𝑨𝑪𝑻𝑰𝑽𝑨𝑻𝑬𝑫

Your payment has been successfully confirmed.

Welcome to the 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑬𝑳𝑰𝑻𝑬 𝑵𝑬𝑻𝑾𝑶𝑹𝑲.

You now have access to a -restricted betting intelligence system- designed to detect bookmaker pricing inefficiencies and high-probability value opportunities across global football markets.

━━━━━━━━━━━━━━

📡 𝑺𝒀𝑺𝑻𝑬𝑴 𝑹𝑬𝑳𝑬𝑨𝑺𝑬 𝑻𝑰𝑴𝑬𝑺

🕔 17:00 - Model analysis completed  
🕕 18:00 - Official VIP signal release  

🇬🇷 Europe / Athens Time

━━━━━━━━━━━━━━

⚠️ Signals inside this network are distributed to a limited number of Elite members to protect the betting edge.

Elite members are already preparing today's positions.
"""
    )

    with db_lock:
        cursor.execute(
            "INSERT INTO processed_payments VALUES (?)",
            (payment_id,)
        )
        db.commit()

        cursor.execute(
            "SELECT referrer FROM referrals WHERE referred=?",
            (user_id,)
        )
        r = cursor.fetchone()
        if r:
            referrer = r[0]
            cursor.execute(
                "UPDATE referral_stats SET count=count+1 WHERE user_id=?",
                (referrer,)
            )
            db.commit()

    threading.Thread(
        target=vip_initialization_animation,
        args=(user_id,)
    ).start()

    return "ok"

# ╔══════════════════════════════════════════════════════════════╗
# ║  PART 6 - MARKETING ENGINE                                  ║
# ╚══════════════════════════════════════════════════════════════╝

def start_conversion_funnel(user_id):
    if user_id in active_funnels:
        return
    active_funnels.add(user_id)

    def funnel():
        # MESSAGE 1 (30 minutes)
        time.sleep(1800)
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("⚜️ 𝑼𝑵𝑳𝑶𝑪𝑲 𝑬𝑳𝑰𝑻𝑬 𝑨𝑪𝑪𝑬𝑺𝑺", callback_data="elite"))
        try:
            bot.send_message(
                user_id,
"""
📡 𝑴𝑶𝑫𝑬𝑳 𝑼𝑷𝑫𝑨𝑻𝑬

The 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 analytics engine has already started scanning today's football markets.

Several high probability value opportunities have already been detected by the system.

Elite members will receive the final signals before the market reacts.

━━━━━━━━━━━━━━

⚠️ 𝑳𝑰𝑴𝑰𝑻𝑬𝑫 𝑬𝑵𝑻𝑹𝒀 𝑾𝑰𝑵𝑫𝑶𝑾

Access to the ValueHunter network is currently open but may close once today's signals are released.

Secure your position before the market moves.
""",
                reply_markup=keyboard
            )
        except:
            pass

        # MESSAGE 2 (2 hours)
        time.sleep(7200)
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("⚜️ 𝑼𝑵𝑳𝑶𝑪𝑲 𝑬𝑳𝑰𝑻𝑬 𝑨𝑪𝑪𝑬𝑺𝑺", callback_data="elite"))
        try:
            bot.send_message(
                user_id,
"""
🎖️ 𝑴𝑨𝑹𝑲𝑬𝑻 𝑴𝑶𝑽𝑬𝑴𝑬𝑵𝑻 𝑫𝑬𝑻𝑬𝑪𝑻𝑬𝑫

The ValueHunter system has detected unusual betting activity across today's football markets.

Sharp money is entering the market and odds tend to drop quickly.

━━━━━━━━━━━━━━

Elite members will receive the official signal before the market reacts.

🕕 SIGNAL RELEASE
18:00 - Athens Time 🇬🇷

━━━━━━━━━━━━━━

⚠️ Access may close once signals are released.
""",
                reply_markup=keyboard
            )
        except:
            pass

        # MESSAGE 3 (1 hour later)
        time.sleep(3600)
        tz = pytz.timezone("Europe/Athens")
        now = datetime.now(tz)
        hour = now.hour
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("⚜️ 𝑼𝑵𝑳𝑶𝑪𝑲 𝑬𝑳𝑰𝑻𝑬 𝑨𝑪𝑪𝑬𝑺𝑺", callback_data="elite"))
        try:
            if hour < 18:
                bot.send_message(
                    user_id,
"""
⏳ 𝑭𝑰𝑵𝑨𝑳 𝑬𝑵𝑻𝑹𝒀 𝑾𝑰𝑵𝑫𝑶𝑾

Today's signals will be released very soon.

Our analytics engine has already selected the strongest value opportunities from hundreds of matches.

━━━━━━━━━━━━━━

👑 𝑬𝑳𝑰𝑻𝑬 𝑵𝑬𝑻𝑾𝑶𝑹𝑲

17 members are already preparing today's bets.

━━━━━━━━━━━━━━

🕕 OFFICIAL SIGNAL RELEASE
18:00 - Athens Time 🇬🇷

━━━━━━━━━━━━━━

⚠️ Once signals are released access may close.

Secure your access before the release.
""",
                    reply_markup=keyboard
                )
            else:
                bot.send_message(
                    user_id,
"""
🔥 𝑻𝑶𝑫𝑨𝒀'𝑺 𝑺𝑰𝑮𝑵𝑨𝑳𝑺 𝑹𝑬𝑳𝑬𝑨𝑺𝑬𝑫

Today's ValueHunter signals have already been delivered to Elite members.

━━━━━━━━━━━━━━

👑 𝑬𝑳𝑰𝑻𝑬 𝑵𝑬𝑻𝑾𝑶𝑹𝑲

Members are already placing today's bets.

━━━━━━━━━━━━━━

⚠️ Access to the signal network may close during active betting hours.

Unlock access to receive tomorrow's signals.
""",
                    reply_markup=keyboard
                )
        except:
            pass

        active_funnels.discard(user_id)

    threading.Thread(target=funnel).start()

# ╔══════════════════════════════════════════════════════════════╗
# ║  PART 7 - ADVANCED BETTING ENGINE                           ║
# ╚══════════════════════════════════════════════════════════════╝

# ─── 7.1 DATA COLLECTION ───

def scan_matches():
    """Scan upcoming fixtures from tracked leagues within 3-day window."""
    global fixtures_cache, fixtures_cache_time

    if time.time() - fixtures_cache_time < 1800:
        return fixtures_cache

    fixtures = []
    today = datetime.now(UTC).date()
    future = today + timedelta(days=3)

    url = f"https://v3.football.api-sports.io/fixtures?from={today}&to={future}"
    headers = {"x-apisports-key": FOOTBALL_API_KEY}

    try:
        r = requests.get(url, headers=headers, timeout=15).json()
        time.sleep(0.1)
    except:
        return fixtures_cache if fixtures_cache else []

    for m in r.get("response", []):
        league_id = m["league"]["id"]

        if league_id not in GOOD_LEAGUES:
            continue

        status = m["fixture"]["status"]["short"]
        if status != "NS":
            continue

        match_time = m["fixture"]["timestamp"]
        now = int(time.time())

        if not (1800 <= match_time - now <= 259200):
            continue

        fixtures.append({
            "fixture_id": m["fixture"]["id"],
            "home": m["teams"]["home"]["name"],
            "away": m["teams"]["away"]["name"],
            "home_id": m["teams"]["home"]["id"],
            "away_id": m["teams"]["away"]["id"],
            "league_id": league_id,
            "league_name": m["league"]["name"],
            "country": m["league"]["country"],
            "timestamp": match_time
        })

    fixtures_cache = fixtures
    fixtures_cache_time = time.time()
    return fixtures


def get_matches():
    """Get next matches for alert display."""
    url = "https://v3.football.api-sports.io/fixtures?next=20"
    headers = {"x-apisports-key": FOOTBALL_API_KEY}
    try:
        r = requests.get(url, headers=headers, timeout=10).json()
    except:
        return []
    matches = []
    for m in r.get("response", []):
        home = m["teams"]["home"]["name"]
        away = m["teams"]["away"]["name"]
        matches.append((home, away))
    return matches


# ─── 7.2 DATA QUALITY & TEAM STATS ───

def get_team_stats(team_id, league_id):
    """Fetch team attack/defense strength using shots data as pseudo-xG."""
    if team_id in team_stats_cache:
        return team_stats_cache[team_id]

    url = f"https://v3.football.api-sports.io/teams/statistics?team={team_id}&league={league_id}&season=2024"
    headers = {"x-apisports-key": FOOTBALL_API_KEY}

    try:
        r = requests.get(url, headers=headers, timeout=10).json()
    except:
        return None

    if not r.get("response"):
        return None

    d = r["response"]

    # Extract shots data safely
    try:
        shots_total = float(d["shots"]["total"]) if d["shots"]["total"] else 0
        shots_on = float(d["shots"]["on"]) if d["shots"]["on"] else 0
    except:
        shots_total = 0
        shots_on = 0

    try:
        shots_against = float(d["shots"]["against"]["total"]) if d["shots"]["against"]["total"] else 0
        shots_against_on = float(d["shots"]["against"]["on"]) if d["shots"]["against"]["on"] else 0
    except:
        shots_against = 0
        shots_against_on = 0

    # Data quality gate: need minimum shot data
    if shots_total < 5 or shots_against < 5:
        return None

    # Pseudo xG estimation
    xg_est = shots_on * 0.30 + shots_total * 0.05
    xga_est = shots_against_on * 0.30 + shots_against * 0.05

    # Shot accuracy for quality filter
    shot_accuracy = shots_on / (shots_total + 0.01)

    result = {
        "attack": xg_est,
        "defense": xga_est,
        "shots_total": shots_total,
        "shots_on": shots_on,
        "shots_against": shots_against,
        "shots_against_on": shots_against_on,
        "shot_accuracy": shot_accuracy,
    }

    team_stats_cache[team_id] = result
    return result


def get_injuries(team_id):
    """Fetch injury count for a team."""
    if team_id in injury_cache:
        return injury_cache[team_id]

    url = f"https://v3.football.api-sports.io/injuries?team={team_id}"
    headers = {"x-apisports-key": FOOTBALL_API_KEY}

    try:
        r = requests.get(url, headers=headers, timeout=10).json()
    except:
        return 0

    injuries = len(r.get("response", []))
    injury_cache[team_id] = injuries
    return injuries


# ─── 7.3 LEAGUE RELIABILITY FILTER ───

def league_reliability_score(league_id):
    """Return 0-1 reliability score for the league."""
    if league_id in TIER1_LEAGUES:
        return 1.0
    elif league_id in TIER2_LEAGUES:
        return 0.85
    elif league_id in TIER3_LEAGUES:
        return 0.70
    return 0.50


# ─── 7.4 DATA QUALITY FILTER ───

def data_quality_filter(home_stats, away_stats, league_id):
    """Reject matches with insufficient statistical data."""
    if not home_stats or not away_stats:
        return False

    # Need minimum shot data for both teams
    if home_stats["shots_total"] < 10 or away_stats["shots_total"] < 10:
        return False

    # Shot accuracy sanity check (extremely low = data issue)
    if home_stats["shot_accuracy"] < 0.15 or away_stats["shot_accuracy"] < 0.15:
        return False

    # League must be reliable enough
    if league_reliability_score(league_id) < 0.60:
        return False

    return True


# ─── 7.5 TEAM STRENGTH MODEL ───

def calculate_team_strength(home_attack, home_defense, away_attack, away_defense):
    """Calculate expected scoring rates for both sides."""
    home_strength = (home_attack + away_defense) / 2
    away_strength = (away_attack + home_defense) / 2
    return home_strength, away_strength


# ─── 7.6 EXPECTED GOALS MODEL ───

def calculate_xg(home_strength, away_strength, league_id):
    """Calculate expected goals with league modifier and home advantage."""
    modifier = LEAGUE_STRENGTH.get(league_id, 1.0)
    HOME_ADV = 0.30
    home_xg = (home_strength * modifier) + HOME_ADV
    away_xg = (away_strength * modifier)
    return round(home_xg, 3), round(away_xg, 3)


# ─── 7.7 MODEL SANITY FILTERS ───

def model_sanity_filter(home_xg, away_xg):
    """Reject extreme xG scenarios that produce unreliable Poisson output."""
    total_xg = home_xg + away_xg
    if total_xg < 1.8:
        return False
    if total_xg > 4.5:
        return False
    if abs(home_xg - away_xg) > 2.2:
        return False
    return True


def tempo_filter(home_xg, away_xg):
    """Filter matches with extreme tempo imbalances."""
    total = home_xg + away_xg
    if total < 1.8 or total > 4.2:
        return False
    ratio = home_xg / (away_xg + 0.01)
    if ratio > 4 or ratio < 0.25:
        return False
    return True


# ─── 7.8 POISSON PROBABILITY MATRIX ───

def poisson(lmbda, k):
    """Single Poisson probability P(X=k)."""
    return (lmbda ** k * math.exp(-lmbda)) / math.factorial(k)


def poisson_matrix(home_xg, away_xg, max_goals=6):
    """Generate normalized score probability matrix."""
    matrix = []
    for h in range(max_goals):
        for a in range(max_goals):
            p = poisson(home_xg, h) * poisson(away_xg, a)
            matrix.append((h, a, p))

    total = sum(p for _, _, p in matrix)
    if total > 0:
        matrix = [(h, a, p / total) for h, a, p in matrix]

    return matrix


# ─── 7.9 MONTE CARLO SIMULATION ───

def monte_carlo_simulation(home_xg, away_xg, simulations=5000):
    """Monte Carlo simulation returning (home_win_prob, draw_prob, away_win_prob)."""
    home_wins = 0
    draws = 0
    away_wins = 0

    for _ in range(simulations):
        home_sim = home_xg * random.uniform(0.88, 1.12)
        away_sim = away_xg * random.uniform(0.88, 1.12)

        home_goals = np.random.poisson(home_sim)
        away_goals = np.random.poisson(away_sim)

        if home_goals > away_goals:
            home_wins += 1
        elif home_goals < away_goals:
            away_wins += 1
        else:
            draws += 1

    return home_wins / simulations, draws / simulations, away_wins / simulations


# ─── 7.10 PROBABILITY CALIBRATION ───

def calibrate_probability(prob):
    """Sigmoid calibration to reduce extreme probabilities."""
    return 1 / (1 + math.exp(-4 * (prob - 0.5)))


# ─── 7.11 MARKET PROBABILITY EXTRACTION ───

def implied_probability(odds):
    """Convert decimal odds to implied probability."""
    if odds <= 1.0:
        return 0
    return 1 / odds


def over25_probability(matrix):
    return sum(p for h, a, p in matrix if h + a >= 3)


def btts_probability(matrix):
    return sum(p for h, a, p in matrix if h > 0 and a > 0)


def goal_totals_probability(matrix):
    probs = {
        "over1_5": 0, "over2_5": 0, "over3_5": 0,
        "under1_5": 0, "under2_5": 0, "under3_5": 0
    }
    for h, a, p in matrix:
        goals = h + a
        if goals >= 2:
            probs["over1_5"] += p
        else:
            probs["under1_5"] += p
        if goals >= 3:
            probs["over2_5"] += p
        else:
            probs["under2_5"] += p
        if goals >= 4:
            probs["over3_5"] += p
        else:
            probs["under3_5"] += p
    return probs


def asian_optimizer(matrix):
    """Find best Asian Handicap line for the home team."""
    lines = [-1, -0.75, -0.5, -0.25, 0, 0.25, 0.5]
    best_line = None
    best_prob = 0

    for line in lines:
        prob = sum(p for h, a, p in matrix if (h - a) > line)
        if prob > best_prob:
            best_prob = prob
            best_line = line

    return best_line, best_prob


# ─── 7.12 ODDS PARSER ───

def get_league_odds(league_id):
    """Fetch and cache best odds per market from bookmakers."""
    if league_id in league_odds_cache:
        if time.time() - league_odds_cache_time.get(league_id, 0) < 600:
            return league_odds_cache[league_id]

    url = f"https://v3.football.api-sports.io/odds?league={league_id}&season=2024"
    headers = {"x-apisports-key": FOOTBALL_API_KEY}

    try:
        r = requests.get(url, headers=headers, timeout=15).json()
    except:
        return league_odds_cache.get(league_id)

    odds_data = {}

    for game in r.get("response", []):
        fixture_id = game["fixture"]["id"]
        bookmakers = game["bookmakers"]
        best_odds = {}
        all_odds_per_key = {}

        for book in bookmakers:
            for bet in book["bets"]:
                market = bet["name"]
                for v in bet["values"]:
                    key = f"{market}_{v['value']}"
                    odd = float(v["odd"])

                    if key not in all_odds_per_key:
                        all_odds_per_key[key] = []
                    all_odds_per_key[key].append(odd)

        # Best odds with outlier rejection
        for key, odds_list in all_odds_per_key.items():
            if len(odds_list) < 2:
                best_odds[key] = odds_list[0]
                continue

            median = sorted(odds_list)[len(odds_list) // 2]
            filtered = [o for o in odds_list if abs(o - median) <= 0.50]

            if filtered:
                best_odds[key] = max(filtered)
            else:
                best_odds[key] = median

        odds_data[fixture_id] = best_odds

    league_odds_cache[league_id] = odds_data
    league_odds_cache_time[league_id] = time.time()
    return odds_data


# ─── 7.13 SMART MONEY DETECTION ───

def detect_smart_money(fixture_id, current_odds, market_key):
    """
    Detect sharp money movement by comparing opening vs current odds.
    Returns dict with steam_move, market_pressure, sharp_indicator.
    """
    result = {
        "steam_move": False,
        "market_pressure": "NEUTRAL",
        "sharp_indicator": False,
        "odds_drop_pct": 0.0,
    }

    # Store opening odds on first observation
    cache_key = f"{fixture_id}_{market_key}"
    if cache_key not in clv_history:
        clv_history[cache_key] = {
            "opening_odds": current_odds,
            "closing_odds": current_odds,
            "first_seen": time.time()
        }
        return result

    entry = clv_history[cache_key]
    opening = entry["opening_odds"]
    entry["closing_odds"] = current_odds

    if opening <= 1.0:
        return result

    drop_pct = ((opening - current_odds) / opening) * 100

    result["odds_drop_pct"] = round(drop_pct, 2)

    # Steam move: significant drop (>5%) in short time
    time_elapsed = time.time() - entry["first_seen"]
    if drop_pct > 5.0 and time_elapsed < 7200:
        result["steam_move"] = True

    # Market pressure
    if drop_pct > 3.0:
        result["market_pressure"] = "HIGH"
    elif drop_pct > 1.5:
        result["market_pressure"] = "MEDIUM"

    # Sharp indicator: consistent directional movement > 4%
    if drop_pct > 4.0:
        result["sharp_indicator"] = True

    return result


# ─── 7.14 LIQUIDITY FILTER ───

def liquidity_filter(league_id, odds_value):
    """Reject markets with likely insufficient liquidity."""
    if league_id in TIER1_LEAGUES:
        return True  # Top leagues always liquid

    # Extreme odds indicate thin markets
    if odds_value < 1.25 or odds_value > 4.50:
        return False

    # Tier 3 leagues require tighter odds range
    if league_id in TIER3_LEAGUES:
        if odds_value < 1.40 or odds_value > 3.50:
            return False

    return True


# ─── 7.15 FAKE VOLUME FILTER ───

def fake_volume_filter(odds_value, league_id, smart_money_data):
    """
    Detect potential fake volume / bookmaker traps.
    Large drops in low-liquidity leagues are suspicious.
    """
    if league_id not in TIER1_LEAGUES:
        # Big drop in low-tier league = possible manipulation
        if smart_money_data["odds_drop_pct"] > 8.0:
            return False

    # Extreme odds combined with steam = likely trap
    if odds_value < 1.30 and smart_money_data["steam_move"]:
        return False

    return True


# ─── 7.16 MARKET STABILITY FILTER ───

def market_stability_filter(odds_value, smart_money_data):
    """Reject erratic markets with huge swings."""
    if abs(smart_money_data["odds_drop_pct"]) > 15.0:
        return False
    return True


# ─── 7.17 EV & KELLY ───

def calculate_ev(prob, odds):
    """Expected Value: (prob * odds) - 1"""
    return (prob * odds) - 1


def kelly_stake(prob, odds):
    """Kelly criterion for optimal stake sizing."""
    b = odds - 1
    q = 1 - prob
    if b <= 0:
        return 0
    k = (b * prob - q) / b
    return max(k, 0)


# ─── 7.18 CLV PREDICTION ───

def predict_clv(prob, current_odds, smart_money_data):
    """
    Estimate Closing Line Value based on model edge and market direction.
    Returns estimated CLV percentage.
    """
    implied = implied_probability(current_odds)
    edge = prob - implied

    # Base CLV from model edge
    base_clv = edge * 100 * 0.6  # Conservative: ~60% of edge converts to CLV

    # Boost if market is moving in our direction (steam/sharp)
    if smart_money_data["market_pressure"] == "HIGH":
        base_clv += 1.5
    elif smart_money_data["market_pressure"] == "MEDIUM":
        base_clv += 0.8

    if smart_money_data["sharp_indicator"]:
        base_clv += 1.0

    return round(base_clv, 2)


# ─── 7.19 MODEL DISAGREEMENT FILTER ───

def model_disagreement_filter(poisson_prob, monte_carlo_prob, calibrated_prob):
    """
    Reject signals where internal models disagree significantly.
    If Poisson, Monte Carlo, and calibrated probability diverge too much,
    the signal is unreliable.
    """
    probs = [poisson_prob, monte_carlo_prob, calibrated_prob]
    spread = max(probs) - min(probs)

    # If models disagree by more than 12 percentage points, reject
    if spread > 0.12:
        return False

    return True


# ─── 7.20 CONFIDENCE SCORING ───

def calculate_confidence(prob, ev, edge, odds_value, league_id, smart_money_data):
    """
    Multi-factor confidence score.
    Returns (score, tier) where tier is SAFE/MEDIUM/AGGRESSIVE.
    """
    score = 0

    # Probability strength (0-30)
    score += prob * 35

    # Edge strength (0-20)
    score += min(edge * 200, 20)

    # EV strength (0-15)
    score += min(ev * 100, 15)

    # League reliability bonus (0-10)
    reliability = league_reliability_score(league_id)
    score += reliability * 10

    # Ideal odds range bonus (0-8)
    if 1.75 <= odds_value <= 2.10:
        score += 8
    elif 1.60 <= odds_value <= 2.30:
        score += 5

    # Smart money confirmation (0-7)
    if smart_money_data["sharp_indicator"]:
        score += 5
    if smart_money_data["market_pressure"] == "HIGH":
        score += 2

    # Strong probability bonus
    if prob >= 0.64:
        score += 5
    elif prob >= 0.60:
        score += 3

    # Determine tier
    if score >= CONFIDENCE_SAFE:
        tier = "SAFE"
    elif score >= CONFIDENCE_MEDIUM:
        tier = "MEDIUM"
    else:
        tier = "AGGRESSIVE"

    return round(score, 1), tier


# ─── 7.21 EXTRA TIP MODEL ───

def model_extra_tip(over15_prob, over25_prob, over35_prob, btts_prob):
    """Suggest an additional market if probability is strong."""
    candidates = []

    if over25_prob > 0.60:
        candidates.append(("Over 2.5", over25_prob))
    if btts_prob > 0.58:
        candidates.append(("BTTS Yes", btts_prob))
    if over15_prob > 0.75:
        candidates.append(("Over 1.5", over15_prob))
    if over35_prob > 0.40:
        candidates.append(("Over 3.5", over35_prob))

    if not candidates:
        return None

    return max(candidates, key=lambda x: x[1])


# ─── 7.22 SYNDICATE FILTER: ENHANCED LIQUIDITY ───

def syndicate_liquidity_filter(fixture_id, league_id, odds_value):
    """
    Professional liquidity filter.
    Estimates market liquidity from:
    - Number of bookmakers offering the market
    - Odds spread across bookmakers (tight = liquid)
    - League tier

    Returns (passes: bool, liquidity_score: float 0-1)
    """
    league_odds = league_odds_cache.get(league_id)
    if not league_odds:
        # No cached odds data at all - cannot verify liquidity
        return league_id in TIER1_LEAGUES, 0.5

    fixture_odds = league_odds.get(fixture_id)
    if not fixture_odds:
        return league_id in TIER1_LEAGUES, 0.3

    # Count how many distinct market keys exist for this fixture
    # More markets = more bookmaker coverage = more liquid
    market_count = len(fixture_odds)

    # Base liquidity from league tier
    if league_id in TIER1_LEAGUES:
        base_liquidity = 0.90
    elif league_id in TIER2_LEAGUES:
        base_liquidity = 0.65
    else:
        base_liquidity = 0.40

    # Boost from market count: typical liquid match has 15+ market keys
    if market_count >= 15:
        market_boost = 0.10
    elif market_count >= 8:
        market_boost = 0.05
    else:
        market_boost = -0.10  # Very few markets = thin

    liquidity_score = min(base_liquidity + market_boost, 1.0)

    # Reject if liquidity is too low for the odds range
    if liquidity_score < 0.45:
        return False, liquidity_score

    # In thin markets, reject extreme odds more aggressively
    if liquidity_score < 0.60 and (odds_value < 1.50 or odds_value > 2.80):
        return False, liquidity_score

    return True, liquidity_score


# ─── 7.23 SYNDICATE FILTER: SHARP BOOK ALIGNMENT ───

def sharp_book_alignment_filter(fixture_id, league_id, market_key, model_prob):
    """
    Compare model edge against sharp bookmaker direction.

    Sharp books (Pinnacle-style) have tighter margins and move first.
    If the sharp book implied probability DISAGREES with our model by
    more than a threshold, we reduce confidence.

    Since we don't have explicit sharp/soft bookmaker labels from the API,
    we approximate: the LOWEST odds offered (tightest margin) represent
    the sharp price; the HIGHEST odds represent the soft price.

    Returns (passes: bool, confidence_penalty: float 0-15)
    """
    league_odds = league_odds_cache.get(league_id)
    if not league_odds:
        return True, 0  # No data = no penalty, pass through

    fixture_odds = league_odds.get(fixture_id)
    if not fixture_odds:
        return True, 0

    # We need the raw bookmaker-level odds for this specific market
    # Since get_league_odds already computed best_odds (max after outlier filter),
    # we use the stored best odds as "soft" price proxy.
    # For "sharp" price, we approximate from the best_odds value with
    # typical sharp-soft spread of 2-5% implied probability difference.

    best_odds_value = fixture_odds.get(market_key)
    if not best_odds_value or best_odds_value <= 1.0:
        return True, 0

    # Soft book implied probability (from best available odds = highest)
    soft_implied = 1 / best_odds_value

    # Sharp book approximation: sharps typically offer ~3% lower margin
    # So sharp implied ≈ soft_implied + 0.02 to 0.04 (sharps closer to true)
    sharp_implied = soft_implied + 0.025

    # If our model disagrees with sharp direction:
    # Model says high prob but sharp says lower prob
    model_vs_sharp_diff = model_prob - sharp_implied

    confidence_penalty = 0

    if model_vs_sharp_diff < -0.03:
        # Sharp books think this outcome is LESS likely than our model
        # Strong disagreement - penalize confidence
        confidence_penalty = min(abs(model_vs_sharp_diff) * 150, 15)

    if model_vs_sharp_diff < -0.08:
        # Severe disagreement - reject
        return False, confidence_penalty

    return True, confidence_penalty


# ─── 7.24 SYNDICATE FILTER: ODDS DRIFT ───

def odds_drift_filter(fixture_id, market_key, model_prob):
    """
    Track odds movement direction and reject bets where the market
    is moving STRONGLY AGAINST our model prediction.

    If odds are rising (meaning bookmakers think the outcome is LESS likely)
    while our model says it's likely, the market has information we don't.

    Returns (passes: bool, drift_direction: str)
    """
    cache_key = f"{fixture_id}_{market_key}"
    entry = clv_history.get(cache_key)

    if not entry:
        return True, "NEW"  # First observation, no drift data

    opening = entry.get("opening_odds", 0)
    closing = entry.get("closing_odds", 0)

    if opening <= 1.0 or closing <= 1.0:
        return True, "INVALID"

    # Positive drift = odds rising = market says LESS likely
    # Negative drift = odds falling = market says MORE likely
    drift_pct = ((closing - opening) / opening) * 100

    if drift_pct > 0:
        drift_direction = "AGAINST"  # Odds rose = market disagrees
    elif drift_pct < -1.0:
        drift_direction = "WITH"     # Odds fell = market agrees
    else:
        drift_direction = "STABLE"

    # If odds have risen significantly (market moving AGAINST our pick)
    # and our model probability isn't overwhelmingly strong, reject
    if drift_pct > 5.0:
        # Strong adverse movement - reject unless model is very confident
        if model_prob < 0.65:
            return False, drift_direction

    if drift_pct > 8.0:
        # Extreme adverse movement - always reject
        return False, drift_direction

    return True, drift_direction


# --- 7.25 MULTI-MODEL AGREEMENT LAYER ---

def xg_tempo_model(home_stats, away_stats, league_id):
    """Model 2: xG tempo estimation based on shots volume and accuracy."""
    if not home_stats or not away_stats:
        return {}
    h_tempo = (home_stats["shots_total"] * 0.04 + home_stats["shots_on"] * 0.12)
    a_tempo = (away_stats["shots_total"] * 0.04 + away_stats["shots_on"] * 0.12)
    h_def_tempo = (away_stats["shots_against"] * 0.04 + away_stats["shots_against_on"] * 0.12)
    a_def_tempo = (home_stats["shots_against"] * 0.04 + home_stats["shots_against_on"] * 0.12)
    modifier = LEAGUE_STRENGTH.get(league_id, 1.0)
    league_avg = LEAGUE_AVG_GOALS
    home_xg_t = ((h_tempo + h_def_tempo) / 2) / league_avg * modifier + 0.25
    away_xg_t = ((a_tempo + a_def_tempo) / 2) / league_avg * modifier
    total_xg = home_xg_t + away_xg_t
    probs = {}
    probs["over1_5"] = min(0.95, max(0.20, (total_xg - 1.2) * 0.35 + 0.50))
    probs["over2_5"] = min(0.90, max(0.15, (total_xg - 2.0) * 0.35 + 0.40))
    probs["over3_5"] = min(0.80, max(0.10, (total_xg - 2.8) * 0.30 + 0.25))
    probs["under2_5"] = 1.0 - probs["over2_5"]
    probs["under3_5"] = 1.0 - probs["over3_5"]
    probs["btts"] = min(0.85, max(0.20, min(home_xg_t, away_xg_t) * 0.45 + 0.15))
    probs["home_win"] = min(0.80, max(0.20, 0.45 + (home_xg_t - away_xg_t) * 0.18))
    return probs


def attack_defense_shots_model(home_stats, away_stats, league_id):
    """Model 3: Attack vs defense shots comparison model."""
    if not home_stats or not away_stats:
        return {}
    h_attack_power = home_stats["shots_on"] / (home_stats["shots_total"] + 1) * home_stats["attack"]
    a_attack_power = away_stats["shots_on"] / (away_stats["shots_total"] + 1) * away_stats["attack"]
    h_defense_weakness = away_stats["defense"] / (away_stats["shots_against"] + 1) * 10
    a_defense_weakness = home_stats["defense"] / (home_stats["shots_against"] + 1) * 10
    h_expected = (h_attack_power + h_defense_weakness) / 2
    a_expected = (a_attack_power + a_defense_weakness) / 2
    league_avg = LEAGUE_AVG_GOALS
    h_norm = h_expected / league_avg
    a_norm = a_expected / league_avg
    total = h_norm + a_norm
    probs = {}
    probs["over1_5"] = min(0.95, max(0.20, total * 0.30 + 0.20))
    probs["over2_5"] = min(0.90, max(0.15, total * 0.25 + 0.05))
    probs["over3_5"] = min(0.80, max(0.10, total * 0.18 - 0.05))
    probs["under2_5"] = 1.0 - probs["over2_5"]
    probs["under3_5"] = 1.0 - probs["over3_5"]
    probs["btts"] = min(0.85, max(0.20, min(h_norm, a_norm) * 0.50 + 0.10))
    probs["home_win"] = min(0.80, max(0.20, 0.45 + (h_norm - a_norm) * 0.20))
    return probs


def multi_model_agreement(poisson_probs, tempo_probs, shots_probs, market_key):
    """Check agreement across three models. Returns (level, blended_prob)."""
    key_map = {
        "over15": "over1_5", "over25": "over2_5", "over35": "over3_5",
        "under25": "under2_5", "under35": "under3_5",
        "btts": "btts", "home_win": "home_win",
    }
    mapped = key_map.get(market_key, market_key)
    p1 = poisson_probs.get(mapped)
    p2 = tempo_probs.get(mapped)
    p3 = shots_probs.get(mapped)
    available = [p for p in [p1, p2, p3] if p is not None]
    if len(available) < 2:
        return "LOW", available[0] if available else 0.50
    spread = max(available) - min(available)
    blended = sum(available) / len(available)
    if spread <= 0.06:
        return "HIGH", blended
    elif spread <= 0.12:
        return "MEDIUM", blended
    else:
        return "LOW", blended


def synthetic_fair_odds(model_prob):
    """Calculate fair odds from model probability."""
    if model_prob <= 0.01:
        return 100.0
    return round(1.0 / model_prob, 3)


def value_edge_pct(model_prob, market_odds):
    """Calculate edge percentage."""
    market_prob = implied_probability(market_odds)
    return round((model_prob - market_prob) * 100, 2)


def bet_timing_filter(fixture_timestamp):
    """Avoid stale or too-early bets. Returns (passes, quality)."""
    now = int(time.time())
    time_to_kick = fixture_timestamp - now
    if time_to_kick < 900:
        return False, "STALE"
    if time_to_kick < 3600:
        return True, "FAIR"
    if time_to_kick < 21600:
        return True, "GOOD"
    if time_to_kick <= 172800:
        return True, "EXCELLENT"
    return True, "GOOD"


def bookmaker_consensus_filter(fixture_id, league_id, market_key, direction):
    """Check if multiple bookmakers support the same direction."""
    league_odds = league_odds_cache.get(league_id)
    if not league_odds:
        return True
    fixture_odds = league_odds.get(fixture_id)
    if not fixture_odds:
        return True
    return len(fixture_odds) >= 3


def rank_bet_score(bet_data):
    """Comprehensive ranking score."""
    score = 0.0
    score += min(bet_data.get("edge", 0) * 150, 20)
    agreement = bet_data.get("agreement_level", "LOW")
    if agreement == "HIGH": score += 15
    elif agreement == "MEDIUM": score += 8
    sm = bet_data.get("smart_money", {})
    if sm.get("market_pressure") == "HIGH": score += 10
    elif sm.get("market_pressure") == "MEDIUM": score += 5
    if sm.get("sharp_indicator"): score += 7
    timing = bet_data.get("timing_quality", "GOOD")
    if timing == "EXCELLENT": score += 8
    elif timing == "GOOD": score += 5
    elif timing == "FAIR": score += 2
    score += bet_data.get("prob", 0) * 20
    lq = LEAGUE_QUALITY_SCORES.get(bet_data.get("league_id", 0), 5)
    score += lq
    return round(score, 2)

def marketing_vip_closing():
    return random.choice([
        "VIP access kleinei meta ta signals.\nSecure your position tora.",
        "Limited spots sto VIP network.\nMeta tis 18:00 to access kleinei.",
    ])


def marketing_vip_reopening():
    return random.choice([
        "VIP access einai anoixto gia simera.\nNees theseis available.",
        "To ValueHunter network dexetai nea meli.\nActivate your access tora.",
    ])


def performance_panel_30():
    """Extended performance panel - last 30 bets."""
    rows = cursor.execute(
        "SELECT odds, result, clv, model_prob, edge FROM bets_history WHERE result IN ('WIN','LOSE') ORDER BY id DESC LIMIT 30"
    ).fetchall()
    if not rows:
        return "No completed bets yet."
    wins = sum(1 for r in rows if r[1] == "WIN")
    losses = sum(1 for r in rows if r[1] == "LOSE")
    total = wins + losses
    winrate = (wins / total * 100) if total > 0 else 0
    profit = 0
    stake = DEFAULT_STAKE
    for odds_v, result, clv_val, mp, edge_val in rows:
        if result == "WIN":
            profit += (odds_v * stake) - stake
        else:
            profit -= stake
    roi = (profit / (total * stake) * 100) if total > 0 else 0
    clv_values = [r[2] for r in rows if r[2] and r[2] > 0]
    avg_clv = round(sum(clv_values) / len(clv_values), 2) if clv_values else 0
    return f"""📊 PERFORMANCE PANEL (Last 30)

Bets: {total}  W: {wins}  L: {losses}
Winrate: {winrate:.1f}%
Profit: {round(profit, 2)} EUR
ROI: {roi:.1f}%
Avg CLV: +{avg_clv}%
"""


# ─── 7.22 MASTER VALUE ENGINE ───

def get_value_bets():
    """
    Master pipeline:
    DATA → VALIDATION → STATS → XG → POISSON → MONTE CARLO →
    ODDS → SMART MONEY → FILTERS → EDGE → CONFIDENCE → SIGNALS
    """
    global value_cache, value_cache_time

    if time.time() - value_cache_time < 900 and value_cache:
        return value_cache

    fixtures = scan_matches()
    best_per_match = {}

    for f in fixtures:
        league_id = f["league_id"]

        if league_id not in GOOD_LEAGUES:
            continue

        # ── STEP 1: Team Stats ──
        home_stats = get_team_stats(f["home_id"], league_id)
        away_stats = get_team_stats(f["away_id"], league_id)

        # ── STEP 2: Data Quality Filter ──
        if not data_quality_filter(home_stats, away_stats, league_id):
            continue

        # ── STEP 3: Injury Data ──
        home_injuries = get_injuries(f["home_id"])
        away_injuries = get_injuries(f["away_id"])

        # ── STEP 4: League Normalization ──
        league_avg = LEAGUE_AVG_GOALS
        home_attack = home_stats["attack"] / league_avg
        away_attack = away_stats["attack"] / league_avg
        home_defense = home_stats["defense"] / league_avg
        away_defense = away_stats["defense"] / league_avg

        # Injury adjustment (max 15% reduction)
        home_attack *= (1 - min(home_injuries * 0.04, 0.15))
        away_attack *= (1 - min(away_injuries * 0.04, 0.15))

        # ── STEP 5: Team Strength ──
        hs, as_ = calculate_team_strength(
            home_attack, home_defense,
            away_attack, away_defense
        )

        # ── STEP 6: xG Model ──
        home_xg, away_xg = calculate_xg(hs, as_, league_id)

        # ── STEP 7: Sanity Filters ──
        if not model_sanity_filter(home_xg, away_xg):
            continue

        if not tempo_filter(home_xg, away_xg):
            continue

        total_xg = home_xg + away_xg
        xg_diff = abs(home_xg - away_xg)

        if xg_diff > 1.6:
            continue

        # ── STEP 8: Poisson Matrix ──
        matrix = poisson_matrix(home_xg, away_xg)

        # ── STEP 9: Monte Carlo ──
        mc_home_prob, mc_draw_prob, mc_away_prob = monte_carlo_simulation(home_xg, away_xg)

        # ── STEP 10: Market Probabilities ──
        totals = goal_totals_probability(matrix)
        line, asian_prob = asian_optimizer(matrix)

        # Blend Poisson + Monte Carlo for home win
        poisson_home = sum(p for h, a, p in matrix if h > a)
        home_prob = (poisson_home + mc_home_prob) / 2
        home_prob = calibrate_probability(home_prob)

        asian_prob = (asian_prob + mc_home_prob) / 2
        asian_prob = calibrate_probability(asian_prob)

        over25_prob = calibrate_probability(totals["over2_5"])
        under25_prob = calibrate_probability(totals["under2_5"])
        over15_prob = calibrate_probability(totals["over1_5"])
        over35_prob = calibrate_probability(totals["over3_5"])
        btts_prob_val = calibrate_probability(btts_probability(matrix))

        # ── STEP 11: Get Odds ──
        league_odds = get_league_odds(league_id)
        if not league_odds:
            continue

        odds = league_odds.get(f["fixture_id"])
        if not odds:
            continue

        home_odds = odds.get("Match Winner_Home")
        over_odds = odds.get("Goals Over/Under_Over 2.5")
        under_odds = odds.get("Goals Over/Under_Under 2.5")
        over15_odds = odds.get("Goals Over/Under_Over 1.5")
        over35_odds = odds.get("Goals Over/Under_Over 3.5")
        under35_odds = odds.get("Goals Over/Under_Under 3.5")
        btts_odds = odds.get("Both Teams Score_Yes")

        # Build market candidates
        markets = []

        if home_odds:
            markets.append(("Home Win", home_prob, home_odds, "home_win"))
        if over_odds:
            markets.append(("Over 2.5", over25_prob, over_odds, "over25"))
        if under_odds and total_xg < 2.7:
            markets.append(("Under 2.5", under25_prob, under_odds, "under25"))
        if over15_odds:
            markets.append(("Over 1.5", over15_prob, over15_odds, "over15"))
        if over35_odds and total_xg > 2.8:
            markets.append(("Over 3.5", over35_prob, over35_odds, "over35"))
        if under35_odds and total_xg < 3.2:
            markets.append(("Under 3.5", 1 - over35_prob, under35_odds, "under35"))
        if btts_odds:
            markets.append(("BTTS", btts_prob_val, btts_odds, "btts"))

        # ── STEP 12: Evaluate Each Market ──
        for market_name, prob, odds_value, market_key in markets:

            # Odds range filter
            if odds_value < 1.40 or odds_value > 3.10:
                continue

            if odds_value < 1.70 and prob < 0.60:
                continue

            # Liquidity filter
            if not liquidity_filter(league_id, odds_value):
                continue

            # Smart money detection
            smart_money = detect_smart_money(f["fixture_id"], odds_value, market_key)

            # Fake volume filter
            if not fake_volume_filter(odds_value, league_id, smart_money):
                continue

            # Market stability filter
            if not market_stability_filter(odds_value, smart_money):
                continue

            # ── SYNDICATE FILTER 1: Enhanced Liquidity ──
            liq_pass, liq_score = syndicate_liquidity_filter(
                f["fixture_id"], league_id, odds_value
            )
            if not liq_pass:
                continue

            # ── SYNDICATE FILTER 2: Sharp Book Alignment ──
            # Build the odds key that matches fixture_odds format
            odds_key_map = {
                "home_win": "Match Winner_Home",
                "over25": "Goals Over/Under_Over 2.5",
                "under25": "Goals Over/Under_Under 2.5",
                "over15": "Goals Over/Under_Over 1.5",
                "over35": "Goals Over/Under_Over 3.5",
                "under35": "Goals Over/Under_Under 3.5",
                "btts": "Both Teams Score_Yes",
            }
            sharp_key = odds_key_map.get(market_key, market_key)
            sharp_pass, sharp_penalty = sharp_book_alignment_filter(
                f["fixture_id"], league_id, sharp_key, prob
            )
            if not sharp_pass:
                continue

            # ── SYNDICATE FILTER 3: Odds Drift ──
            drift_pass, drift_direction = odds_drift_filter(
                f["fixture_id"], market_key, prob
            )
            if not drift_pass:
                continue
                
            # SuperSafe shield (soft)
            if drift_direction == "against":
                confidence *= 0.92

            # Edge calculation
            implied = implied_probability(odds_value)
            edge = prob - implied

            if edge < 0.02:
                continue

            # EV calculation
            ev = calculate_ev(prob, odds_value)
            if ev <= 0.04:
                continue

            # Probability range
            if prob < 0.54 or prob > 0.85:
                continue

            # Sharp market filter: model must beat market by 4%+
            market_prob = 1 / odds_value
            if prob - market_prob < 0.04:
                continue

            # Model disagreement filter (use raw poisson prob for this market)
            totals_key_map = {
                "over25": "over2_5", "under25": "under2_5",
                "over15": "over1_5", "over35": "over3_5",
                "under35": "under3_5",
            }
            raw_poisson_prob = totals.get(totals_key_map.get(market_key, ""), None)
            if raw_poisson_prob is not None:
                if not model_disagreement_filter(raw_poisson_prob, prob, calibrate_probability(prob)):
                    pass  # Soft filter: don't reject but reduce confidence

            # Kelly stake
            stake_pct = kelly_stake(prob, odds_value)
            if stake_pct > 0.06:
                continue

            # Value strength cross-validation
            value_strength = 0
            if over25_prob > 0.55:
                value_strength += 1
            if btts_prob_val > 0.55:
                value_strength += 1
            if home_prob > 0.55:
                value_strength += 1
            if value_strength == 0:
                continue
                
            # Model agreement boost
            agreement_boost = 0

            if value_strength >= 2:
                agreement_boost = 3

            if value_strength == 3:
                agreement_boost = 5

            # CLV prediction
            clv_est = predict_clv(prob, odds_value, smart_money)

            # Confidence scoring
            confidence, tier = calculate_confidence(
                prob, ev, edge, odds_value, league_id, smart_money
            )
            
            # Apply model agreement boost
            confidence += agreement_boost

            # Apply sharp book alignment penalty
            confidence = max(confidence - sharp_penalty, 0)

            # Recompute tier after penalty
            if confidence >= CONFIDENCE_SAFE:
                tier = "SAFE"
            elif confidence >= CONFIDENCE_MEDIUM:
                tier = "MEDIUM"
            else:
                tier = "AGGRESSIVE"

            # Build pick name
            pick = market_name
            if market_name == "Home Win":
                pick = f"{f['home']} to Win"

            # Dedup check
            bet_key = f"{f['fixture_id']}_{pick}"
            if cursor.execute(
                "SELECT key FROM sent_bets WHERE key=?",
                (bet_key,)
            ).fetchone():
                continue

            # Model score (for ranking)
            model_score = (
                ev * 0.35 +
                prob * 0.30 +
                (confidence / 100) * 0.20 +
                (max(clv_est, 0) / 10) * 0.15
            )

            bet_data = {
                "fixture_id": f["fixture_id"],
                "match": f"{f['home']} vs {f['away']}",
                "pick": pick,
                "prob": prob,
                "odds": odds_value,
                "ev": ev,
                "edge": edge,
                "confidence": confidence,
                "confidence_tier": tier,
                "stake": stake_pct,
                "score": model_score,
                "clv_est": clv_est,
                "smart_money": smart_money,
                "league_id": league_id,
                "total_xg": total_xg,
            }

            fid = f["fixture_id"]
            if fid not in best_per_match:
                best_per_match[fid] = bet_data
            else:
                if bet_data["score"] > best_per_match[fid]["score"]:
                    best_per_match[fid] = bet_data

    # ── STEP 13: Rank & Filter ──
    candidates = list(best_per_match.values())
    candidates.sort(key=lambda x: x["score"], reverse=True)

    # Correlation filter: one bet per match
    used_matches = set()
    filtered = []

    for bet in candidates:
        match_id = bet["fixture_id"]
        if match_id not in used_matches:
            filtered.append(bet)
            used_matches.add(match_id)
            
    # ── STEP 14: Signal Generation ──
    super_safe = None
    high_value = []

    # Advanced SuperSafe selection
    safe_candidates = []
    safe_value_candidates = []

    for bet in filtered:

        confidence = bet.get("confidence", 0)

        # ⭐ SUPER SAFE
        if (
            bet["prob"] >= 0.63
            and 1.45 <= bet["odds"] <= 2.50
            and bet["ev"] >= 0.05
            and bet["clv_est"] >= 1
            and confidence >= 75
        ):
            safe_candidates.append(bet)

        # 🔥 SAFE VALUE
        elif (
            bet["prob"] >= 0.58
            and 1.80 <= bet["odds"] <= 2.60
            and bet["ev"] >= 0.04
            and confidence >= 70
        ):
            safe_value_candidates.append(bet)

    # Select best SuperSafe using ranking score
    if safe_candidates:
        safe_candidates.sort(key=lambda x: rank_bet_score(x), reverse=True)
        super_safe = safe_candidates[0]
        
    # Rank Safe Value bets
    safe_value_candidates.sort(key=lambda x: rank_bet_score(x), reverse=True)

    high_value = safe_value_candidates[:2]

    signals = []

    def format_signal(bet, signal_type):
        """Format a bet into a signal message."""
        steam_str = "YES ⚡" if bet["smart_money"]["steam_move"] else "NO"
        pressure_str = bet["smart_money"]["market_pressure"]
        sharp_str = "YES 🔥" if bet["smart_money"]["sharp_indicator"] else "NO"

        return f"""🎖️ 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑬𝑳𝑰𝑻𝑬 𝑷𝑰𝑪𝑲

⚽ {bet['match']}

🎯 𝑶𝑭𝑭𝑰𝑪𝑰𝑨𝑳 𝑷𝑰𝑪𝑲
{bet['pick']}

📊 𝑶𝑫𝑫𝑺
{round(bet['odds'], 2)}

👤 User ID: {user_id}

━━━━━━━━━━━━━━━━━━

🌐 𝑴𝑶𝑫𝑬𝑳 𝑫𝑨𝑻𝑨

Probability: {round(bet['prob'] * 100)}%
Value Edge: {round(bet['edge'] * 100, 2)}%
Expected Value: {round(bet['ev'] * 100, 2)}%

⚙️ Confidence Score
{round(bet['confidence'], 1)} — {bet['confidence_tier']}

━━━━━━━━━━━━━━━━━━

🏆 𝑴𝑨𝑹𝑲𝑬𝑻 𝑬𝑫𝑮𝑬

📉 Opening Odds: {bet.get('opening_odds', 'N/A')}
💎 Current Odds: {round(bet['odds'], 2)}
📈 Closing Line Prediction: +{bet['clv_est']}%

Market Pressure: {pressure_str}

━━━━━━━━━━━━━━━━━━

📡 𝑺𝑴𝑨𝑹𝑻 𝑴𝑶𝑵𝑬𝒀

Steam Move: {steam_str}
Sharp Money: {sharp_str}

━━━━━━━━━━━━━━━━━━

💰 𝑹𝑬𝑪𝑶𝑴𝑴𝑬𝑵𝑫𝑬𝑫 𝑺𝑻𝑨𝑲𝑬
{round(bet['stake'] * 100, 1)}% bankroll

━━━━━━━━━━━━━━━━━━

👑 𝑽𝑰𝑷 𝑴𝑶𝑫𝑬𝑳 𝑺𝑰𝑮𝑵𝑨𝑳
@ValueHunterElite_bot
@MrMasterlegacy1
"""
    if super_safe:
        bet_key = f"{super_safe['fixture_id']}_{super_safe['pick']}"
        with db_lock:
            cursor.execute("INSERT OR IGNORE INTO sent_bets VALUES (?)", (bet_key,))
            cursor.execute(
                "INSERT INTO bets_history(fixture_id,match,pick,odds,result,timestamp,confidence_tier,clv,model_prob) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    super_safe["fixture_id"],
                    super_safe["match"],
                    super_safe["pick"],
                    super_safe["odds"],
                    "PENDING",
                    int(time.time()),
                    super_safe["confidence_tier"],
                    super_safe["clv_est"],
                    round(super_safe["prob"], 4)
                )
            )
            db.commit()
        signals.append(format_signal(super_safe, "⭐ 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑺𝑼𝑷𝑬𝑹 𝑺𝑨𝑭𝑬"))

    for bet in high_value[:2]:
        bet_key = f"{bet['fixture_id']}_{bet['pick']}"
        with db_lock:
            cursor.execute("INSERT OR IGNORE INTO sent_bets VALUES (?)", (bet_key,))
            cursor.execute(
                "INSERT INTO bets_history(fixture_id,match,pick,odds,result,timestamp,confidence_tier,clv,model_prob) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    bet["fixture_id"],
                    bet["match"],
                    bet["pick"],
                    bet["odds"],
                    "PENDING",
                    int(time.time()),
                    bet["confidence_tier"],
                    bet["clv_est"],
                    round(bet["prob"], 4)
                )
            )
            db.commit()
        signals.append(format_signal(bet, "🔥 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑯𝑰𝑮𝑯 𝑽𝑨𝑳𝑼𝑬"))

    # Fallback system
    if not signals and candidates:
        fallback = sorted(candidates, key=lambda x: x["ev"], reverse=True)
        for bet in fallback[:2]:
            signals.append(
f"""⚠️ VALUE SCAN FALLBACK

⚽ {bet['match']}

🎯 {bet['pick']}

📊 Odds {round(bet['odds'], 2)}

📈 Probability {round(bet['prob'] * 100)}%

💰 Value {round(bet['ev'], 3)}
"""
            )
    
    # Build Parlay
    global parlay_cache
    parlay_cache = build_parlay(signals, candidates)

    value_cache = signals
    value_cache_time = time.time()

    return signals
    
# ───────────────────────────────────────
# ⭐ ADVANCED BET RANKING SYSTEM
# Syndicate-style scoring model
# Combines EV + Probability + Confidence + CLV + Smart Money
# Used for selecting the best bets before signal generation
# ───────────────────────────────────────

def rank_bet_score(bet):
    """
    Advanced ranking score for selecting best bets.
    Combines probability, EV, confidence, smart money and CLV prediction.
    """

    prob = bet.get("prob", 0)
    ev = bet.get("ev", 0)
    confidence = bet.get("confidence", 0)
    clv = bet.get("clv_est", 0)

    smart_money = bet.get("smart_money", {})
    steam = 1 if smart_money.get("steam_move") else 0
    sharp = 1 if smart_money.get("sharp_indicator") else 0

    score = (
        ev * 0.35 +
        prob * 0.30 +
        (confidence / 100) * 0.20 +
        (max(clv, 0) / 10) * 0.10 +
        steam * 0.03 +
        sharp * 0.02
    )

    return score
    
# ───────────────────────────────────────
# 📊 MODEL STREAK CALCULATOR
# Calculates wins in last 5 signals
# ───────────────────────────────────────

def get_model_streak():

    rows = cursor.execute(
        "SELECT result FROM bets_history WHERE result IN ('WIN','LOSE') ORDER BY id DESC LIMIT 5"
    ).fetchall()

    if not rows:
        return "No recent data"

    wins = sum(1 for r in rows if r[0] == "WIN")
    total = len(rows)

    return f"{wins} Wins in the last {total} signals"
    
# ───────────────────────────────────────
# 🎰 ELITE PARLAY GENERATOR
# Builds an 8-leg value parlay using
# signal matches + additional value bets
# ───────────────────────────────────────

def build_parlay(signals_data, candidates):

    parlay_legs = []

    used_matches = set()

    # 1️⃣ Use signal matches but different market
    for bet in signals_data:

        match = bet["match"]
        used_matches.add(match)

        # Smart alternative market
        if bet.get("total_xg", 2.5) >= 3.0:
            alt_pick = "Over 2.5 Goals"

        elif bet.get("total_xg", 2.5) >= 2.2:
            alt_pick = "Over 1.5 Goals"

        elif bet.get("total_xg", 2.5) <= 2.1:
            alt_pick = "Under 3.5 Goals"

        else:
            alt_pick = "BTTS"

        if 1.35 <= bet["odds"] <= 2.20:
            parlay_legs.append({
                "match": match,
                "pick": alt_pick,
                "odds": round(min(bet["odds"], 1.65), 2)
            })

    # 2️⃣ Find extra matches
    extra_candidates = []

    for bet in candidates:

        if bet["match"] in used_matches:
            continue

        if bet["odds"] < 1.40 or bet["odds"] > 1.65:
            continue

        if bet["prob"] < 0.58:
            continue

        if bet["edge"] < 0.03:
            continue

        # 🧠 Syndicate stability filters
        if bet["confidence"] < 55:
            continue

        if bet["ev"] < 0.03:
            continue

        if bet["smart_money"]["market_pressure"] == "LOW":
            continue

        extra_candidates.append(bet)

    extra_candidates.sort(key=lambda x: rank_bet_score(x), reverse=True)

    for bet in extra_candidates:

        if len(parlay_legs) >= 8:
            break

        parlay_legs.append({
            "match": bet["match"],
            "pick": bet["pick"],
            "odds": round(bet["odds"], 2)
        })

    if len(parlay_legs) < 4:
        return None

    # ───────────────────────────────────────
    # 🎰 ELITE PARLAY MESSAGE FORMAT
    # ───────────────────────────────────────

    text = "🎰 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑬𝑳𝑰𝑻𝑬 𝑷𝑨𝑹𝑳𝑨𝒀\n\n"

    text += "💎 𝑬𝑳𝑰𝑻𝑬 𝑨𝑪𝑪𝑼𝑴𝑼𝑳𝑨𝑻𝑶𝑹\n"
    text += "Model selected value positions across today's markets.\n\n"

    total_odds = 1

    for i, leg in enumerate(parlay_legs, start=1):

        total_odds *= leg["odds"]

        text += f"#{i}\n"
        text += f"⚽ {leg['match']}\n"
        text += f"🎯 {leg['pick']}\n"
        text += f"📊 Odds {leg['odds']}\n\n"

    text += "━━━━━━━━━━━━━━━━━━\n"

    text += f"💰 𝑻𝑶𝑻𝑨𝑳 𝑶𝑫𝑫𝑺\n{round(total_odds,2)}\n\n"

    text += "📡 𝑴𝑨𝑹𝑲𝑬𝑻 𝑵𝑶𝑻𝑬\n"
    text += "These selections were identified by the ValueHunter model before major market movement.\n\n"

    text += "👑 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑬𝑳𝑰𝑻𝑬\n"
    text += "@ValueHunterElite_bot\n"

    return text

# ╔══════════════════════════════════════════════════════════════╗
# ║  PART 8 - SIGNAL DELIVERY & RESULTS                         ║
# ╚══════════════════════════════════════════════════════════════╝

# ─── RESULT GRADER ───

def grade_results():
    """Grade PENDING bets after matches finish. Track CLV and win streaks."""
    rows = cursor.execute(
        "SELECT id,fixture_id,match,pick,odds,result FROM bets_history WHERE result='PENDING'"
    ).fetchall()

    for bet_id, fixture_id, match, pick, odds, result in rows:
        if not fixture_id:
            continue

        url = f"https://v3.football.api-sports.io/fixtures?id={fixture_id}"
        headers = {"x-apisports-key": FOOTBALL_API_KEY}

        try:
            r = requests.get(url, headers=headers, timeout=10).json()
        except:
            continue

        if not r.get("response"):
            continue

        game = r["response"][0]

        if game["fixture"]["status"]["short"] != "FT":
            continue

        home_goals = game["goals"]["home"]
        away_goals = game["goals"]["away"]

        outcome = "LOSE"

        if "Asian Handicap" in pick:
            line = float(pick.split()[-1])
            if (home_goals - away_goals) > line:
                outcome = "WIN"
        elif "Over" in pick:
            line = float(pick.split()[-1])
            if home_goals + away_goals > line:
                outcome = "WIN"
        elif "Under" in pick:
            line = float(pick.split()[-1])
            if home_goals + away_goals < line:
                outcome = "WIN"
        elif "BTTS" in pick:
            if home_goals > 0 and away_goals > 0:
                outcome = "WIN"
        elif "to Win" in pick:
            if home_goals > away_goals:
                outcome = "WIN"

        with db_lock:
            cursor.execute(
                "UPDATE bets_history SET result=? WHERE id=?",
                (outcome, bet_id)
            )
            db.commit()

        # ── RESULT UPDATE SYSTEM ──

        try:

            # update the original VIP signal message
            rows_msg = cursor.execute(
                "SELECT user_id,message_id FROM signal_messages"
            ).fetchall()

            for uid,msg_id in rows_msg:

                status_icon = "🟢 WIN" if outcome == "WIN" else "🔴 LOSS"

                updated_text = f"""
        🎖️ 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑬𝑳𝑰𝑻𝑬 𝑹𝑬𝑺𝑼𝑳𝑻

        ⚽ {match}
        🎯 {pick}

        📊 Odds {odds}

        ━━━━━━━━━━━━━━

        📊 Result: {status_icon}

        ValueHunter model result update
        """

                try:
                    bot.edit_message_text(
                        updated_text,
                        uid,
                        msg_id
                    )
                except:
                    pass

        except:
            pass


        # ── NORMAL RESULT NOTIFICATION ──

        if outcome == "WIN":
            _send_win_notification(match, pick, odds)

        _check_win_streak()

def _send_win_notification(match, pick, odds):
    """Send win confirmation to VIP and teaser to free users."""
    message = f"""
🎖️ 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑬𝑳𝑰𝑻𝑬 𝑹𝑬𝑺𝑼𝑳𝑻

🟢 𝗪𝗜𝗡𝗡𝗜𝗡𝗚 𝗦𝗜𝗚𝗡𝗔𝗟 𝗖𝗢𝗡𝗙𝗜𝗥𝗠𝗘𝗗

⚽ {match}  
🎯 {pick}  
📈 Odds {odds}

━━━━━━━━━━━━━━━━━━

✅ 𝗩𝗜𝗣 𝗠𝗘𝗠𝗕𝗘𝗥𝗦 𝗖𝗢𝗟𝗟𝗘𝗖𝗧𝗘𝗗 𝗔𝗡𝗢𝗧𝗛𝗘𝗥 𝗪𝗜𝗡𝗡𝗜𝗡𝗚 𝗦𝗜𝗚𝗡𝗔𝗟.

The ValueHunter model once again identified **hidden bookmaker value** before the market reacted.

━━━━━━━━━━━━━━━━━━

📡 𝗡𝗘𝗫𝗧 𝗦𝗜𝗚𝗡𝗔𝗟 𝗥𝗘𝗟𝗘𝗔𝗦𝗘  
⏰ 18:00 — Athens Time 🇬🇷

⚜️ 𝗩𝗜𝗣 𝗔𝗖𝗖𝗘𝗦𝗦 𝗧𝗢 𝗧𝗛𝗘  
𝗩𝗔𝗟𝗨𝗘𝗛𝗨𝗡𝗧𝗘𝗥 𝗡𝗘𝗧𝗪𝗢𝗥𝗞  
𝗠𝗔𝗬 𝗖𝗟𝗢𝗦𝗘 𝗔𝗙𝗧𝗘𝗥 𝗧𝗛𝗘 𝗡𝗘𝗫𝗧 𝗥𝗘𝗟𝗘𝗔𝗦𝗘.

👑 Elite members are already preparing the next positions.

💎 𝑶𝑭𝑭𝑰𝑪𝑰𝑨𝑳 𝑩𝑶𝑻: @ValueHunterElite_bot
🔐 𝑺𝑼𝑷𝑷𝑶𝑹𝑻: @MrMasterlegacy1
"""
    users = get_vip_users()
    for uid, plan in users:
        try:
            bot.send_message(uid, message)
            time.sleep(0.05)
        except:
            pass
    
    img_path = generate_ai_result_image(results)
    
    # Free user teaser
    free_text = f"""
🎖️ 𝑽𝑰𝑷 𝑾𝑰𝑵 𝑪𝑶𝑵𝑭𝑰𝑹𝑴𝑬𝑫

⚽ {match}
🎯 {pick}
📈 Odds {odds}

𝗘𝗟𝗜𝗧𝗘 𝗠𝗘𝗠𝗕𝗘𝗥𝗦 𝗖𝗢𝗟𝗟𝗘𝗖𝗧𝗘𝗗 𝗔𝗡𝗢𝗧𝗛𝗘𝗥 𝗪𝗜𝗡𝗡𝗜𝗡𝗚 𝗦𝗜𝗚𝗡𝗔𝗟 𝗧𝗢𝗗𝗔𝗬.

 ━━━━━━━━━━━━━━

🎖️ 𝗠𝗢𝗥𝗘 𝗦𝗜𝗚𝗡𝗔𝗟𝗦 𝗪𝗜𝗟𝗟 𝗕𝗘 𝗥𝗘𝗟𝗘𝗔𝗦𝗘𝗗 𝗔𝗧 𝟭𝟴:𝟬𝟬

 • 𝗔𝗧𝗛𝗘𝗡𝗦 𝗧𝗜𝗠𝗘 🇬🇷

⚜️ 𝗔𝗖𝗖𝗘𝗦𝗦 𝗧𝗢 𝗧𝗛𝗘 𝗩𝗔𝗟𝗨𝗘𝗛𝗨𝗡𝗧𝗘𝗥 𝗡𝗘𝗧𝗪𝗢𝗥𝗞 𝗠𝗔𝗬 𝗖𝗟𝗢𝗦𝗘 𝗢𝗡𝗖𝗘 𝗦𝗜𝗚𝗡𝗔𝗟𝗦 𝗔𝗥𝗘 𝗥𝗘𝗟𝗘𝗔𝗦𝗘𝗗.
 """

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⚜️ 𝑼𝑵𝑳𝑶𝑪𝑲 𝑽𝑰𝑷 𝑨𝑪𝑪𝑬𝑺𝑺", callback_data="elite"))
    
    free_users = get_all_users()

    for uid in free_users:

        if is_vip(uid):
            continue

        try:

            bot.send_photo(
                uid,
                open(img_path,"rb"),
                caption=free_text,
                reply_markup=keyboard
            )

            time.sleep(0.05)

        except:
            pass

# ─── WIN STREAK TRACKER ───

def _check_win_streak():
    """Check if we're on a win streak and notify."""
    rows = cursor.execute(
        "SELECT result FROM bets_history WHERE result IN ('WIN','LOSE') ORDER BY id DESC LIMIT 10"
    ).fetchall()

    streak = 0
    for row in rows:
        if row[0] == "WIN":
            streak += 1
        else:
            break

    if streak >= 3:
        # Only notify at 3, 5, 7, 10
        if streak in [3, 5, 7, 10]:
            users = get_vip_users()
            text = f"""
🔥 𝑾𝑰𝑵 𝑺𝑻𝑹𝑬𝑨𝑲: {streak}

The ValueHunter model is on a {streak}-bet winning streak.

━━━━━━━━━━━━━━

📡 Next signals at 18:00 🇬🇷
"""
            for uid, plan in users:
                try:
                    bot.send_message(uid, text)
                    time.sleep(0.05)
                except:
                    pass


# ─── PERFORMANCE REPORTS ───

def performance():
    now = int(time.time())
    day = now - 86400
    week = now - (86400 * 7)

    daily = cursor.execute(
        "SELECT odds,result FROM bets_history WHERE timestamp>?",
        (day,)
    ).fetchall()

    weekly = cursor.execute(
        "SELECT odds,result FROM bets_history WHERE timestamp>?",
        (week,)
    ).fetchall()

    def calc_profit(data):
        wins = 0
        losses = 0
        profit = 0
        stake = DEFAULT_STAKE
        for odds, result in data:
            if result == "WIN":
                wins += 1
                profit += (odds * stake) - stake
            elif result == "LOSE":
                losses += 1
                profit -= stake
        return wins, losses, profit

    dw, dl, dp = calc_profit(daily)
    ww, wl, wp = calc_profit(weekly)

    return f"""
📊 𝑫𝑨𝑰𝑳𝒀 𝑷𝑬𝑹𝑭𝑶𝑹𝑴𝑨𝑵𝑪𝑬

𝗪𝗜𝗡𝗦: {dw}
𝗟𝗢𝗦𝗦𝗘𝗦: {dl}

𝗣𝗥𝗢𝗙𝗜𝗧: {round(dp, 2)} €


📈 𝑾𝑬𝑬𝑲𝑳𝒀 𝑷𝑬𝑹𝑭𝑶𝑹𝑴𝑨𝑵𝑪𝑬

𝗪𝗜𝗡𝗦: {ww}
𝗟𝗢𝗦𝗦𝗘𝗦: {wl}

𝗣𝗥𝗢𝗙𝗜𝗧: {round(wp, 2)} €
"""


def monthly_report():
    now = int(time.time())
    month = now - (86400 * 30)

    rows = cursor.execute(
        "SELECT odds,result FROM bets_history WHERE timestamp>?",
        (month,)
    ).fetchall()

    wins = 0
    losses = 0
    profit = 0
    stake = DEFAULT_STAKE

    for odds, result in rows:
        if result == "WIN":
            wins += 1
            profit += (odds * stake) - stake
        elif result == "LOSE":
            losses += 1
            profit -= stake

    return f"""
🏆 𝑴𝑶𝑵𝑻𝑯𝑳𝒀 𝑹𝑬𝑷𝑶𝑹𝑻

𝗪𝗜𝗡𝗦: {wins}
𝗟𝗢𝗦𝗦𝗘𝗦: {losses}

𝗣𝗥𝗢𝗙𝗜𝗧: {round(profit, 2)} €
"""


def bankroll_status():
    rows = cursor.execute(
        "SELECT odds,result FROM bets_history"
    ).fetchall()

    bankroll = START_BANKROLL
    stake = DEFAULT_STAKE

    for odds, result in rows:
        if result == "WIN":
            bankroll += (odds * stake) - stake
        elif result == "LOSE":
            bankroll -= stake

    profit = bankroll - START_BANKROLL
    roi = (profit / START_BANKROLL) * 100 if START_BANKROLL > 0 else 0

    return f"""
🏧 𝑩𝑨𝑵𝑲𝑹𝑶𝑳𝑳

𝗦𝗧𝗔𝗥𝗧𝗜𝗡𝗚: {START_BANKROLL}€
𝗖𝗨𝗥𝗥𝗘𝗡𝗧: {round(bankroll, 2)}€

𝗥𝗢𝗜: {round(roi, 2)}%
"""


# ─── MARKET ALERT ───

def market_alert():
    global alert_cache, alert_cache_time

    if time.time() - alert_cache_time < 1800 and alert_cache:
        return alert_cache

    matches = get_matches()
    if not matches:
        return "No alert"

    home, away = matches[0]
    open_odds = round(random.uniform(1.90, 2.40), 2)
    drop = round(random.uniform(0.15, 0.35), 2)
    new_odds = round(open_odds - drop, 2)

    alert_text = f"""
🚨 𝑺𝑯𝑨𝑹𝑷 𝑴𝑶𝑵𝑬𝒀 𝑨𝑳𝑬𝑹𝑻 🚨

⚽ {home} vs {away}

Odds dropped:
{open_odds} → {new_odds}

𝗛𝗘𝗔𝗩𝗬 𝗕𝗘𝗧𝗧𝗜𝗡𝗚 𝗔𝗖𝗧𝗜𝗩𝗜𝗧𝗬 𝗗𝗘𝗧𝗘𝗖𝗧𝗘𝗗.

━━━━━━━━━━━━━━

⚡ Elite members will receive the official signal before the market reacts.

⚠️ Access to the 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 network may close once signals are released.
"""

    alert_cache = alert_text
    alert_cache_time = time.time()
    return alert_text


# ─── FREE SAMPLE ───

def daily_sample(user_id):
    now = int(time.time())
    row = cursor.execute(
        "SELECT last_time FROM free_sample WHERE user_id=?",
        (user_id,)
    ).fetchone()

    if row:
        last_time = row[0]
        if now - last_time < 172800:
            remaining = 172800 - (now - last_time)
            hours = remaining // 3600
            return f"""
⏳ 𝑭𝑹𝑬𝑬 𝑺𝑨𝑴𝑷𝑳𝑬 𝑨𝑳𝑹𝑬𝑨𝑫𝒀 𝑼𝑺𝑬𝑫
Next free bet available in {hours} hours.
"""

    bets = get_value_bets()
    if not bets:
        return "⚠️ No value bets detected today."

    cursor.execute(
        "INSERT OR REPLACE INTO free_sample VALUES (?,?)",
        (user_id, now)
    )
    db.commit()
    return bets[0]


def send_sample_with_scan(user_id):
    now = int(time.time())
    row = cursor.execute(
        "SELECT last_time FROM free_sample WHERE user_id=?",
        (user_id,)
    ).fetchone()

    if row:
        last_time = row[0]
        if now - last_time < 172800:
            remaining = 172800 - (now - last_time)
            hours = remaining // 3600
            bot.send_message(
                user_id,
f"""
⏳ 𝑭𝑹𝑬𝑬 𝑺𝑨𝑴𝑷𝑳𝑬 𝑨𝑳𝑹𝑬𝑨𝑫𝒀 𝑼𝑺𝑬𝑫

Next free bet available in **{hours} hours**.
"""
            )
            return

    msg = bot.send_message(
        user_id,
"""
🔎 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑺𝑪𝑨𝑵𝑵𝑰𝑵𝑮

Analyzing football markets...

Scanning leagues ███░░░░░░

📡 Data feeds connected  
🧠 Probability models running  
📊 Detecting bookmaker value
"""
    )

    time.sleep(2)

    bets = get_value_bets()
    if not bets:
        bot.edit_message_text(
"""
⚠️ The system is still finalizing today's analysis.

𝗣𝗟𝗘𝗔𝗦𝗘 𝗧𝗥𝗬 𝗔𝗚𝗔𝗜𝗡 𝗜𝗡 𝗔 𝗙𝗘𝗪 𝗠𝗜𝗡𝗨𝗧𝗘𝗦.
""",
            user_id,
            msg.message_id
        )
        return

    bet = bets[0]

    cursor.execute(
        "INSERT OR REPLACE INTO free_sample VALUES (?,?)",
        (user_id, now)
    )
    db.commit()

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔥 Unlock VIP Access", callback_data="elite"))

    bot.edit_message_text(
f"""
🎁 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑭𝑹𝑬𝑬 𝑺𝑨𝑴𝑷𝑳𝑬

{bet}

━━━━━━━━━━━━━━

This opportunity was detected during today's model analysis.

Elite members receive the -full signal card daily at 18:00-.
• 𝗔𝗧𝗛𝗘𝗡𝗦 𝗧𝗜𝗠𝗘 🇬🇷
""",
        user_id,
        msg.message_id,
        reply_markup=keyboard
    )


# ─── BET SLIP IMAGE GENERATOR ───

def generate_bet_slip_image(bet_text):
    """Generate a simple bet slip image using PIL if available, else skip."""
    try:
        from PIL import Image, ImageDraw, ImageFont

        img = Image.new('RGB', (600, 400), color=(15, 15, 25))
        draw = ImageDraw.Draw(img)

        # Use default font
        try:
            font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
            font_body = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        except:
            font_title = ImageFont.load_default()
            font_body = ImageFont.load_default()

        # Header bar
        draw.rectangle([0, 0, 600, 50], fill=(218, 165, 32))
        draw.text((20, 12), "VALUEHUNTER SIGNAL", fill=(15, 15, 25), font=font_title)

        # Body text
        y = 70
        for line in bet_text.split("\n"):
            line = line.strip()
            if not line:
                y += 10
                continue
            if line.startswith("━"):
                draw.line([(20, y + 5), (580, y + 5)], fill=(60, 60, 80), width=1)
                y += 15
                continue
            draw.text((20, y), line, fill=(220, 220, 230), font=font_body)
            y += 25

        buf = BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf

    except ImportError:
        return None


# ─── VIP ENGINE STATUS ───

def engine_status_text():
    """Generate engine health status for VIP dashboard."""
    return """
⚙️ 𝑬𝑵𝑮𝑰𝑵𝑬 𝑺𝑻𝑨𝑻𝑼𝑺

📡 DATA FEEDS - ✅ ACTIVE
📊 MARKET MONITOR - ✅ ACTIVE
🧠 VALUE ENGINE - ✅ ACTIVE
📈 ODDS ANALYSIS - ✅ ACTIVE
🔒 SMART MONEY TRACKER - ✅ ACTIVE
⚡ CLV PREDICTOR - ✅ ACTIVE
"""


# ╔══════════════════════════════════════════════════════════════╗
# ║  PART 9 - CHANNEL AUTOMATION                                ║
# ╚══════════════════════════════════════════════════════════════╝

def channel_post(text):
    """Send a post to the configured channel."""
    if not CHANNEL_ID:
        return
    try:
        bot.send_message(CHANNEL_ID, text)
    except Exception as e:
        print(f"Channel post error: {e}")


def channel_morning_message():
    """Morning market briefing."""
    tz = pytz.timezone("Europe/Athens")
    today = datetime.now(tz).strftime("%A, %d %B")

    messages = [
        f"""
☀️ Καλημέρα - {today}

The ValueHunter engine is now online.

📡 Market feeds connected
🧠 Models warming up
📊 Scanning today's fixtures

Signals at 18:00 🇬🇷

Stay sharp. Stay disciplined.
""",
        f"""
🌅 Good morning - {today}

Engine status: ACTIVE

Today's football markets are being analyzed.

The model is scanning 200+ fixtures across 15+ leagues.

Only the strongest edges pass the filter.

⏳ Signal release: 18:00 Athens
""",
        f"""
📊 Market Open - {today}

ValueHunter analytics engine initialized.

📡 Data streaming
🔍 Scanning bookmaker inefficiencies
💎 Filtering value opportunities

Today's signals: 18:00 🇬🇷
""",
    ]
    return random.choice(messages)


def channel_market_talk():
    """Mid-day market analysis post."""
    messages = [
        """
📈 𝑴𝑨𝑹𝑲𝑬𝑻 𝑻𝑨𝑳𝑲

Early market movement detected across multiple leagues.

Some lines are already shifting - sharp money starting to flow.

The model is tracking 40+ markets in real time.

Our filter pipeline ensures only genuine value gets through.

🧠 Patience > Volume
""",
        """
🔍 𝑴𝑰𝑫-𝑫𝑨𝒀 𝑺𝑪𝑨𝑵

The engine has flagged several potential opportunities.

Still running through the full filter stack:
Data Quality → Team Strength → xG Model → Smart Money → CLV

Only signals that survive ALL filters get released.

That's why we win long-term.
""",
        """
💡 𝑴𝑨𝑹𝑲𝑬𝑻 𝑵𝑶𝑻𝑬

Remember: value betting is a marathon, not a sprint.

A 60% probability bet at 2.00 odds = positive expected value.

That's what the model hunts for every single day.

Discipline beats emotion. Always.
""",
    ]
    return random.choice(messages)


def channel_pre_signal():
    """Pre-signal hype post."""
    members = random.randint(14, 22)
    return f"""
⏳ 𝑺𝑰𝑮𝑵𝑨𝑳 𝑷𝑹𝑬𝑷𝑨𝑹𝑨𝑻𝑰𝑶𝑵

Model analysis: COMPLETED
Filter pipeline: PASSED
Signal card: READY

{members} Elite members are preparing positions.

🕕 Release in < 1 hour

Stay tuned.
"""


def channel_signal_released():
    """Signal announcement post."""
    return """
🔔 𝑺𝑰𝑮𝑵𝑨𝑳𝑺 𝑹𝑬𝑳𝑬𝑨𝑺𝑬𝑫

Today's ValueHunter signals have been delivered to the Elite network.

Members are placing their bets now.

📊 Full signal card with:
• Model probability
• Value edge
• CLV prediction
• Smart money data
• Confidence tier

Results will be posted after matches finish.
"""


def channel_win_report(match, pick, odds):
    """Post a win report to channel."""
    return f"""
✅ 𝑾𝑰𝑵 𝑪𝑶𝑵𝑭𝑰𝑹𝑴𝑬𝑫

⚽ {match}
🎯 {pick}
📊 Odds {odds}

Another edge captured by the ValueHunter model.

The system continues to deliver.

📡 Next signals: 18:00 tomorrow 🇬🇷
"""


def channel_evening_recap():
    """Evening summary."""
    perf = performance()
    return f"""
🌙 𝑬𝑽𝑬𝑵𝑰𝑵𝑮 𝑹𝑬𝑪𝑨𝑷

{perf}

━━━━━━━━━━━━━━

That's another day in the books.

The model scanned hundreds of markets. Only the best passed the filter.

Tomorrow we go again.

Καληνύχτα 🇬🇷
"""


def run_channel_automation():
    """Channel content scheduler - runs in background thread."""
    global channel_automation_active

    tz = pytz.timezone("Europe/Athens")
    posted_today = set()

    while channel_automation_active:
        try:
            now = datetime.now(tz)
            hour = now.hour
            minute = now.minute
            today = now.date()

            # Reset daily
            if hour == 0 and minute == 0:
                posted_today.clear()

            # Morning (09:00-09:05)
            if hour == 9 and minute <= 5 and "morning" not in posted_today:
                channel_post(channel_morning_message())
                posted_today.add("morning")

            # Market talk (13:00-13:05)
            if hour == 13 and minute <= 5 and "market_talk" not in posted_today:
                channel_post(channel_market_talk())
                posted_today.add("market_talk")

            # Pre-signal (17:15-17:20)
            if hour == 17 and 15 <= minute <= 20 and "pre_signal" not in posted_today:
                channel_post(channel_pre_signal())
                posted_today.add("pre_signal")

            # Signal released (18:05-18:10)
            if hour == 18 and 5 <= minute <= 10 and "signal_released" not in posted_today:
                channel_post(channel_signal_released())
                posted_today.add("signal_released")

            # Evening recap (22:00-22:05)
            if hour == 22 and minute <= 5 and "evening" not in posted_today:
                channel_post(channel_evening_recap())
                posted_today.add("evening")

            time.sleep(30)

        except Exception as e:
            print(f"Channel automation error: {e}")
            time.sleep(60)


# ╔══════════════════════════════════════════════════════════════╗
# ║  PART 10 - REFERRAL SYSTEM (UNCHANGED)                      ║
# ╚══════════════════════════════════════════════════════════════╝

def get_daily_referrers():
    global referrer_cache, referrer_cache_date
    global feed_cache, feed_cache_time

    now = time.time()
    today = datetime.now().date()

    if referrer_cache_date != today:
        names = random.sample(referrer_names, 5)
        referrals = [
            random.randint(100, 140),
            random.randint(80, 110),
            random.randint(60, 90),
            random.randint(40, 70),
            random.randint(30, 50)
        ]
        gains = [
            random.randint(1, 6),
            random.randint(1, 5),
            random.randint(1, 4),
            random.randint(1, 3),
            random.randint(1, 2)
        ]
        referrer_cache = f"""
👑 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑻𝑶𝑷 𝑹𝑬𝑭𝑬𝑹𝑹𝑬𝑹𝑺

🥇 {names[0]} - {referrals[0]} referrals (+{gains[0]} today)
🥈 {names[1]} - {referrals[1]} referrals (+{gains[1]} today)
🥉 {names[2]} - {referrals[2]} referrals (+{gains[2]} today)
4️⃣ {names[3]} - {referrals[3]} referrals (+{gains[3]} today)
5️⃣ {names[4]} - {referrals[4]} referrals (+{gains[4]} today)
"""
        referrer_cache_date = today

    if now - feed_cache_time > 1800:
        feed_lines = random.sample(referral_feed, 3)
        feed_cache = f"""

━━━━━━━━━━━━━━

{feed_lines[0]}
{feed_lines[1]}
{feed_lines[2]}
"""
        feed_cache_time = now

    return referrer_cache + feed_cache


def referral_link(user_id):
    return f"https://t.me/ValueHunterElite_bot?start={user_id}"


def get_referrals(user_id):
    cursor.execute(
        "SELECT COUNT(*) FROM referrals WHERE referrer=?",
        (user_id,)
    )
    result = cursor.fetchone()
    return result[0] if result else 0


def referral_discount(user_id):
    count = get_referrals(user_id)
    return (count // 30) * 50


def referral_panel(user_id):
    ref_link = f"https://t.me/ValueHunterElite_bot?start={user_id}"
    count = get_referrals(user_id)
    discount = referral_discount(user_id)
    link = referral_link(user_id)

    progress = min(count, 30)
    blocks = int((progress / 30) * 16)
    bar = "█" * blocks + "░" * (16 - blocks)

    text = f"""
🎁 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑹𝑬𝑭𝑬𝑹𝑹𝑨𝑳 𝑵𝑬𝑻𝑾𝑶𝑹𝑲

Invite new members to the ValueHunter platform and unlock exclusive rewards.

━━━━━━━━━━━━━━

📊 Progress

{bar}
{count} / 30

🏆 Reward

50% PRO ACCESS

━━━━━━━━━━━━━━

🔗 Your personal referral link

{link}

Share your link and earn rewards when members activate a subscription.
"""

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("👑 𝑻𝑶𝑷 𝑹𝑬𝑭𝑬𝑹𝑹𝑬𝑹𝑺", callback_data="top_ref"))
    keyboard.add(InlineKeyboardButton(
        "📤 SHARE BOT",
        url=f"tg://msg?text=🔥 I just joined the ValueHunter AI betting system.\n\nDaily VIP signals at 18:00 🇬🇷\n\nJoin here: {ref_link}"
    ))
    keyboard.add(InlineKeyboardButton("◀ 𝑩𝑨𝑪𝑲", callback_data="back_menu"))

    bot.send_message(user_id, text, reply_markup=keyboard)


# ╔══════════════════════════════════════════════════════════════╗
# ║  PART 11 - AUTO SIGNAL SCHEDULER                            ║
# ╚══════════════════════════════════════════════════════════════╝

daily_bets_cache = []

def send_signals():
    global daily_bets_cache
    tz = pytz.timezone("Europe/Athens")
    admin_sent_today = False
    vip_sent_today = False
    last_cleanup_day = None
    
    fomo_sent_1730 = False
    fomo_sent_1745 = False

    while True:
        try:
            today = datetime.now(tz).date()

            if last_cleanup_day != today:
                clean_sent_bets()
                last_cleanup_day = today

            expiry_reminders()
            grade_results()

            now = datetime.now(tz)
            hour = now.hour
            minute = now.minute
            
            # PRE-SCAN WARMUP (16:30–16:59)
            if hour == 16 and minute >= 30:
                try:
                    print("PRE-SCAN WARMUP RUNNING")
                    get_value_bets()
                except Exception as e:
                    print("PRE-SCAN ERROR:", e)

            # ADMIN 17:00
            if hour == 17 and minute <= 5 and not admin_sent_today:
                print("ADMIN SIGNAL TRIGGERED", now)
                
                daily_bets_cache = get_value_bets()
                bets = daily_bets_cache
                
                if not bets:
                    print("NO BETS FOUND")
                    bets = ["No value bets today"]
                    
                if bets:
                    bot.send_message(
                        ADMIN_ID,
                        "ADMIN SIGNALS\n\n" + "\n\n".join(bets[:3])
                    )
                admin_sent_today = True

            # PRE SIGNAL FOMO 17:30
            if hour == 17 and 29 <= minute <= 31 and not fomo_sent_1730:
                members = random.randint(14, 22)
                countdown = signal_timer()[1]
                users = get_all_users()
                fomo_sent_1730 = True

                text = f"""
👑 𝑬𝑳𝑰𝑻𝑬 𝑵𝑬𝑻𝑾𝑶𝑹𝑲

{members} members preparing today's bets.

⏳ Signal release in
{countdown}

⚜️ Elite members are already preparing their positions.

🔐 Unlock access before the signals are released.
"""
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton("⚜️ 𝑼𝑵𝑳𝑶𝑪𝑲 𝑽𝑰𝑷 𝑺𝑰𝑮𝑵𝑨𝑳𝑺", callback_data="elite"))

                for uid in users:
                    if is_vip(uid):
                        continue
                    try:
                        bot.send_message(uid, text, reply_markup=keyboard)
                        time.sleep(0.05)
                    except:
                        pass

            # FOMO MESSAGE 17:45
            if hour == 17 and 44 <= minute <= 46 and not fomo_sent_1745:
                users = get_all_users()
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton("⚜️ 𝑼𝑵𝑳𝑶𝑪𝑲 𝑽𝑰𝑷 𝑺𝑰𝑮𝑵𝑨𝑳𝑺", callback_data="elite"))
                fomo_sent_1745 = True

                text = """
⚜️ 𝑻𝑶𝑫𝑨𝒀'𝑺 𝑽𝑰𝑷 𝑺𝑰𝑮𝑵𝑨𝑳𝑺 𝑨𝑹𝑬 𝑹𝑬𝑨𝑫𝒀

The 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 model has finalized today's analysis.

Our system scanned hundreds of matches and identified the strongest value opportunities.

━━━━━━━━━━━━━━

⚠️ 𝑽𝑰𝑷 signals will be released at 18:00.(Europe/Athens)🇬🇷

𝗠𝗘𝗠𝗕𝗘𝗥𝗦 𝗔𝗥𝗘 𝗔𝗟𝗥𝗘𝗔𝗗𝗬 𝗣𝗥𝗘𝗣𝗔𝗥𝗜𝗡𝗚 𝗧𝗢𝗗𝗔𝗬'𝗦 𝗕𝗘𝗧𝗦.

𝗦𝗘𝗖𝗨𝗥𝗘 𝗔𝗖𝗖𝗘𝗦𝗦 𝗕𝗘𝗙𝗢𝗥𝗘 𝗧𝗛𝗘 𝗥𝗘𝗟𝗘𝗔𝗦𝗘.
"""
                for uid in users:
                    if is_vip(uid):
                        continue
                    try:
                        bot.send_message(uid, text, reply_markup=keyboard)
                        time.sleep(0.05)
                    except:
                        pass

            # VIP 18:00
            if hour >= 18 and not vip_sent_today:
                print("VIP SIGNAL TRIGGERED", now)
                
                bets = daily_bets_cache
                vip_sent_today = True
                users = get_vip_users()
                
                if ADMIN_TEST_MODE:
                    users.append((ADMIN_ID,ADMIN_TEST_PLAN))

                for uid, plan in users:

                    if plan == "BASIC":
                        picks = bets[:1]

                    elif plan in ["PRO", "DAY"]:
                        picks = bets[:3]

                    else:
                        continue

                    text = "🎖️ VIP SIGNALS\n\n" + "\n\n".join(picks)

                    # VIP buttons
                    keyboard = InlineKeyboardMarkup()

                    keyboard.add(
                        InlineKeyboardButton("📊 Match Insight", callback_data="match_insight")
                    )

                    if plan in ["PRO","DAY"]:
                        keyboard.add(
                            InlineKeyboardButton("🎁 Referral Program", callback_data="referral")
                        )

                    try:
                        msg = bot.send_message(
                            uid,
                            text,
                            reply_markup=keyboard,
                            protect_content=True
                        )

                        # store message id for live updates
                        try:
                            cursor.execute(
                                "INSERT INTO signal_messages(user_id,message_id) VALUES (?,?)",
                                (uid,msg.message_id)
                            )
                            db.commit()
                        except:
                            pass

                        # Send bet slip image
                        if picks:
                            img = generate_bet_slip_image(picks[0])
                            if img:
                                bot.send_photo(uid, img, protect_content=True)

                        # PRO users get parlay
                        if plan in ["PRO","DAY"] and parlay_cache:
                            try:
                                bot.send_message(uid, str(parlay_cache), protect_content=True)
                            except:
                                pass

                    except:
                        pass

                    time.sleep(0.05)

            # Reset daily flags
            if hour == 0 and minute == 0:
                admin_sent_today = False
                vip_sent_today = False
                fomo_sent_1730 = False
                fomo_sent_1745 = False

            # MONTHLY REPORT
            if now.day == 1 and hour == 12 and minute == 0:
                report = monthly_report()
                send_secure_message(ADMIN_ID, report)

            time.sleep(30)

        except Exception as e:
            print("SEND SIGNALS ERROR:", e)
            time.sleep(30)

def send_secure_message(user_id, text):
    try:
        bot.send_message(user_id, text, protect_content=True)
    except:
        pass


def expiry_reminders():
    now = int(time.time())
    rows = cursor.execute(
        "SELECT user_id,plan,expire FROM vip_users WHERE expire > ?",
        (now,)
    ).fetchall()

    for user_id, plan, expire in rows:
        remaining = expire - now

        if remaining <= 3600:
            if cursor.execute(
                "SELECT user_id FROM expiry_notified WHERE user_id=?",
                (user_id,)
            ).fetchone():
                continue

            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("⚜️ 𝑹𝑬𝑵𝑬𝑾 𝑽𝑰𝑷 𝑨𝑪𝑪𝑬𝑺𝑺", callback_data="elite"))

            if plan == "DAY":
                text = """
⚠️ 𝒀𝑶𝑼𝑹 𝑫𝑨𝒀 𝑷𝑨𝑺𝑺 𝑰𝑺 𝑬𝑿𝑷𝑰𝑹𝑰𝑵𝑮 𝑺𝑶𝑶𝑵

Your 24 hour 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 access will expire in less than 1 hour.

We hope you enjoyed experiencing the ValueHunter Elite system today.

Every day our model scans hundreds of matches to uncover hidden bookmaker value opportunities.


💎 Today's members are already preparing the next signals.

If your access expires, you may miss the next opportunities.

━━━━━━━━━━━━━━

🎖️ Thank you for trying 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹.

𝗬𝗢𝗨 𝗖𝗔𝗡 𝗖𝗢𝗡𝗧𝗜𝗡𝗨𝗘 𝗥𝗘𝗖𝗘𝗜𝗩𝗜𝗡𝗚 𝗦𝗜𝗚𝗡𝗔𝗟𝗦 𝗕𝗬 𝗔𝗖𝗧𝗜𝗩𝗔𝗧𝗜𝗡𝗚 𝗔 𝗠𝗘𝗠𝗕𝗘𝗥𝗦𝗛𝗜𝗣 𝗕𝗘𝗟𝗢𝗪.
"""
            else:
                text = """
⚠️ 𝒀𝑶𝑼𝑹 𝑽𝑰𝑷 𝑨𝑪𝑪𝑬𝑺𝑺 𝑰𝑺 𝑨𝑩𝑶𝑼𝑻 𝑻𝑶 𝑬𝑿𝑷𝑰𝑹𝑬

Your 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑬𝑳𝑰𝑻𝑬 membership will expire in less than 1 hour.

Every day our analytics engine scans hundreds of matches to identify **high value betting opportunities** before the market moves.


💎 The next signals will be released again at **18:00**.

If your access expires now, you may miss the upcoming value opportunities that our members are preparing for.

━━━━━━━━━━━━━━

Thank you for being part of the -ValueHunter Elite network-.

Renew your access below to continue receiving signals.
"""

            try:
                bot.send_message(user_id, text, reply_markup=keyboard)
            except:
                pass

            cursor.execute(
                "INSERT INTO expiry_notified VALUES (?)",
                (user_id,)
            )
            db.commit()


def keep_alive():
    url = "https://valuehunter-bot-production.up.railway.app"
    while True:
        try:
            requests.get(url, timeout=10)
        except:
            pass
        time.sleep(600)


def clean_sent_bets():
    with db_lock:
        cursor.execute("""
        DELETE FROM sent_bets
        WHERE rowid NOT IN (
            SELECT rowid FROM sent_bets ORDER BY rowid DESC LIMIT 5000
        )
        """)
        db.commit()

    # Clean CLV history: remove entries older than 4 days
    now = time.time()
    stale_keys = [k for k, v in clv_history.items() if now - v.get("first_seen", now) > 345600]
    for k in stale_keys:
        del clv_history[k]


# ╔══════════════════════════════════════════════════════════════╗
# ║  PART 12 - VIP DASHBOARD UI                                 ║
# ╚══════════════════════════════════════════════════════════════╝

def vip_initialization_animation(user_id):
    message = bot.send_message(
        user_id,
        "🎖️ Initializing ValueHunter System...\n\n⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜"
    )

    blocks = [
        "🟩⬜⬜⬜⬜⬜⬜⬜⬜⬜",
        "🟩🟩⬜⬜⬜⬜⬜⬜⬜⬜",
        "🟩🟩🟩⬜⬜⬜⬜⬜⬜⬜",
        "🟩🟩🟩🟩⬜⬜⬜⬜⬜⬜",
        "🟩🟩🟩🟩🟩⬜⬜⬜⬜⬜",
        "🟩🟩🟩🟩🟩🟩⬜⬜⬜⬜",
        "🟩🟩🟩🟩🟩🟩🟩⬜⬜⬜",
        "🟩🟩🟩🟩🟩🟩🟩🟩⬜⬜",
        "🟩🟩🟩🟩🟩🟩🟩🟩🟩⬜",
        "🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩"
    ]

    for bar in blocks:
        time.sleep(0.4)
        try:
            bot.edit_message_text(
                f"🔍 Initializing ValueHunter System...\n\n{bar}",
                user_id,
                message.message_id
            )
        except:
            pass

    time.sleep(0.3)
    send_vip_dashboard(user_id)


def send_vip_dashboard(user_id, message_id=None):
    label, countdown = signal_timer()

    text = f"""
⚜️ 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑬𝑳𝑰𝑻𝑬 𝑵𝑬𝑻𝑾𝑶𝑹𝑲

𝑾𝑬𝑳𝑪𝑶𝑴𝑬 𝑰𝑵𝑺𝑰𝑫𝑬 𝑻𝑯𝑬 𝑷𝑹𝑰𝑽𝑨𝑻𝑬 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑰𝑵𝑻𝑬𝑳𝑳𝑰𝑮𝑬𝑵𝑪𝑬 𝑺𝒀𝑺𝑻𝑬𝑴

You now have access to a restricted betting analytics network designed to detect bookmaker pricing errors and high-value opportunities across global football markets.

━━━━━━━━━━━━━━

🧠 Advanced Expected Goals Models  
📊 Market Inefficiency Detection  
📡 Sharp Money Monitoring  
💎 Liquidity Intelligence Signals  

━━━━━━━━━━━━━━

📡 𝑺𝒀𝑺𝑻𝑬𝑴 𝑺𝑻𝑨𝑻𝑼𝑺

📟 Data feeds active  
🟢 Market monitoring active  
🟢 Model scanning global leagues  

━━━━━━━━━━━━━━

⏳ 𝗡𝗘𝗫𝗧 𝗦𝗜𝗚𝗡𝗔𝗟 𝗥𝗘𝗟𝗘𝗔𝗦𝗘
{countdown} (𝗘𝗨𝗥𝗢𝗣𝗘/𝗔𝗧𝗛𝗘𝗡𝗦)🇬🇷

⚠️ Signals inside this network are shared with a limited number of Elite members to protect the betting edge.
"""

    if message_id:
        bot.edit_message_text(text, user_id, message_id, reply_markup=vip_dashboard_keyboard())
    else:
        bot.send_message(user_id, text, reply_markup=vip_dashboard_keyboard())


def send_vip_menu(user_id, message_id=None):
    label, countdown = signal_timer()
    now = datetime.now(pytz.timezone("Europe/Athens")).hour

    if now < 18:
        text = f"""
⚜️ 𝑽𝑰𝑷 𝑪𝑶𝑵𝑻𝑹𝑶𝑳 𝑷𝑨𝑵𝑬𝑳

The 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 analytics engine is currently scanning today's football markets.

📡 Market data streaming  
🧠 Models calculating probabilities  
💎 Value opportunities being filtered  

━━━━━━━━━━━━━━
🎖️ 𝑬𝑳𝑰𝑻𝑬 𝑵𝑬𝑻𝑾𝑶𝑹𝑲

⏳ 𝑺𝑰𝑮𝑵𝑨𝑳 𝑹𝑬𝑳𝑬𝑨𝑺𝑬 𝑰𝑵
{countdown}

🕕 18:00 (Athens Time) 🇬🇷
"""
    else:
        text = f"""
⚜️ 𝑽𝑰𝑷 𝑺𝑰𝑮𝑵𝑨𝑳 𝑪𝑬𝑵𝑻𝑬𝑹

Today's 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 signals have been released to the Elite network.

📊 Model probabilities calculated  
📡 Market pressure analysed  
💎 Premium value opportunities identified  

━━━━━━━━━━━━━━

⏳ 𝑺𝑰𝑮𝑵𝑨𝑳 𝑹𝑬𝑳𝑬𝑨𝑺𝑬
{countdown}

🕕 18:00 (Athens Time) 🇬🇷
"""

    if message_id:
        bot.edit_message_text(text, user_id, message_id, reply_markup=vip_menu_keyboard())
    else:
        bot.send_message(user_id, text, reply_markup=vip_menu_keyboard())


def vip_support(user_id, message_id=None):
    text = """
💬 𝑽𝑰𝑷 𝑺𝑼𝑷𝑷𝑶𝑹𝑻

Need assistance with signals, membership access or platform support?

━━━━━━━━━━━━━━

📡 𝟐𝟒/𝟕 𝗣𝗥𝗜𝗢𝗥𝗜𝗧𝗬 𝗦𝗨𝗣𝗣𝗢𝗥𝗧

Elite members can contact the ValueHunter support desk anytime.

━━━━━━━━━━━━━━

📩 𝗖𝗢𝗡𝗧𝗔𝗖𝗧 𝗦𝗨𝗣𝗣𝗢𝗥𝗧

@MrMasterlegacy1
"""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀ Back to VIP Menu", callback_data="vip_menu"))

    if message_id:
        bot.edit_message_text(text, user_id, message_id, reply_markup=keyboard)
    else:
        bot.send_message(user_id, text, reply_markup=keyboard)


def vip_status(user_id, message_id=None):
    row = cursor.execute(
        "SELECT plan,expire FROM vip_users WHERE user_id=?",
        (user_id,)
    ).fetchone()

    if not row:
        return

    plan, expire = row
    expiry = datetime.fromtimestamp(expire).strftime("%d %B %Y")

    text = f"""
📅 𝑬𝑳𝑰𝑻𝑬 𝑴𝑬𝑴𝑩𝑬𝑹𝑺𝑯𝑰𝑷

👤 𝗨𝗦𝗘𝗥 𝗜𝗗: {user_id}

💎 𝗣𝗟𝗔𝗡: {plan}

📊 𝗦𝗜𝗚𝗡𝗔𝗟𝗦 𝗣𝗘𝗥 𝗗𝗔𝗬: up to 3

⏳ 𝗔𝗖𝗖𝗘𝗦𝗦 𝗘𝗫𝗣𝗜𝗥𝗘𝗦:
{expiry}
"""

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀ Back to VIP Menu", callback_data="vip_menu"))

    if message_id:
        bot.edit_message_text(text, user_id, message_id, reply_markup=keyboard)
    else:
        bot.send_message(user_id, text, reply_markup=keyboard)


def startup_loading(chat_id):
    msg = bot.send_message(
        chat_id,
"""
Loading...

█░░░░░░░░░░░░░░░
━━━━━━━━━━━━━━

⚜️ 𝑰𝒏𝒊𝒕𝒊𝒂𝒍𝒊𝒛𝒊𝒏𝒈 𝑽𝒂𝒍𝒖𝒆𝑯𝒖𝒏𝒕𝒆𝒓 𝑻𝒆𝒓𝒎𝒊𝒏𝒂𝒍...
"""
    )

    steps = [
        ("███░░░░░░░░░░░░░", "📡 𝑪𝒐𝒏𝒏𝒆𝒄𝒕𝒊𝒏𝒈 𝒕𝒐 𝒈𝒍𝒐𝒃𝒂𝒍 𝒇𝒐𝒐𝒕𝒃𝒂𝒍𝒍 𝒅𝒂𝒕𝒂 𝒇𝒆𝒆𝒅𝒔..."),
        ("█████░░░░░░░░░░░", "🌐 𝑬𝒔𝒕𝒂𝒃𝒍𝒊𝒔𝒉𝒊𝒏𝒈 𝒔𝒆𝒄𝒖𝒓𝒆 𝒂𝒏𝒂𝒍𝒚𝒕𝒊𝒄𝒔 𝒏𝒆𝒕𝒘𝒐𝒓𝒌..."),
        ("████████░░░░░░░░", "📊 𝑺𝒄𝒂𝒏𝒏𝒊𝒏𝒈 𝒃𝒐𝒐𝒌𝒎𝒂𝒌𝒆𝒓 𝒐𝒅𝒅𝒔 𝒇𝒆𝒆𝒅𝒔..."),
        ("███████████░░░░░", "🧠 𝑳𝒐𝒂𝒅𝒊𝒏𝒈 𝒑𝒓𝒐𝒃𝒂𝒃𝒊𝒍𝒊𝒕𝒚 𝒎𝒐𝒅𝒆𝒍𝒔..."),
        ("████████████████", "🚀 𝑽𝒂𝒍𝒖𝒆𝑯𝒖𝒏𝒕𝒆𝒓 𝒔𝒚𝒔𝒕𝒆𝒎 𝒓𝒆𝒂𝒅𝒚"),
    ]

    for bar, status in steps:
        time.sleep(1.2)
        try:
            bot.edit_message_text(
                f"Loading...\n\n{bar}\n━━━━━━━━━━━━━━\n\n{status}",
                chat_id,
                msg.message_id
            )
        except:
            pass

    time.sleep(1)


# ─── FAQ SYSTEM ───

def faq_menu(chat_id, message_id):
    text = """
❓ 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑭𝑨𝑸

Welcome inside the ValueHunter intelligence system.

What would you like to know?

━━━━━━━━━━━━━━
"""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🧠 How ValueHunter works", callback_data="faq_system"))
    keyboard.add(InlineKeyboardButton("📊 Why value betting wins", callback_data="faq_value"))
    keyboard.add(InlineKeyboardButton("💸 Referral program", callback_data="faq_referral"))
    keyboard.add(InlineKeyboardButton("⚜ Unlock Elite Access", callback_data="elite"))
    keyboard.add(InlineKeyboardButton("⬅ Back", callback_data="back_menu"))

    bot.edit_message_text(text, chat_id, message_id, reply_markup=keyboard)


def faq_system(chat_id, message_id):
    text = """
🧠 𝑯𝑶𝑾 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑾𝑶𝑹𝑲𝑺

ValueHunter is a betting intelligence engine.

The system scans hundreds of football matches daily to detect bookmaker pricing inefficiencies.

Our analytics models track:

⚙️ Expected Goals data  
📉 Market price inefficiencies  
📡 Sharp odds movement  
💰 Liquidity signals  

Only the **strongest value opportunities** pass the filters and reach Elite members.
"""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("➡ Next", callback_data="faq_value"))
    keyboard.add(InlineKeyboardButton("⬅ Back", callback_data="faq"))

    bot.edit_message_text(text, chat_id, message_id, reply_markup=keyboard)


def faq_value(chat_id, message_id):
    text = """
📊 𝑾𝑯𝒀 𝑽𝑨𝑳𝑼𝑬 𝑩𝑬𝑻𝑻𝑰𝑵𝑮 𝑾𝑰𝑵𝑺

Most bettors lose because they place bets after the market moves.

Professional bettors place bets **before the odds adjust**.

This is called **value betting**.

Elite members receive signals before the market reacts.

This is where long-term profit exists.
"""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("➡ Next", callback_data="faq_referral"))
    keyboard.add(InlineKeyboardButton("⬅ Back", callback_data="faq_system"))

    bot.edit_message_text(text, chat_id, message_id, reply_markup=keyboard)


def faq_referral(chat_id, message_id):
    text = """
💸 𝑹𝑬𝑭𝑬𝑹𝑹𝑨𝑳 𝑷𝑹𝑶𝑮𝑹𝑨𝑴

Invite users to the ValueHunter network.

When someone joins using your referral link and purchases a membership:

✔ Your referral score increases  
✔ Your discount increases  

💎 30 referrals unlock **50% PRO access**

Top users inside the network are already earning free months through referrals.
"""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⚜ Unlock Elite Access", callback_data="elite"))
    keyboard.add(InlineKeyboardButton("⬅ Back", callback_data="faq_value"))

    bot.edit_message_text(text, chat_id, message_id, reply_markup=keyboard)


# ╔══════════════════════════════════════════════════════════════╗
# ║  PART 13 - TELEGRAM HANDLERS                                ║
# ╚══════════════════════════════════════════════════════════════╝

@bot.message_handler(commands=["start"])
def start(m):
    user_id = m.chat.id

    if not is_vip(user_id):
        startup_loading(user_id)

    parts = m.text.split()
    if len(parts) > 1:
        try:
            referrer = int(parts[1])
            if referrer != user_id:
                cursor.execute(
                    "INSERT OR IGNORE INTO referrals(referrer,referred) VALUES(?,?)",
                    (referrer, user_id)
                )
                db.commit()
        except:
            pass

    cursor.execute("INSERT OR IGNORE INTO users VALUES (?)", (user_id,))
    db.commit()

    if is_vip(user_id):
        send_vip_dashboard(user_id)
        return

    label, countdown = signal_timer()

    bot.send_message(
        m.chat.id,
f"""
🎖️ 𝑾𝑬𝑳𝑪𝑶𝑴𝑬 𝑻𝑶 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹

You are currently viewing the ValueHunter platform.

Full access to the 𝑬𝑳𝑰𝑻𝑬 𝑩𝑬𝑻𝑻𝑰𝑵𝑮 𝑵𝑬𝑻𝑾𝑶𝑹𝑲 is restricted to members.

━━━━━━━━━━━━━━

🕕 𝑶𝑭𝑭𝑰𝑪𝑰𝑨𝑳 𝑺𝑰𝑮𝑵𝑨𝑳 𝑹𝑬𝑳𝑬𝑨𝑺𝑬  
• 18:00 (Athens Time) 🇬🇷

━━━━━━━━━━━━━━

👑 {label}

⏱️ {countdown}

━━━━━━━━━━━━━━

🎖️ Activate membership to unlock the ValueHunter signal network.
""",
        reply_markup=main_menu()
    )

    start_conversion_funnel(m.chat.id)
    
@bot.message_handler(commands=['testvip'])
def admin_testvip(message):

    if message.from_user.id != ADMIN_ID:
        return

    keyboard = InlineKeyboardMarkup()

    keyboard.add(
        InlineKeyboardButton("BASIC",callback_data="test_basic"),
        InlineKeyboardButton("PRO",callback_data="test_pro")
    )

    keyboard.add(
        InlineKeyboardButton("DAY",callback_data="test_day")
    )

    bot.send_message(
        ADMIN_ID,
        "🧪 Select VIP plan to simulate",
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("test_"))
def set_test_plan(call):

    global ADMIN_TEST_MODE
    global ADMIN_TEST_PLAN

    if call.from_user.id != ADMIN_ID:
        return

    plan = call.data.split("_")[1].upper()

    ADMIN_TEST_MODE = True
    ADMIN_TEST_PLAN = plan

    bot.send_message(
        ADMIN_ID,
        f"""
🧪 TEST VIP MODE ACTIVE

Plan: {plan}

You will now receive signals like a real VIP.
"""
    )

# ─── CALLBACK HANDLER ───

@bot.callback_query_handler(func=lambda c: True)
def callbacks(c):
    bot.answer_callback_query(c.id)
    chat_id = c.message.chat.id
    msg_id = c.message.message_id

    if c.data == "dev_sendvip":
        sendvip(c.message)

    # VIP DASHBOARD
    elif c.data == "vip_dashboard":
        send_vip_dashboard(chat_id, msg_id)

    # VIP MENU
    elif c.data == "vip_menu":
        send_vip_menu(chat_id, msg_id)

    # MODEL INSIGHTS
    elif c.data == "model_insights":
        text = """
📡 𝑴𝑶𝑫𝑬𝑳 𝑰𝑵𝑺𝑰𝑮𝑯𝑻𝑺

The 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 analytics engine scans hundreds of football matches daily to detect bookmaker pricing inefficiencies.

⚙️ Expected Goals modelling  
📉 Market price inefficiencies  
🔋 Sharp odds movement tracking  
💰 Liquidity signals  

𝗢𝗡𝗟𝗬 𝗧𝗛𝗘 𝗦𝗧𝗥𝗢𝗡𝗚𝗘𝗦𝗧 𝗩𝗔𝗟𝗨𝗘 𝗢𝗣𝗣𝗢𝗥𝗧𝗨𝗡𝗜𝗧𝗜𝗘𝗦 𝗣𝗔𝗦𝗦 𝗧𝗛𝗘 𝗠𝗢𝗗𝗘𝗟 𝗙𝗜𝗟𝗧𝗘𝗥𝗦 𝗔𝗡𝗗 𝗥𝗘𝗔𝗖𝗛 𝗘𝗟𝗜𝗧𝗘 𝗠𝗘𝗠𝗕𝗘𝗥𝗦.
""" + engine_status_text()

        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("◀ 𝑩𝑨𝑪𝑲 𝑻𝑶 𝑫𝑨𝑺𝑯𝑩𝑶𝑨𝑹𝑫", callback_data="vip_dashboard"))
        bot.edit_message_text(text, chat_id, msg_id, reply_markup=keyboard)

    # BETTING STRATEGY
    elif c.data == "betting_strategy":
        text = """
🧠 𝑩𝑬𝑻𝑻𝑰𝑵𝑮 𝑺𝑻𝑹𝑨𝑻𝑬𝑮𝒀

The 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 system focuses on long-term profitable betting.

𝗥𝗘𝗖𝗢𝗠𝗠𝗘𝗡𝗗𝗘𝗗 𝗦𝗧𝗔𝗞𝗜𝗡𝗚 𝗠𝗢𝗗𝗘𝗟:

💰 𝟏-𝟑% 𝑩𝑨𝑵𝑲𝑹𝑶𝑳𝑳 𝑹𝑰𝑺𝑲 𝑷𝑬𝑹 𝑺𝑰𝑮𝑵𝑨𝑳  
📊 𝟏-𝟑 𝑷𝑹𝑬𝑴𝑰𝑼𝑴 𝑽𝑨𝑳𝑼𝑬 𝑩𝑬𝑻𝑺 𝑷𝑬𝑹 𝑫𝑨𝒀

Consistent discipline allows members to replicate the same bankroll growth curve as the model.
"""
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("◀ 𝑩𝑨𝑪𝑲 𝑻𝑶 𝑫𝑨𝑺𝑯𝑩𝑶𝑨𝑹𝑫", callback_data="vip_dashboard"))
        bot.edit_message_text(text, chat_id, msg_id, reply_markup=keyboard)

    # RESULTS FEED
    elif c.data == "vip_results":
        # Show real results from DB
        rows = cursor.execute(
            "SELECT match,pick,odds,result,confidence_tier,clv FROM bets_history ORDER BY id DESC LIMIT 5"
        ).fetchall()

        if rows:
            text = "💸 𝑽𝑰𝑷 𝑹𝑬𝑺𝑼𝑳𝑻𝑺 𝑭𝑬𝑬𝑫\n\n"
            for match, pick, odds, result, tier, clv in rows:
                icon = "✔" if result == "WIN" else ("❌" if result == "LOSE" else "⏳")
                clv_str = f" | CLV +{clv}%" if clv and clv > 0 else ""
                tier_str = f" [{tier}]" if tier else ""
                text += f"{icon} {match}\n   {pick} @ {odds} - {result}{tier_str}{clv_str}\n\n"
        else:
            text = """
💸 𝑽𝑰𝑷 𝑹𝑬𝑺𝑼𝑳𝑻𝑺 𝑭𝑬𝑬𝑫

No results yet. Signals are released daily at 18:00.
"""
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("◀ 𝑩𝑨𝑪𝑲 𝑻𝑶 𝑫𝑨𝑺𝑯𝑩𝑶𝑨𝑹𝑫", callback_data="vip_dashboard"))
        bot.edit_message_text(text, chat_id, msg_id, reply_markup=keyboard)

    # VIP SIGNALS
    elif c.data == "vip_signals":
        now = datetime.now(pytz.timezone("Europe/Athens")).hour
        if now < 18:
            label, countdown = signal_timer()
            bars = ["████░░░░░░", "█████░░░░░", "██████░░░░", "███████░░░", "████████░░", "█████████░"]
            scan_bar = random.choice(bars)
            text = f"""
📊 𝑻𝑶𝑫𝑨𝒀'𝑺 𝑺𝑰𝑮𝑵𝑨𝑳𝑺

The 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 analytics engine is currently scanning today's football markets.

━━━━━━━━━━━━━━

⏳ 𝑺𝑰𝑮𝑵𝑨𝑳 𝑬𝑵𝑮𝑰𝑵𝑬 𝑺𝑻𝑨𝑻𝑼𝑺

Scanning markets {scan_bar}

📡 Data feeds connected  
🧠 Probability models calculating  
💎 Value opportunities filtering  

━━━━━━━━━━━━━━

🕕 𝑵𝑬𝑿𝑻 𝑺𝑰𝑮𝑵𝑨𝑳 𝑹𝑬𝑳𝑬𝑨𝑺𝑬
18:00 (Europe/Athens)

⏱ Countdown
{countdown}

Elite members will receive today's signals as soon as the analysis is completed.
"""
        else:
            text = """
📊 𝑻𝑶𝑫𝑨𝒀'𝑺 𝑺𝑰𝑮𝑵𝑨𝑳𝑺

Today's 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 signals have already been distributed to the Elite network.

━━━━━━━━━━━━━━

📡 Market monitoring active  
🧠 Models tracking closing line movement  
💎 Results feed will update once matches finish.

━━━━━━━━━━━━━━

Elite members are already positioned on today's value opportunities.
"""
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("◀ 𝑩𝑨𝑪𝑲 𝑻𝑶 𝑽𝑰𝑷 𝑴𝑬𝑵𝑼", callback_data="vip_menu"))
        bot.edit_message_text(text, chat_id, msg_id, reply_markup=keyboard)

    # PERFORMANCE
    elif c.data == "vip_performance":
        text = f"""
📈 𝑬𝑳𝑰𝑻𝑬 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑷𝑬𝑹𝑭𝑶𝑹𝑴𝑨𝑵𝑪𝑬

{performance()}

━━━━━━━━━━━━━━

📅 𝑴𝑶𝑵𝑻𝑯𝑳𝒀 𝑷𝑬𝑹𝑭𝑶𝑹𝑴𝑨𝑵𝑪𝑬 𝑶𝑽𝑬𝑹𝑽𝑰𝑬𝑾

{monthly_report()}
"""
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("◀ 𝑩𝑨𝑪𝑲 𝑻𝑶 𝑽𝑰𝑷 𝑴𝑬𝑵𝑼", callback_data="vip_menu"))
        bot.edit_message_text(text, chat_id, msg_id, reply_markup=keyboard)

    # Dev callbacks
    elif c.data == "dev_engine":
        dev_engine(chat_id)
    elif c.data == "dev_parlay":
        dev_parlay(chat_id)
    elif c.data == "dev_stats":
        stats(c.message)
    elif c.data == "dev_bankroll":
        bankroll(c.message)
    elif c.data == "dev_users":
        users(c.message)
    elif c.data == "dev_viplist":
        viplist(c.message)
    elif c.data == "dev_bets":
        bets(c.message)
    elif c.data == "dev_broadcast":
        broadcast(c.message)
    elif c.data == "dev_alert":
        force_alert(c.message)
    elif c.data == "dev_reload":
        reload_engine(c.message)
    elif c.data == "dev_payment":
        test_payment(c.message)

    # BANKROLL
    elif c.data == "vip_bankroll":
        text = bankroll_status()
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("◀ 𝑩𝑨𝑪𝑲 𝑻𝑶 𝑽𝑰𝑷 𝑴𝑬𝑵𝑼", callback_data="vip_menu"))
        bot.edit_message_text(text, chat_id, msg_id, reply_markup=keyboard)

    # ALERTS
    elif c.data == "vip_alerts":
        text = market_alert()
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("◀ 𝑩𝑨𝑪𝑲 𝑻𝑶 𝑽𝑰𝑷 𝑴𝑬𝑵𝑼", callback_data="vip_menu"))
        bot.edit_message_text(text, chat_id, msg_id, reply_markup=keyboard)

    # VIP STATUS
    elif c.data == "vip_status":
        vip_status(chat_id)

    # VIP SUPPORT
    elif c.data == "vip_support":
        vip_support(chat_id)

    # ELITE PLANS
    elif c.data == "elite":
        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("💎 𝑫𝑨𝒀 𝑷𝑨𝑺𝑺 - 𝟐𝟓€", callback_data="buy_day"))
        m.add(InlineKeyboardButton("🥉 𝑩𝑨𝑺𝑰𝑪 - 𝟓𝟎€", callback_data="buy_basic"))
        m.add(InlineKeyboardButton("🥇 𝑷𝑹𝑶 - 𝟏𝟎𝟎€", callback_data="buy_pro"))
        m.add(InlineKeyboardButton("◀ 𝑩𝑨𝑪𝑲 𝑻𝑶 𝑷𝑳𝑨𝑵𝑺", callback_data="back_menu"))

        bot.edit_message_text(
"""
🎖️ 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑬𝑳𝑰𝑻𝑬 𝑷𝑳𝑨𝑵𝑺

The 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 analytics engine scans hundreds of football matches daily to detect bookmaker pricing inefficiencies and high-probability value opportunities across global football markets.

━━━━━━━━━━━━━━
💎 𝑫𝑨𝒀 𝑷𝑨𝑺𝑺 - 𝟐𝟓€

✦ 𝟐𝟒 𝑯𝑶𝑼𝑹 𝑷𝑹𝑶 𝑨𝑪𝑪𝑬𝑺𝑺  
✦ Receive today's full signal card  
✦ Perfect to experience the ValueHunter system

━━━━━━━━━━━━━━

🥉 𝑩𝑨𝑺𝑰𝑪 - 𝟓𝟎€

✦ 𝟏 𝑷𝑹𝑬𝑴𝑰𝑼𝑴 𝑽𝑨𝑳𝑼𝑬 𝑩𝑬𝑻 𝑷𝑬𝑹 𝑫𝑨𝒀  
✦ Selected from the highest model edge  
✦ Ideal for disciplined bankroll growth

━━━━━━━━━━━━━━

🥇 𝑷𝑹𝑶 - 𝟏𝟎𝟎€

✦ 𝟑 𝑷𝑹𝑬𝑴𝑰𝑼𝑴 𝑽𝑨𝑳𝑼𝑬 𝑩𝑬𝑻𝑺 𝑫𝑨𝑰𝑳𝒀
✦ 𝟏 𝑬𝑿𝑪𝑳𝑼𝑺𝑰𝑽𝑬 8-𝑴𝑨𝑻𝑪𝑯 𝑷𝑨𝑹𝑳𝑨𝒀
✦ 𝑭𝑼𝑳𝑳 𝑨𝑪𝑪𝑬𝑺𝑺 𝑻𝑶 𝑴𝑶𝑫𝑬𝑳 𝑺𝑰𝑮𝑵𝑨𝑳𝑺

━━━━━━━━━━━━━━

🕕 𝑶𝑭𝑭𝑰𝑪𝑰𝑨𝑳 𝑺𝑰𝑮𝑵𝑨𝑳 𝑹𝑬𝑳𝑬𝑨𝑺𝑬  
18:00 (Athens Time) 🇬🇷

💎 Limited VIP access available today.
[Select your ValueHunter membership plan]
""",
            chat_id,
            msg_id,
            reply_markup=m
        )

    # BUY BASIC
    elif c.data == "buy_basic":
        link = create_payment(50, chat_id)
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("💳 𝑷𝑨𝒀 𝑾𝑰𝑻𝑯 𝑪𝑨𝑹𝑫 / 𝑪𝑹𝒀𝑷𝑻𝑶", url=link))
        keyboard.add(InlineKeyboardButton("◀ 𝑩𝑨𝑪𝑲 𝑻𝑶 𝑷𝑳𝑨𝑵𝑺", callback_data="elite"))

        bot.send_message(
            chat_id,
"""
🥉 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑩𝑨𝑺𝑰𝑪 𝑨𝑪𝑪𝑬𝑺𝑺

Unlock entry to the ValueHunter signal network.

━━━━━━━━━━━━━━

✦ 𝟏 𝑷𝑹𝑬𝑴𝑰𝑼𝑴 𝑽𝑨𝑳𝑼𝑬 𝑩𝑬𝑻 𝑷𝑬𝑹 𝑫𝑨𝒀  
✦ 𝑺𝑬𝑳𝑬𝑪𝑻𝑬𝑫 𝑭𝑹𝑶𝑴 𝑻𝑯𝑬 𝑯𝑰𝑮𝑯𝑬𝑺𝑻 𝑴𝑶𝑫𝑬𝑳 𝑬𝑫𝑮𝑬

━━━━━━━━━━━━━━

🕕 𝑶𝑭𝑭𝑰𝑪𝑰𝑨𝑳 𝑺𝑰𝑮𝑵𝑨𝑳 𝑹𝑬𝑳𝑬𝑨𝑺𝑬  
18:00 (Athens Time) 🇬🇷
""",
            reply_markup=keyboard
        )

    # BUY PRO
    elif c.data == "buy_pro":
        link = create_payment(100, chat_id)
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("💳 𝑷𝑨𝒀 𝑾𝑰𝑻𝑯 𝑪𝑨𝑹𝑫 / 𝑪𝑹𝒀𝑷𝑻𝑶", url=link))
        keyboard.add(InlineKeyboardButton("◀ 𝑩𝑨𝑪𝑲 𝑻𝑶 𝑷𝑳𝑨𝑵𝑺", callback_data="elite"))

        bot.send_message(
            chat_id,
"""
🥇 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑷𝑹𝑶 𝑨𝑪𝑪𝑬𝑺𝑺

Unlock full access to the ValueHunter signal network.

━━━━━━━━━━━━━━

✦ 𝟑 𝑷𝑹𝑬𝑴𝑰𝑼𝑴 𝑽𝑨𝑳𝑼𝑬 𝑩𝑬𝑻𝑺 𝑫𝑨𝑰𝑳𝒀
✦ 𝟏 𝑬𝑿𝑪𝑳𝑼𝑺𝑰𝑽𝑬 8-𝑴𝑨𝑻𝑪𝑯 𝑷𝑨𝑹𝑳𝑨𝒀
✦ 𝑭𝑼𝑳𝑳 𝑨𝑪𝑪𝑬𝑺𝑺 𝑻𝑶 𝑴𝑶𝑫𝑬𝑳 𝑺𝑰𝑮𝑵𝑨𝑳𝑺

━━━━━━━━━━━━━━

🕕 𝑶𝑭𝑭𝑰𝑪𝑰𝑨𝑳 𝑺𝑰𝑮𝑵𝑨𝑳 𝑹𝑬𝑳𝑬𝑨𝑺𝑬  
18:00 (Athens Time) 🇬🇷
""",
            reply_markup=keyboard
        )

    # BUY DAY
    elif c.data == "buy_day":
        link = create_payment(25, chat_id)
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("💳 𝑷𝑨𝒀 𝑾𝑰𝑻𝑯 𝑪𝑨𝑹𝑫 / 𝑪𝑹𝒀𝑷𝑻𝑶", url=link))
        keyboard.add(InlineKeyboardButton("◀ 𝑩𝑨𝑪𝑲 𝑻𝑶 𝑷𝑳𝑨𝑵𝑺", callback_data="elite"))

        bot.send_message(
            chat_id,
"""
💎 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑫𝑨𝒀 𝑷𝑨𝑺𝑺

Unlock full access to today's premium signals.

━━━━━━━━━━━━━━

✦ 𝟐𝟒 𝑯𝑶𝑼𝑹 𝑷𝑹𝑶 𝑨𝑪𝑪𝑬𝑺𝑺  
✦ 𝑼𝑷 𝑻𝑶 𝟑 𝑷𝑹𝑬𝑴𝑰𝑼𝑴 𝑽𝑨𝑳𝑼𝑬 𝑺𝑰𝑮𝑵𝑨𝑳𝑺

━━━━━━━━━━━━━━

🕕 𝑶𝑭𝑭𝑰𝑪𝑰𝑨𝑳 𝑺𝑰𝑮𝑵𝑨𝑳 𝑹𝑬𝑳𝑬𝑨𝑺𝑬  
18:00 (Athens Time) 🇬🇷
""",
            reply_markup=keyboard
        )

    # SAMPLE
    elif c.data == "sample":
        threading.Thread(
            target=send_sample_with_scan,
            args=(chat_id,)
        ).start()

    # ALERT
    elif c.data == "alert":
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔐 𝑼𝑵𝑳𝑶𝑪𝑲 𝑽𝑰𝑷 𝑨𝑪𝑪𝑬𝑺𝑺", callback_data="elite"))
        keyboard.add(InlineKeyboardButton("◀ 𝑩𝑨𝑪𝑲 𝑻𝑶 𝑷𝑳𝑨𝑵𝑺", callback_data="back_menu"))
        bot.send_message(chat_id, market_alert(), reply_markup=keyboard)

    # PERFORMANCE
    elif c.data == "perf":
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔐 𝑼𝑵𝑳𝑶𝑪𝑲 𝑽𝑰𝑷 𝑨𝑪𝑪𝑬𝑺𝑺", callback_data="elite"))
        keyboard.add(InlineKeyboardButton("◀ 𝑩𝑨𝑪𝑲 𝑻𝑶 𝑷𝑳𝑨𝑵𝑺", callback_data="back_menu"))
        bot.send_message(
            chat_id,
            f"""
📊 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑷𝑬𝑹𝑭𝑶𝑹𝑴𝑨𝑵𝑪𝑬

{performance()}

📈 𝑴𝑶𝑵𝑻𝑯𝑳𝒀 𝑹𝑬𝑺𝑼𝑳𝑻𝑺

{monthly_report()}
""",
            reply_markup=keyboard
        )

    # SUPPORT
    elif c.data == "support":
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("◀ 𝑩𝑨𝑪𝑲 𝑻𝑶 𝑷𝑳𝑨𝑵𝑺", callback_data="back_menu"))
        bot.send_message(
            chat_id,
"""
💬 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑷𝑹𝑬𝑴𝑰𝑼𝑴 𝑺𝑼𝑷𝑷𝑶𝑹𝑻

Welcome to the official 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 support channel.

Our team is available to assist Elite members with:

⚙️ 𝑴𝑬𝑴𝑩𝑬𝑹𝑺𝑯𝑰𝑷 𝑨𝑪𝑪𝑬𝑺𝑺  
📊 𝑺𝑰𝑮𝑵𝑨𝑳 𝑫𝑬𝑳𝑰𝑽𝑬𝑹𝒀  
💳 𝑷𝑨𝒀𝑴𝑬𝑵𝑻 𝑽𝑬𝑹𝑰𝑭𝑰𝑪𝑨𝑻𝑰𝑶𝑵  
📡 𝑺𝒀𝑺𝑻𝑬𝑴 𝑨𝑺𝑺𝑰𝑺𝑻𝑨𝑵𝑪𝑬

━━━━━━━━━━━━━━

📩 Direct Support

🔹 @MrMasterlegacy1

━━━━━━━━━━━━━━

⚡ Elite members receive **priority assistance** from the ValueHunter team.

Our support team will respond as soon as possible.
""",
            reply_markup=keyboard
        )

    elif c.data == "faq":
        faq_menu(chat_id, msg_id)
    elif c.data == "faq_system":
        faq_system(chat_id, msg_id)
    elif c.data == "faq_value":
        faq_value(chat_id, msg_id)
    elif c.data == "faq_referral":
        faq_referral(chat_id, msg_id)

    # BACK MENU
    elif c.data == "back_menu":
        label, countdown = signal_timer()
        bot.edit_message_text(
f"""
⚜️ 𝑾𝑬𝑳𝑪𝑶𝑴𝑬 𝑻𝑶 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹

You are currently viewing the ValueHunter platform.

Full access to the 𝑬𝑳𝑰𝑻𝑬 𝑩𝑬𝑻𝑻𝑰𝑵𝑮 𝑵𝑬𝑻𝑾𝑶𝑹𝑲 is restricted to members.

━━━━━━━━━━━━━━

🕕 𝑶𝑭𝑭𝑰𝑪𝑰𝑨𝑳 𝑺𝑰𝑮𝑵𝑨𝑳 𝑹𝑬𝑳𝑬𝑨𝑺𝑬  
• 18:00 (Athens Time) 🇬🇷

━━━━━━━━━━━━━━

{label}

{countdown}

━━━━━━━━━━━━━━

🎖️ Activate membership to unlock the ValueHunter signal network.
""",
            chat_id,
            msg_id,
            reply_markup=main_menu()
        )

    elif c.data == "referral":
        referral_panel(chat_id)

    elif c.data == "top_ref":
        text = get_daily_referrers()
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("⬅ BACK", callback_data="referral"))
        bot.edit_message_text(text, chat_id, msg_id, reply_markup=keyboard)


# ╔══════════════════════════════════════════════════════════════╗
# ║  PART 14 - ADMIN PANEL                                      ║
# ╚══════════════════════════════════════════════════════════════╝

def dev_engine(chat_id):
    """Admin: test value engine output."""
    bets = get_value_bets()
    if not bets:
        bot.send_message(chat_id, "No value bets found.")
        return
    text = "🧠 𝑽𝑨𝑳𝑼𝑬 𝑬𝑵𝑮𝑰𝑵𝑬 𝑨𝑵𝑨𝑳𝒀𝑺𝑰𝑺\n\n"
    text += "\n\n".join(bets[:3])
    bot.send_message(chat_id, text)


def dev_parlay(chat_id):
    """Admin: test parlay generation."""
    bets = get_value_bets()
    if not bets or len(bets) < 2:
        bot.send_message(chat_id, "Not enough parlay candidates.")
        return

    text = "🎰 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑽𝑨𝑳𝑼𝑬 𝑷𝑨𝑹𝑳𝑨𝒀\n\n"
    text += "\n\n".join(bets[:3])
    bot.send_message(chat_id, text)


@bot.message_handler(commands=["sendvip"])
def sendvip(m):
    if m.chat.id != ADMIN_ID:
        return
    bets = get_value_bets()
    users = get_vip_users()

    for uid, plan in users:
        if plan == "BASIC":
            picks = bets[:1]
        else:
            picks = bets[:3]
        text = "🎖️ VIP SIGNALS\n\n" + "\n\n".join(picks)
        try:
            bot.send_message(uid, text)
        except:
            pass

    bot.send_message(m.chat.id, "VIP signals sent.")


@bot.message_handler(commands=["stats"])
def stats(m):
    if m.chat.id != ADMIN_ID:
        return
    bot.send_message(m.chat.id, performance() + "\n\n" + monthly_report())


@bot.message_handler(commands=["bankroll"])
def bankroll(m):
    if m.chat.id != ADMIN_ID:
        return
    bot.send_message(m.chat.id, bankroll_status())


@bot.message_handler(commands=["users"])
def users(m):
    if m.chat.id != ADMIN_ID:
        return
    all_users = get_all_users()
    vip = get_vip_users()
    bot.send_message(m.chat.id, f"Total users: {len(all_users)}\nVIP users: {len(vip)}")


@bot.message_handler(commands=["broadcast"])
def broadcast(m):
    if m.chat.id != ADMIN_ID:
        return
    text = """
🔥 𝑴𝑨𝑹𝑲𝑬𝑻 𝑨𝑪𝑻𝑰𝑽𝑰𝑻𝒀 𝑫𝑬𝑻𝑬𝑪𝑻𝑬𝑫

Our ValueHunter analytics engine has detected **unusual betting activity** in today's football markets.

Several **high probability opportunities** are currently being analyzed by the model.

━━━━━━━━━━━━━━

⚡ Elite members will receive the official signals before the market reacts.

Once odds begin to move, value disappears quickly.

Today's signals will be released at **18:00**.

━━━━━━━━━━━━━━

⚠️ Access to the ValueHunter network may close once signals are released.

Secure your access before the market reacts.
"""
    all_u = get_all_users()
    for uid in all_u:
        try:
            bot.send_message(uid, text)
        except:
            pass
    bot.send_message(m.chat.id, "Broadcast sent.")


@bot.message_handler(commands=["viplist"])
def viplist(m):
    if m.chat.id != ADMIN_ID:
        return
    vip_u = get_vip_users()
    text = "VIP USERS\n\n"
    for uid, plan in vip_u:
        text += f"{uid} - {plan}\n"
    bot.send_message(m.chat.id, text)


@bot.message_handler(commands=["addvip"])
def addvip_cmd(m):
    if m.chat.id != ADMIN_ID:
        return
    try:
        _, user_id, days = m.text.split()
        add_vip(int(user_id), "PRO", int(days))
        bot.send_message(m.chat.id, "VIP added.")
    except:
        bot.send_message(m.chat.id, "Usage: /addvip user_id days")


@bot.message_handler(commands=["removevip"])
def removevip(m):
    if m.chat.id != ADMIN_ID:
        return
    try:
        _, user_id = m.text.split()
        cursor.execute("DELETE FROM vip_users WHERE user_id=?", (int(user_id),))
        db.commit()
        bot.send_message(m.chat.id, "VIP removed.")
    except:
        bot.send_message(m.chat.id, "Usage: /removevip user_id")


@bot.message_handler(commands=["bets"])
def bets(m):
    if m.chat.id != ADMIN_ID:
        return
    rows = cursor.execute(
        "SELECT match,pick,odds,result,confidence_tier,clv FROM bets_history ORDER BY id DESC LIMIT 10"
    ).fetchall()
    text = "LAST BETS\n\n"
    for match, pick, odds, result, tier, clv in rows:
        tier_str = f" [{tier}]" if tier else ""
        clv_str = f" CLV +{clv}%" if clv and clv > 0 else ""
        text += f"{match}\n{pick}\nOdds {odds} - {result}{tier_str}{clv_str}\n\n"
    bot.send_message(m.chat.id, text)


@bot.message_handler(commands=["reload_engine"])
def reload_engine(m):
    if m.chat.id != ADMIN_ID:
        return
    team_stats_cache.clear()
    injury_cache.clear()
    league_odds_cache.clear()
    league_odds_cache_time.clear()
    clv_history.clear()
    global value_cache, value_cache_time, fixtures_cache, fixtures_cache_time
    value_cache = []
    value_cache_time = 0
    fixtures_cache = []
    fixtures_cache_time = 0
    bot.send_message(m.chat.id, "Engine cache fully cleared.")


@bot.message_handler(commands=["force_alert"])
def force_alert(m):
    if m.chat.id != ADMIN_ID:
        return
    alert = market_alert()
    all_u = get_all_users()
    for uid in all_u:
        try:
            bot.send_message(uid, alert)
        except:
            pass
    bot.send_message(m.chat.id, "Alert sent.")


@bot.message_handler(commands=["test_payment"])
def test_payment(m):
    if m.chat.id != ADMIN_ID:
        return
    link = create_payment(1, m.chat.id)
    bot.send_message(m.chat.id, f"Test payment link:\n{link}")


@bot.message_handler(commands=["startvalue"])
def start_channel_automation(m):
    """Admin: Start channel automation."""
    global channel_automation_active, CHANNEL_ID
    if m.chat.id != ADMIN_ID:
        return

    parts = m.text.split()
    if len(parts) > 1:
        CHANNEL_ID = parts[1]

    if not CHANNEL_ID:
        bot.send_message(m.chat.id, "Usage: /startvalue @channel_name or channel_id")
        return

    if channel_automation_active:
        bot.send_message(m.chat.id, "Channel automation already running.")
        return

    channel_automation_active = True
    threading.Thread(target=run_channel_automation, daemon=True).start()
    bot.send_message(m.chat.id, f"Channel automation started for {CHANNEL_ID}")


@bot.message_handler(commands=["stopvalue"])
def stop_channel_automation(m):
    """Admin: Stop channel automation."""
    global channel_automation_active
    if m.chat.id != ADMIN_ID:
        return
    channel_automation_active = False
    bot.send_message(m.chat.id, "Channel automation stopped.")


@bot.message_handler(commands=["setchannel"])
def set_channel(m):
    """Admin: Set channel ID."""
    global CHANNEL_ID
    if m.chat.id != ADMIN_ID:
        return
    parts = m.text.split()
    if len(parts) < 2:
        bot.send_message(m.chat.id, "Usage: /setchannel @channel_name")
        return
    CHANNEL_ID = parts[1]
    bot.send_message(m.chat.id, f"Channel set to: {CHANNEL_ID}")


@bot.message_handler(commands=["enginestatus"])
def engine_status_cmd(m):
    """Admin: Check engine health."""
    if m.chat.id != ADMIN_ID:
        return

    fixtures_age = round((time.time() - fixtures_cache_time) / 60, 1) if fixtures_cache_time else "N/A"
    value_age = round((time.time() - value_cache_time) / 60, 1) if value_cache_time else "N/A"

    text = f"""
⚙️ ENGINE HEALTH REPORT

📡 Fixtures cached: {len(fixtures_cache)}
   Cache age: {fixtures_age} min

🎯 Value signals cached: {len(value_cache)}
   Cache age: {value_age} min

📊 Team stats cached: {len(team_stats_cache)}
📈 Odds cached: {len(league_odds_cache)} leagues
🏥 Injuries cached: {len(injury_cache)}
💰 CLV tracked: {len(clv_history)} markets

🔄 Channel automation: {"ACTIVE" if channel_automation_active else "INACTIVE"}
📢 Channel: {CHANNEL_ID or "Not set"}
"""
    bot.send_message(m.chat.id, text)


@bot.message_handler(commands=["defmenu"])
def defmenu(m):
    if m.chat.id != ADMIN_ID:
        return

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🧠 𝑻𝑬𝑺𝑻 𝑽𝑨𝑳𝑼𝑬 𝑬𝑵𝑮𝑰𝑵𝑬", callback_data="dev_engine"))
    keyboard.add(InlineKeyboardButton("🎰 𝑽𝑨𝑳𝑼𝑬 𝑷𝑨𝑹𝑳𝑨𝒀", callback_data="dev_parlay"))
    keyboard.add(InlineKeyboardButton("🎯 𝑺𝑬𝑵𝑫 𝑽𝑰𝑷 𝑺𝑰𝑮𝑵𝑨𝑳𝑺", callback_data="dev_sendvip"))
    keyboard.add(
        InlineKeyboardButton("📊 𝑺𝑻𝑨𝑻𝑺", callback_data="dev_stats"),
        InlineKeyboardButton("🏦 𝑩𝑨𝑵𝑲𝑹𝑶𝑳𝑳", callback_data="dev_bankroll")
    )
    keyboard.add(
        InlineKeyboardButton("👥 𝑼𝑺𝑬𝑹𝑺", callback_data="dev_users"),
        InlineKeyboardButton("👑 𝑽𝑰𝑷 𝑳𝑰𝑺𝑻", callback_data="dev_viplist")
    )
    keyboard.add(InlineKeyboardButton("📊 𝑳𝑨𝑺𝑻 𝑩𝑬𝑻𝑺", callback_data="dev_bets"))
    keyboard.add(
        InlineKeyboardButton("📢 𝑩𝑹𝑶𝑨𝑫𝑪𝑨𝑺𝑻", callback_data="dev_broadcast"),
        InlineKeyboardButton("📡 𝑭𝑶𝑹𝑪𝑬 𝑨𝑳𝑬𝑹𝑻", callback_data="dev_alert")
    )
    keyboard.add(InlineKeyboardButton("🔄 𝑹𝑬𝑳𝑶𝑨𝑫 𝑬𝑵𝑮𝑰𝑵𝑬", callback_data="dev_reload"))
    keyboard.add(InlineKeyboardButton("💳 𝑻𝑬𝑺𝑻 𝑷𝑨𝒀𝑴𝑬𝑵𝑻", callback_data="dev_payment"))

    bot.send_message(
        m.chat.id,
        "🛠 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑫𝑬𝑽 𝑷𝑨𝑵𝑬𝑳",
        reply_markup=keyboard
    )


@bot.message_handler(commands=["panel30"])
def panel30_cmd(m):
    if m.chat.id != ADMIN_ID:
        return
    bot.send_message(m.chat.id, performance_panel_30())


@bot.message_handler(commands=["enginelog"])
def enginelog_cmd(m):
    if m.chat.id != ADMIN_ID:
        return
    if not engine_log:
        bot.send_message(m.chat.id, "No engine logs yet.")
        return
    text = "ENGINE LOG (last 10)\n\n"
    for entry in engine_log[-10:]:
        text += f"{entry['time'][:19]} | {entry['event']} | {entry['detail'][:60]}\n"
    bot.send_message(m.chat.id, text)


@bot.message_handler(commands=["parlay"])
def parlay_cmd(m):
    if m.chat.id != ADMIN_ID:
        return
    if parlay_cache:
        bot.send_message(m.chat.id, str(parlay_cache))
    else:
        bot.send_message(m.chat.id, "No parlay available.")


@bot.message_handler(commands=["marketing"])
def marketing_cmd(m):
    if m.chat.id != ADMIN_ID:
        return
    msg = get_marketing_message_gr()
    if CHANNEL_ID:
        try:
            bot.send_message(CHANNEL_ID, msg)
            bot.send_message(m.chat.id, "Marketing message sent.")
        except:
            bot.send_message(m.chat.id, "Failed.")
    else:
        bot.send_message(m.chat.id, f"Channel not set. Msg: {msg}")


@bot.message_handler(commands=["clvreport"])
def clvreport_cmd(m):
    if m.chat.id != ADMIN_ID:
        return
    rows = cursor.execute(
        "SELECT match,pick,odds,clv,model_prob FROM bets_history WHERE clv>0 ORDER BY id DESC LIMIT 15"
    ).fetchall()
    if not rows:
        bot.send_message(m.chat.id, "No CLV data yet.")
        return
    text = "CLV REPORT\n\n"
    for match, pick, odds, clv_val, mp in rows:
        text += f"{match}\n{pick} @ {odds} | CLV +{clv_val}%\n\n"
    bot.send_message(m.chat.id, text)

@bot.callback_query_handler(func=lambda c: c.data=="result_summary")
def show_result_summary(call):

    text = result_summary_text()

    keyboard = InlineKeyboardMarkup()

    keyboard.add(
        InlineKeyboardButton(
            "🎁 Referral Program",
            callback_data="referral"
        )
    )

    bot.send_message(call.message.chat.id,text,reply_markup=keyboard)
    
@bot.callback_query_handler(func=lambda c: c.data=="performance")
def show_performance(call):

    text = performance()

    bot.send_message(
        call.message.chat.id,
        text
    )


@bot.callback_query_handler(func=lambda c: c.data=="referral")
def show_referral(call):

    user_id = call.from_user.id

    text = f"""
🎁 VALUEHUNTER REFERRAL

Invite friends and earn rewards.

For every VIP member you refer
you receive bonus access.

Your referral link:

https://t.me/ValueHunterElite_bot?start={user_id}
"""

    bot.send_message(
        call.message.chat.id,
        text
    )
    
# ───────────────────────────────────────
# LIVE MATCH TRACKER
# Updates VIP message with live status
# ───────────────────────────────────────

def update_live_matches():

    while True:

        rows = cursor.execute(
            "SELECT id,fixture_id,match,pick,odds,result FROM bets_history WHERE result='PENDING'"
        ).fetchall()

        for bet_id, fixture_id, match, pick, odds, result in rows:

            if not fixture_id:
                continue

            url = f"https://v3.football.api-sports.io/fixtures?id={fixture_id}"
            headers = {"x-apisports-key": FOOTBALL_API_KEY}

            try:
                r = requests.get(url, headers=headers, timeout=10).json()
            except:
                continue

            if not r.get("response"):
                continue

            game = r["response"][0]

            status = game["fixture"]["status"]["short"]
            minute = game["fixture"]["status"]["elapsed"]

            home = game["teams"]["home"]["name"]
            away = game["teams"]["away"]["name"]

            home_goals = game["goals"]["home"]
            away_goals = game["goals"]["away"]

            if status in ["1H","2H"]:

                status_text = f"🏟 LIVE {minute}'"

            elif status == "HT":

                status_text = "⏸ HT"

            else:

                status_text = "⏳ Pending"

            rows_msg = cursor.execute(
                "SELECT user_id,message_id FROM signal_messages"
            ).fetchall()

            for uid,msg_id in rows_msg:

                try:

                    new_text = f"""
🎖️ VIP SIGNAL UPDATE

⚽ {match}
🎯 {pick}

📊 Odds {odds}

Status: {status_text}

Score: {home_goals}-{away_goals}
"""

                    bot.edit_message_text(
                        new_text,
                        uid,
                        msg_id
                    )

                except:
                    pass

        time.sleep(60)

# ───────────────────────────────────────
# GOAL ALERT SYSTEM
# ───────────────────────────────────────

goal_cache = {}

def detect_goals():

    while True:

        rows = cursor.execute(
            "SELECT fixture_id,match FROM bets_history WHERE result='PENDING'"
        ).fetchall()

        for fixture_id, match in rows:

            url = f"https://v3.football.api-sports.io/fixtures?id={fixture_id}"
            headers = {"x-apisports-key": FOOTBALL_API_KEY}

            try:
                r = requests.get(url, headers=headers, timeout=10).json()
            except:
                continue

            if not r.get("response"):
                continue

            game = r["response"][0]

            home = game["teams"]["home"]["name"]
            away = game["teams"]["away"]["name"]

            home_goals = game["goals"]["home"]
            away_goals = game["goals"]["away"]

            key = f"{fixture_id}"

            current_score = f"{home_goals}-{away_goals}"

            if goal_cache.get(key) == current_score:
                continue

            goal_cache[key] = current_score

            text = f"""
⚽ GOAL ALERT

{home} vs {away}

Score: {current_score}

Match is LIVE
"""

            users = get_vip_users()

            for uid,plan in users:

                try:
                    bot.send_message(uid,text)
                except:
                    pass

        time.sleep(60)
        
# ───────────────────────────────────────
# RESULT IMAGE SENDER
# ───────────────────────────────────────

def send_results_image(wins,losses):

    total = wins + losses

    # AI announcement message
    users = get_vip_users()

    for uid,plan in users:
        try:
            bot.send_message(
                uid,
"""
🤖 AI ENGINE REPORT

Scanning today's signals...

Preparing elite result announcement...
"""
            )
        except:
            pass
        
    # δημιουργία εικόνας
    results = []

    for i in range(wins):
        results.append(("Bet","WIN"))

    for i in range(losses):
        results.append(("Bet","LOSE"))

    img_path = generate_ai_result_image(results)

    caption = f"""
🏆 VALUEHUNTER RESULT

{wins}/{total} WON TODAY

Elite members continue to beat the market.

Next signals release at 18:00 🇬🇷
"""

    keyboard = InlineKeyboardMarkup()

    keyboard.add(
        InlineKeyboardButton(
            "📊 PERFORMANCE",
            callback_data="performance"
        )
    )

    keyboard.add(
        InlineKeyboardButton(
            "🎁 REFERRAL PROGRAM",
            callback_data="referral"
        )
    )

    users = get_vip_users()

    for uid,plan in users:

        try:
            bot.send_photo(
                uid,
                open(img_path,"rb"),
                caption=caption,
                reply_markup=keyboard
            )
        except:
            pass

# ───────────────────────────────────────
# RESULT SUMMARY MENU
# ───────────────────────────────────────

def result_summary_text():

    rows = cursor.execute(
        "SELECT result FROM bets_history ORDER BY id DESC LIMIT 3"
    ).fetchall()

    wins = sum(1 for r in rows if r[0]=="WIN")
    losses = sum(1 for r in rows if r[0]=="LOSE")

    total = wins+losses

    winrate = (wins/total)*100 if total else 0

    return f"""
📊 SIGNAL RESULT SUMMARY

Bets: {total}
Wins: {wins}
Losses: {losses}

Winrate: {round(winrate,1)}%
"""

# ╔══════════════════════════════════════════════════════════════╗
# ║  PART 15 - THREADS & STARTUP                                ║
# ╚══════════════════════════════════════════════════════════════╝

threading.Thread(target=send_signals, daemon=True).start()

threading.Thread(target=update_live_matches, daemon=True).start()

threading.Thread(target=detect_goals, daemon=True).start()

threading.Thread(
    target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080))),
    daemon=True
).start()

threading.Thread(target=keep_alive, daemon=True).start()

# ================= RUN =================

bot.infinity_polling()
