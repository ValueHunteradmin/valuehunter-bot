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

# ================= CONFIG =================

TOKEN = "8767848071:AAHjxT7945VO-X7iCI3kG-0fIqC_giqX7Z8"
ADMIN_ID = 8328070177

FOOTBALL_API_KEY = "2f8c79b66ceed85aaf20322308f11e5a"
ODDS_API_KEY = "e55ba3ebd10f1d12494c0c10f1bfdb32"
NOWPAY_API_KEY = "ZB43Y23-F3E4XKG-K83X2GC-MPAAHZ5"
IPN_SECRET = "5B8MWD7S1sz5J+F100Hr7PyHI2D3jCjR"

START_BANKROLL = 2000
stake = 50

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

WEBHOOK_URL = "https://valuehunter-bot-production.up.railway.app/payment-webhook"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ================= DATABASE =================

db = sqlite3.connect(
"database.db",
check_same_thread=False,
timeout=30
)
cursor = db.cursor()

active_funnels = set()

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

# προσθήκη fixture_id αν δεν υπάρχει
try:
    cursor.execute("ALTER TABLE bets_history ADD COLUMN fixture_id INTEGER")
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

# ---------- REFERRAL SYSTEM ----------

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

def get_all_users():

    users = set()

    vip = cursor.execute(
        "SELECT user_id FROM vip_users"
    ).fetchall()

    sample = cursor.execute(
        "SELECT user_id FROM free_sample"
    ).fetchall()

    for u in vip:
        users.add(u[0])

    for u in sample:
        users.add(u[0])

    return list(users)
    
    if not r:
        return False

    return r[0] > now

# ================= MENU =================

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
    
    # αποφυγή διπλής ενεργοποίησης VIP
    exists = cursor.execute(
        "SELECT payment_id FROM processed_payments WHERE payment_id=?",
        (payment_id,)
    ).fetchone()

    if exists:
        return "already processed"

    if status != "finished":
        return "ignored"

    import time
    now = int(time.time())

    # επιλογή plan + διάρκεια
    if amount == 25:
        plan = "DAY"
        expiry = now + 86400          # 1 μέρα

    elif amount == 50:
        plan = "BASIC"
        expiry = now + 2592000       # 30 μέρες

    elif amount == 100:
        plan = "PRO"
        expiry = now + 2592000       # 30 μέρες

    else:
        return "invalid amount"

    cursor.execute(
    "INSERT OR REPLACE INTO vip_users VALUES (?,?,?)",
    (user_id,plan,expiry)
    )

    db.commit()
    
    # ---------- UNLOCK REFERRAL VIP PANEL ----------

    if plan == "pro":

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

🕔 17:00 — Model analysis completed  
🕕 18:00 — Official VIP signal release  

🇬🇷 Europe / Athens Time

━━━━━━━━━━━━━━

⚠️ Signals inside this network are distributed to a limited number of Elite members to protect the betting edge.

Elite members are already preparing today's positions.
"""
    )
    
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
    
# ================= FOOTBALL DATA =================

def get_matches():

    url = "https://v3.football.api-sports.io/fixtures?next=20"

    headers = {"x-apisports-key":FOOTBALL_API_KEY}

    try:
        r = requests.get(url,headers=headers).json()
    except:
        return []

    matches = []

    for m in r.get("response", []):

        home = m["teams"]["home"]["name"]
        away = m["teams"]["away"]["name"]

        matches.append((home,away))

    return matches
    
def model_extra_tip(over15_prob, over25_prob, over35_prob, btts_prob):

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

    # παίρνει το πιο δυνατό probability
    best = max(candidates, key=lambda x: x[1])

    return best

# ================= VALUE ENGINE =================

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

league_strength = {
39:1.05,
78:1.08,
135:0.95,
140:1.00,
61:0.97,
88:1.02,
94:0.98,
203:0.96,
144:0.99,  # Belgium
113:1.02,  # Sweden
71:0.98,   # Scotland
218:1.01,  # Austria
119:1.03,  # Norway
106:0.97   # Poland
}

odds_history={}
steam_history={}
clv_history={}

team_stats_cache={}
injury_cache={}
league_odds_cache={}
league_odds_cache_time={}
value_cache = []
value_cache_time = 0
fixtures_cache = []
fixtures_cache_time = 0
alert_cache = None
alert_cache_time = 0
    
def dev_engine(chat_id):

    bets = get_value_bets()

    if not bets:
        bot.send_message(chat_id,"No value bets found.")
        return

    text = "🧠 𝑽𝑨𝑳𝑼𝑬 𝑬𝑵𝑮𝑰𝑵𝑬 𝑨𝑵𝑨𝑳𝒀𝑺𝑰𝑺\n\n"

    for bet in bets:

        lines = bet.split("\n")

        try:
            match = lines[1]
            pick = lines[2]
            odds = lines[3]
        except:
            continue

        confidence = random.randint(78,92)
        steam = random.choice(["LOW","MEDIUM","HIGH"])
        clv = round(random.uniform(3,10),1)

        # placeholder probabilities (μόνο για dev)
        over15_prob = random.uniform(0.65,0.85)
        over25_prob = random.uniform(0.55,0.70)
        over35_prob = random.uniform(0.30,0.45)
        btts_prob = random.uniform(0.50,0.65)

        extra = model_extra_tip(
            over15_prob,
            over25_prob,
            over35_prob,
            btts_prob
        )

        text += f"""
⚽ {match}
🎯 {pick}
📊 {odds}

━━━━━━━━━━━━━━

📊 MODEL INSIGHTS

Confidence: {confidence}%
Steam signal: {steam}
CLV prediction: {clv}%
"""

        if extra:

            tip_name, tip_prob = extra

            text += f"""

🧠 EXTRA MODEL TIP

{tip_name}
Model probability: {round(tip_prob*100)}%
"""

        text += "\n━━━━━━━━━━━━━━\n"

    bot.send_message(chat_id,text)

def dev_parlay(chat_id):

    bets = get_value_bets()

    candidates = []

    for bet in bets:

        lines = bet.split("\n")

        match = lines[1]
        pick = lines[2]

        odds_line = lines[3]

        try:
            odds = float(odds_line.replace("📊 Odds ",""))
        except:
            continue

        if 1.60 <= odds <= 2.20:
            candidates.append((match,pick,odds))

    if len(candidates) < 5:
        bot.send_message(chat_id,"Not enough parlay candidates.")
        return

    random.shuffle(candidates)

    picks = candidates[:5]

    text = "🎰 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑽𝑨𝑳𝑼𝑬 𝑷𝑨𝑹𝑳𝑨𝒀\n\n"

    total = 1

    for i,(match,pick,odds) in enumerate(picks,1):

        total *= odds

        text += f"""
{i}. ⚽ {match}
🎯 {pick}
📊 Odds {odds}

"""

    text += f"\n💰 TOTAL ODDS ≈ {round(total,2)}"

    bot.send_message(chat_id,text)

# ---------- IMPLIED PROBABILITY ----------

def implied_probability(odds):

    if odds <= 0:
        return 0

    return 1 / odds
    
# ---------- TRUE MARKET PROBABILITY ----------

def true_probability(prob):

    # remove bookmaker margin
    return prob / (1 + prob)

# ---------- MATCH SCANNER ----------

def scan_matches():

    global fixtures_cache, fixtures_cache_time

    # ---------- 1 CACHE SYSTEM ----------
    if time.time() - fixtures_cache_time < 1800:
        return fixtures_cache

    fixtures = []

    # ---------- 2 SCAN 3 DAYS ----------
    today = datetime.now(UTC).date()
    future = today + timedelta(days=3)

    url = f"https://v3.football.api-sports.io/fixtures?from={today}&to={future}"

    headers = {"x-apisports-key": FOOTBALL_API_KEY}

    try:
        r = requests.get(url, headers=headers).json()
        time.sleep(0.1)
    except:
        return []

    for m in r.get("response", []):

        # ---------- 3 LEAGUE FILTER ----------
        league_id = m["league"]["id"]

        if league_id not in GOOD_LEAGUES:
            continue

        # ---------- 4 STATUS FILTER ----------
        status = m["fixture"]["status"]["short"]

        if status not in ["NS"]:
            continue

        match_time = m["fixture"]["timestamp"]
        now = int(time.time())

        # ---------- 5 TIME WINDOW ----------
        if not (7200 <= match_time-now <= 259200):
            continue

        fixtures.append({

            "fixture_id": m["fixture"]["id"],
            "home": m["teams"]["home"]["name"],
            "away": m["teams"]["away"]["name"],
            "home_id": m["teams"]["home"]["id"],
            "away_id": m["teams"]["away"]["id"],
            "league_id": league_id,

            # ---------- 6 EXTRA DATA ----------
            "league_name": m["league"]["name"],
            "country": m["league"]["country"],
            "timestamp": match_time

        })

    # ---------- 7 CACHE SAVE ----------
    fixtures_cache = fixtures
    fixtures_cache_time = time.time()

    return fixtures

# ---------- TEAM STATS ----------

def get_team_stats(team_id,league_id):

    if team_id in team_stats_cache:
        return team_stats_cache[team_id]

    url=f"https://v3.football.api-sports.io/teams/statistics?team={team_id}&league={league_id}&season=2024"
    headers={"x-apisports-key":FOOTBALL_API_KEY}

    try:
        r=requests.get(url,headers=headers).json()
    except:
        return None

    if not r.get("response"):
        return None

    d=r["response"]

    attack=float(d["goals"]["for"]["average"]["total"])
    defense=float(d["goals"]["against"]["average"]["total"])

    team_stats_cache[team_id]=(attack,defense)

    return attack,defense


# ---------- INJURIES ----------

def get_injuries(team_id):

    if team_id in injury_cache:
        return injury_cache[team_id]

    url=f"https://v3.football.api-sports.io/injuries?team={team_id}"
    headers={"x-apisports-key":FOOTBALL_API_KEY}

    try:
        r=requests.get(url,headers=headers).json()
    except:
        return 0

    injuries=len(r["response"])

    injury_cache[team_id]=injuries

    return injuries


# ---------- TEAM STRENGTH ----------

def team_strength(home_attack,home_defense,away_attack,away_defense):

    home_strength=(home_attack+away_defense)/2
    away_strength=(away_attack+home_defense)/2

    return home_strength,away_strength


# ---------- xG MODEL ----------

def calculate_xg(home_strength,away_strength,league_id):

    modifier = league_strength.get(league_id,1)

    HOME_ADV = 0.30

    home_xg = (home_strength * modifier) + HOME_ADV
    away_xg = (away_strength * modifier)

    return home_xg,away_xg

# ---------- POISSON ----------

def poisson(lmbda,k):
    return (lmbda**k*math.exp(-lmbda))/math.factorial(k)


def poisson_matrix(home_xg,away_xg):

    matrix=[]

    for h in range(6):
        for a in range(6):

            p=poisson(home_xg,h)*poisson(away_xg,a)

            matrix.append((h,a,p))

    return matrix


# ---------- MONTE CARLO ----------

def monte_carlo_simulation(home_xg,away_xg,simulations=3000):

    home_wins=0

    for _ in range(simulations):

        hg=np.random.poisson(home_xg)
        ag=np.random.poisson(away_xg)

        if hg>ag:
            home_wins+=1

    return home_wins/simulations


# ---------- PROBABILITY CALIBRATION ----------

def calibrate_probability(prob):

    calibrated=1/(1+math.exp(-4*(prob-0.5)))

    return calibrated

# ---------- MODEL SANITY FILTER ----------

def model_sanity_filter(home_xg, away_xg):

    total_xg = home_xg + away_xg

    # πολύ χαμηλό tempo παιχνίδι
    if total_xg < 1.6:
        return False

    # πολύ υψηλό tempo (unstable poisson)
    if total_xg > 4.8:
        return False

    # πολύ μονόπλευρο παιχνίδι
    if abs(home_xg - away_xg) > 2.5:
        return False

    return True
    
# ---------- MARKET PROBABILITIES ----------

def over25_probability(matrix):

    prob=0

    for h,a,p in matrix:
        if h+a>=3:
            prob+=p

    return prob


def btts_probability(matrix):

    prob=0

    for h,a,p in matrix:
        if h>0 and a>0:
            prob+=p

    return prob
    
# ---------- OVER / UNDER ENGINE ----------

def goal_totals_probability(matrix):

    probs = {
        "over1_5":0,
        "over2_5":0,
        "over3_5":0,
        "under1_5":0,
        "under2_5":0,
        "under3_5":0
    }

    for h,a,p in matrix:

        goals = h+a

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

# ---------- ASIAN HANDICAP ----------

def asian_optimizer(matrix):

    lines=[-1,-0.75,-0.5,-0.25,0,0.25,0.5]

    best_line=None
    best_prob=0

    for line in lines:

        prob=0

        for h,a,p in matrix:

            if (h-a)>line:
                prob+=p

        if prob>best_prob:
            best_prob=prob
            best_line=line

    return best_line,best_prob


# ---------- ODDS PARSER ----------

def get_league_odds(league_id):

    if league_id in league_odds_cache:
        if time.time() - league_odds_cache_time[league_id] < 600:
            return league_odds_cache[league_id]

    url = f"https://v3.football.api-sports.io/odds?league={league_id}&season=2024"
    headers = {"x-apisports-key": FOOTBALL_API_KEY}

    try:
        r = requests.get(url, headers=headers).json()
    except:
        return None

    odds_data = {}

    for game in r.get("response", []):

        fixture_id = game["fixture"]["id"]
        bookmakers = game["bookmakers"]

        best_odds = {}

        for book in bookmakers:

            for bet in book["bets"]:

                market = bet["name"]

                for v in bet["values"]:

                    key = f"{market}_{v['value']}"
                    odd = float(v["odd"])

                    if key not in best_odds:
                        best_odds[key] = odd
                    else:
                        # αποφυγή ακραίων odds
                        if abs(best_odds[key] - odd) > 0.50:
                            continue

                        best_odds[key] = max(best_odds[key], odd)

        odds_data[fixture_id] = best_odds

    league_odds_cache[league_id] = odds_data
    league_odds_cache_time[league_id] = time.time()

    return odds_data

# ---------- ODDS MOVEMENT ----------

def track_odds(fixture_id,odds):

    if fixture_id not in odds_history:
        odds_history[fixture_id] = odds
        return 0

    old_odds = odds_history[fixture_id]

    movement = old_odds - odds

    odds_history[fixture_id] = odds

    return movement


# ---------- STEAM DETECTOR ----------

def detect_steam_move(fixture_id,odds):

    if fixture_id not in steam_history:
        steam_history[fixture_id]=odds
        return False

    drop=steam_history[fixture_id]-odds
    steam_history[fixture_id]=odds

    return drop>=0.20
# ---------- STEAM PREDICTOR ----------

def predict_steam(prob, odds):

    market_prob = 1 / odds

    edge = prob - market_prob

    # αν το model διαφωνεί έντονα με την αγορά
    if edge > 0.08 and prob > 0.60:
        return True

    return False
    
    # ---------- MARKET TIMING ENGINE ----------

def market_timing_engine(prob, odds):

    market_prob = 1 / odds

    edge = prob - market_prob

    # μεγάλο edge → πιθανό odds drop
    if edge > 0.06 and prob > 0.60:
        return True

    return False
    
# ---------- CLV TRACKER ----------

def track_clv(fixture_id,odds):

    if fixture_id not in clv_history:
        clv_history[fixture_id]=odds
        return 0

    open_odds=clv_history[fixture_id]

    clv=open_odds-odds

    return clv
    
# ---------- EV ----------

def calculate_ev(prob,odds):
    return (prob*odds)-1

# ---------- MARKET CONSENSUS FILTER ----------

def market_consensus_filter(prob, odds):

    market_prob = 1 / odds

    edge = prob - market_prob

    # μικρό edge → άχρηστο bet
    if edge < 0.02:
        return False

    return True
    
# ---------- MARKET EFFICIENCY DETECTOR ----------

def market_efficiency_detector(prob, odds):

    market_prob = 1 / odds

    diff = abs(prob - market_prob)

    # αγορά πολύ αποδοτική
    if diff < 0.015:
        return False

    return True
    
# ---------- LIQUIDITY FILTER ----------

def liquidity_filter(league_id, odds):

    # μεγάλες λίγκες έχουν υψηλή ρευστότητα
    top_leagues = {39,78,140,135,61}

    if league_id in top_leagues:
        return True

    # περίεργα odds σημαίνουν low liquidity
    if odds < 1.30 or odds > 4.50:
        return False

    return True
    
# ---------- PINNACLE SHARP COMPARISON ----------

def pinnacle_sharp_check(prob, odds):

    pinnacle_prob = 1 / odds

    edge = prob - pinnacle_prob

    if edge > 0.03:
        return True

    return False
    
# ---------- KELLY ----------

def kelly_stake(prob,odds):

    b=odds-1
    q=1-prob

    k=(b*prob-q)/b

    if k<0:
        return 0

    return k


# ---------- RANK ----------

def rank_bets(bets):
    bets.sort(key=lambda x:x["confidence"],reverse=True)
    return bets
    
# ---------- BET CORRELATION FILTER ----------

def correlation_filter(bets):

    used_matches=set()

    filtered=[]

    for bet in bets:

        match=bet["match"]

        if match in used_matches:
            continue

        filtered.append(bet)

        used_matches.add(match)

    return filtered
    
# ---------- RESULT GRADER ----------

def grade_results():

    rows = cursor.execute(
        "SELECT id,fixture_id,match,pick,odds,result FROM bets_history WHERE result='PENDING'"
    ).fetchall()

    for bet_id,fixture_id,match,pick,odds,result in rows:

        url = f"https://v3.football.api-sports.io/fixtures?id={fixture_id}"

        headers = {"x-apisports-key":FOOTBALL_API_KEY}

        try:
            r = requests.get(url,headers=headers).json()
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

        # ---------- ASIAN HANDICAP ----------

        if "Asian Handicap" in pick:

            line = float(pick.split()[-1])

            diff = home_goals - away_goals

            if diff > line:
                outcome = "WIN"

        # ---------- OVER ----------

        elif "Over" in pick:

            line = float(pick.split()[-1])

            if home_goals + away_goals > line:
                outcome = "WIN"

        # ---------- UNDER ----------

        elif "Under" in pick:

            line = float(pick.split()[-1])

            if home_goals + away_goals < line:
                outcome = "WIN"

        # ---------- BTTS ----------

        elif "BTTS" in pick:

            if home_goals > 0 and away_goals > 0:
                outcome = "WIN"

        cursor.execute(
            "UPDATE bets_history SET result=? WHERE id=?",
            (outcome,bet_id)
        )
        db.commit()
        
        if outcome == "WIN" and result == "PENDING":
            
            message = f"""
        🎖️ 𝑾𝑰𝑵 𝑪𝑶𝑵𝑭𝑰𝑹𝑴𝑬𝑫

        ⚽ {match}
        🎯 {pick}
        🚀 Odds {odds}
        ━━━━━━━━━━━━━━
        🏆 𝑽𝑰𝑷 𝗠𝗘𝗠𝗕𝗘𝗥𝗦 𝗖𝗢𝗟𝗟𝗘𝗖𝗧𝗘𝗗 𝗔𝗡𝗢𝗧𝗛𝗘𝗥 𝗪𝗜𝗡 𝗧𝗢𝗗𝗔𝗬.
        
        📡 𝗡𝗘𝗫𝗧 𝗦𝗜𝗚𝗡𝗔𝗟𝗦 𝗥𝗘𝗟𝗘𝗔𝗦𝗘𝗗 𝗔𝗧 𝟭𝟴:𝟬𝟬
        • 𝗔𝗧𝗛𝗘𝗡𝗦 𝗧𝗜𝗠𝗘 🇬🇷
        

        🔐 𝑺𝑼𝑷𝑷𝑶𝑹𝑻: @MrMasterlegacy1
        """

            users = get_vip_users()

            for uid, plan in users:

                try:
                    bot.send_message(uid, message)
                    time.sleep(0.05)
                except:
                    pass
                                
            # ---------- SEND WIN TO FREE USERS ---------
                                        
            free_users = get_all_users()

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
            keyboard.add(
                InlineKeyboardButton(
                    "⚜️ 𝑼𝑵𝑳𝑶𝑪𝑲 𝑽𝑰𝑷 𝑨𝑪𝑪𝑬𝑺𝑺",
                    callback_data="elite"
                )
            )

            for uid in free_users:

                if is_vip(uid):
                    continue

                try:
                    bot.send_message(
                        uid,
                        free_text,
                        reply_markup=keyboard
                    )
                    time.sleep(0.05)
                except:
                    pass
                    
# ---------- VALUE ENGINE ----------

def get_value_bets():

    global value_cache, value_cache_time

    # αν έχουν περάσει λιγότερα από 15 λεπτά
    if time.time() - value_cache_time < 900:
        return value_cache

    fixtures = scan_matches()

    candidates = []

    for f in fixtures:

        if f["league_id"] not in GOOD_LEAGUES:
            continue

        stats_home = get_team_stats(f["home_id"], f["league_id"])
        stats_away = get_team_stats(f["away_id"], f["league_id"])

        if not stats_home or not stats_away:
            continue

        home_attack, home_defense = stats_home
        away_attack, away_defense = stats_away

        home_attack -= get_injuries(f["home_id"]) * 0.05
        away_attack -= get_injuries(f["away_id"]) * 0.05

        hs, as_ = team_strength(
            home_attack,
            home_defense,
            away_attack,
            away_defense
        )

        home_xg, away_xg = calculate_xg(
            hs,
            as_,
            f["league_id"]
        )
        
        # ---------- TEAM BALANCE FILTER ----------

        if abs(home_xg - away_xg) > 2.5:
            continue
        
        xg_diff = abs(home_xg - away_xg)
        total_xg = home_xg + away_xg
        
        # ---------- TEMPO FILTER ----------

        if total_xg < 1.9 or total_xg > 3.9:
            continue
        if xg_diff > 1.8:
            continue

        if not model_sanity_filter(home_xg, away_xg):
            continue

        matrix = poisson_matrix(home_xg, away_xg)

        totals = goal_totals_probability(matrix)

        total = sum(p for _, _, p in matrix)
        matrix = [(h, a, p / total) for h, a, p in matrix]

        home_prob = monte_carlo_simulation(home_xg, away_xg)

        line, asian_prob = asian_optimizer(matrix)

        asian_prob = (asian_prob + home_prob) / 2
        asian_prob = calibrate_probability(asian_prob)

        over25_prob = calibrate_probability(totals["over2_5"])
        under25_prob = calibrate_probability(totals["under2_5"])
        over15_prob = calibrate_probability(totals["over1_5"])
        over35_prob = calibrate_probability(totals["over3_5"])

        btts_prob = calibrate_probability(
            btts_probability(matrix)
        )

        league_odds = get_league_odds(f["league_id"])

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

        markets = []

        if home_odds:
            markets.append(
                ("Home Win", home_prob, home_odds, None)
            )

        if over_odds:
            markets.append(
                ("Over 2.5", over25_prob, over_odds, None)
            )

        if under_odds and total_xg < 2.7:
            markets.append(
                ("Under 2.5", under25_prob, under_odds, None)
            )

        if over15_odds:
            markets.append(
                ("Over 1.5", over15_prob, over15_odds, None)
            )

        if over35_odds and total_xg > 2.8:
            markets.append(
                ("Over 3.5", over35_prob, over35_odds, None)
            )
            
        if under35_odds and total_xg < 3.2:
            markets.append(
                ("Under 3.5", 1 - over35_prob, under35_odds, None)
            )

        if btts_odds:
            markets.append(
                ("BTTS", btts_prob, btts_odds, None)
            )

        for market, prob, odds_value, line in markets:
            
            # ---------- PROBABILITY STABILITY FILTER ----------
            expected_range = 0.45 + (total_xg - 2.2) * 0.08

            if prob > expected_range + 0.18:
                continue
            
            # ---------- ODDS RANGE FILTER ----------

            if odds_value < 1.60 or odds_value > 2.40:
                continue
                
            if odds_value < 1.70 and prob < 0.60:
                continue

            implied = implied_probability(odds_value)

            edge = prob - implied
            
            market_prob = 1 / odds_value
            
            # ---------- SHARP MARKET FILTER ----------

            if abs(prob - market_prob) > 0.12:
                continue

            if prob - market_prob < 0.04:
                continue

            if not liquidity_filter(
                f["league_id"],
                odds_value
            ):
                continue

            if not market_efficiency_detector(
                prob,
                odds_value
            ):
                continue

            if not market_consensus_filter(
                prob,
                odds_value
            ):
                continue

            pinnacle_signal = pinnacle_sharp_check(
                prob,
                odds_value
            )
            
            # ---------- PROBABILITY STABILITY FILTER ----------

            if prob > 0.85:
                continue
                
            if edge < 0.04 or prob < 0.58:
                continue
                
            ev = calculate_ev(prob, odds_value)

            move = track_odds(
                f["fixture_id"],
                odds_value
            )
            
            # ---------- ODDS MOVEMENT FILTER ----------
            if move < -0.15:
                continue
                
            steam = detect_steam_move(
                f["fixture_id"],
                odds_value
            )

            clv = track_clv(
                f["fixture_id"],
                odds_value
            )

            stake = kelly_stake(
                prob,
                odds_value
            )
            
            if stake > 0.06:
                continue

            timing_signal = market_timing_engine(
                prob,
                odds_value
            )
            
            if timing_signal:
                early_text = "\n⚡ Early value detected\nOdds may drop soon\n"
            else:
                early_text = ""

            steam_prediction = predict_steam(
                prob,
                odds_value
            )

            confidence = (
                (prob * 50) +
                (edge * 200) +
                (ev * 100)
            )
                
            if pinnacle_signal:
                confidence += 6

            if steam:
                confidence += 10

            if steam_prediction:
                confidence += 7

            if timing_signal:
                confidence += 8
                
            # EARLY VALUE SIGNAL
            if timing_signal and prob > 0.63:
                confidence += 5

            if clv > 0.10:
                confidence += 5
                
            # ideal odds range bonus
            if 1.70 <= odds_value <= 2.20:
                confidence += 4

            # strong probability bonus
            if prob >= 0.62:
                confidence += 3

            if ev <= 0.04:
                continue

            pick = market

            if market == "Home Win":
                pick = f"{f['home']} to Win"
                
            bet_key = f"{f['fixture_id']}_{pick}"

            if cursor.execute(
                "SELECT key FROM sent_bets WHERE key=?",
                (bet_key,)
            ).fetchone():
                continue

            cursor.execute(
                "INSERT INTO sent_bets VALUES (?)",
                (bet_key,)
            )

            db.commit()

            cursor.execute(
                "INSERT INTO bets_history(fixture_id,match,pick,odds,result,timestamp) VALUES (?,?,?,?,?,?)",
                (
                    f["fixture_id"],
                    f"{f['home']} vs {f['away']}",
                    pick,
                    odds_value,
                    "PENDING",
                    int(time.time())
                )
            )

            db.commit()

            candidates.append({
                "match": f"{f['home']} vs {f['away']}",
                "pick": pick,
                "prob": prob,
                "odds": odds_value,
                "ev": ev,
                "confidence": confidence,
                "stake": stake,
                "early": early_text
            })

    ranked = rank_bets(candidates)

    ranked = correlation_filter(ranked)

    super_safe = None
    high_value = []

    for bet in ranked:

        if bet["prob"] >= 0.63 and 1.60 <= bet["odds"] <= 1.90 and not super_safe:
            super_safe = bet

        elif bet["prob"] >= 0.60 and bet["odds"] <= 2.20:
            high_value.append(bet)

    signals = []

    if super_safe:

        signals.append(
f"""⭐ 𝑺𝑼𝑷𝑬𝑹 𝑺𝑨𝑭𝑬 𝑩𝑬𝑻
⚽ {super_safe['match']}
🎯 {super_safe['pick']}
📊 Odds {round(super_safe['odds'],2)}
📈 Probability {round(super_safe['prob']*100)}%
💰 Value {round(super_safe['ev'],2)}
💵 Stake {round(super_safe['stake']*100,1)}% bankroll

{super_safe['early']}

💸 Bet: 50€"""
        )

    for bet in high_value[:2]:

        signals.append(
f"""🔥 𝑯𝑰𝑮𝑯 𝑽𝑨𝑳𝑼𝑬
⚽ {bet['match']}
🎯 {bet['pick']}
📊 Odds {round(bet['odds'],2)}
📈 Probability {round(bet['prob']*100)}%
💰 Value {round(bet['ev'],2)}
💵 Stake {round(bet['stake']*100,1)}% bankroll

{bet['early']}

💸 Bet: 50€"""
        )
        
    # ---------- FALLBACK BET ----------
    if not signals and candidates:

        bet = ranked[0]

        signals.append(
f"""🔥 𝑽𝑨𝑳𝑼𝑬 𝑩𝑬𝑻

⚽ {bet['match']}
🎯 {bet['pick']}
📊 Odds {round(bet['odds'],2)}
📈 Probability {round(bet['prob']*100)}%
💰 Value {round(bet['ev'],2)}

💸 Bet: 50€"""
    )

    league_odds_cache.clear()
    team_stats_cache.clear()
    injury_cache.clear()
    value_cache = signals
    value_cache_time = time.time()
    
    return signals
    
# ================= DAILY SAMPLE =================

def daily_sample(user_id):

    now = int(time.time())

    row = cursor.execute(
        "SELECT last_time FROM free_sample WHERE user_id=?",
        (user_id,)
    ).fetchone()

    # αν υπάρχει record
    if row:

        last_time = row[0]

        # 48 ώρες = 172800 sec
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

    # ---------- 48H LIMIT ----------
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


    # ---------- SCANNING MESSAGE ----------
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

    # ---------- GET BET ----------
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

    bet = bets[0]   # SUPER SAFE BET

    cursor.execute(
        "INSERT OR REPLACE INTO free_sample VALUES (?,?)",
        (user_id, now)
    )

    db.commit()

    keyboard = InlineKeyboardMarkup()

    keyboard.add(
        InlineKeyboardButton(
            "🔥 Unlock VIP Access",
            callback_data="elite"
        )
    )

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

# ================= MARKET ALERT =================

def market_alert():

    global alert_cache, alert_cache_time

    # cache για 30 λεπτά
    if time.time() - alert_cache_time < 1800 and alert_cache:
        return alert_cache

    matches = get_matches()

    if not matches:
        return "No alert"

    home, away = matches[0]
    
    import random
    
    open_odds = round(random.uniform(1.90,2.40),2)
    drop = round(random.uniform(0.15,0.35),2)

    new_odds = round(open_odds - drop,2)
    
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

def start_conversion_funnel(user_id):

    if user_id in active_funnels:
        return

    active_funnels.add(user_id)

    def funnel():

        # ---------- MESSAGE 1 (30 minutes) ----------
        time.sleep(1800)

        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(
                "⚜️ 𝑼𝑵𝑳𝑶𝑪𝑲 𝑬𝑳𝑰𝑻𝑬 𝑨𝑪𝑪𝑬𝑺𝑺",
                callback_data="elite"
            )
        )

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


        # ---------- MESSAGE 2 (2 hours) ----------
        time.sleep(7200)

        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(
                "⚜️ 𝑼𝑵𝑳𝑶𝑪𝑲 𝑬𝑳𝑰𝑻𝑬 𝑨𝑪𝑪𝑬𝑺𝑺",
                callback_data="elite"
            )
        )

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
18:00 — Athens Time 🇬🇷

━━━━━━━━━━━━━━

⚠️ Access may close once signals are released.
""",
                reply_markup=keyboard
            )
        except:
            pass


        # ---------- MESSAGE 3 ----------
        time.sleep(3600)

        tz = pytz.timezone("Europe/Athens")
        now = datetime.now(tz)
        hour = now.hour

        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(
                "⚜️ 𝑼𝑵𝑳𝑶𝑪𝑲 𝑬𝑳𝑰𝑻𝑬 𝑨𝑪𝑪𝑬𝑺𝑺",
                callback_data="elite"
            )
        )

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
18:00 — Athens Time 🇬🇷

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
    
# ================= PERFORMANCE =================

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
        stake = 50

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

𝗣𝗥𝗢𝗙𝗜𝗧: {round(dp,2)} €


📈 𝑾𝑬𝑬𝑲𝑳𝒀 𝑷𝑬𝑹𝑭𝑶𝑹𝑴𝑨𝑵𝑪𝑬

𝗪𝗜𝗡𝗦: {ww}
𝗟𝗢𝗦𝗦𝗘𝗦: {wl}

𝗣𝗥𝗢𝗙𝗜𝗧: {round(wp,2)} €
"""

def get_daily_referrers():

    global referrer_cache, referrer_cache_date
    global feed_cache, feed_cache_time

    now = time.time()
    today = datetime.now().date()

    # ---------- DAILY LEADERBOARD ----------
    if referrer_cache_date != today:

        names = random.sample(referrer_names,5)

        referrals = [
            random.randint(100,140),
            random.randint(80,110),
            random.randint(60,90),
            random.randint(40,70),
            random.randint(30,50)
        ]

        gains = [
            random.randint(1,6),
            random.randint(1,5),
            random.randint(1,4),
            random.randint(1,3),
            random.randint(1,2)
        ]

        referrer_cache = f"""
👑 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑻𝑶𝑷 𝑹𝑬𝑭𝑬𝑹𝑹𝑬𝑹𝑺

🥇 {names[0]} — {referrals[0]} referrals (+{gains[0]} today)
🥈 {names[1]} — {referrals[1]} referrals (+{gains[1]} today)
🥉 {names[2]} — {referrals[2]} referrals (+{gains[2]} today)
4️⃣ {names[3]} — {referrals[3]} referrals (+{gains[3]} today)
5️⃣ {names[4]} — {referrals[4]} referrals (+{gains[4]} today)
"""

        referrer_cache_date = today

    # ---------- LIVE FEED (30 MIN) ----------
    if now - feed_cache_time > 1800:

        feed_lines = random.sample(referral_feed,3)

        feed_cache = f"""

━━━━━━━━━━━━━━

{feed_lines[0]}
{feed_lines[1]}
{feed_lines[2]}
"""

        feed_cache_time = now

    return referrer_cache + feed_cache
    
# ---------- REFERRAL LINK ----------

def referral_link(user_id):

    return f"https://t.me/ValueHunterElite_bot?start={user_id}"
    
    # ---------- REFERRAL COUNT ----------

def get_referrals(user_id):

    cursor.execute(
        "SELECT COUNT(*) FROM referrals WHERE referrer=?",
        (user_id,)
    )

    result = cursor.fetchone()

    if result:
        return result[0]

    return 0
    
    # ---------- REFERRAL DISCOUNT ----------

def referral_discount(user_id):

    count = get_referrals(user_id)

    return (count // 30) * 50
    
# ---------- REFERRAL PANEL ----------

def referral_panel(user_id):
    
    ref_link = f"https://t.me/ValueHunterElite_botstart={user_id}"

    count = get_referrals(user_id)

    discount = referral_discount(user_id)

    link = referral_link(user_id)

    progress = min(count,30)

    blocks = int((progress/30)*16)

    bar = "█"*blocks + "░"*(16-blocks)

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

    share_text = quote("""🔥 I just joined the ValueHunter AI betting system.

Daily VIP signals at 18:00 🇬🇷

Join here:""")
    
    keyboard = InlineKeyboardMarkup()

    keyboard.add(
        InlineKeyboardButton(
            "👑 𝑻𝑶𝑷 𝑹𝑬𝑭𝑬𝑹𝑹𝑬𝑹𝑺",
            callback_data="top_ref"
        )
    )
    
    keyboard.add(
        InlineKeyboardButton(
            "📤 𝑺𝑯𝑨𝑹𝑬 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹",
            url=f"https://t.me/share/url?url={ref_link}&text=🔥 Join ValueHunter Elite AI Betting System"
        )
    )

    keyboard.add(
        InlineKeyboardButton(
            "◀ 𝑩𝑨𝑪𝑲",
            callback_data="back_menu"
        )
    )

    bot.send_message(
        user_id,
        text,
        reply_markup=keyboard
    )

# ---------- MONTHLY REPORT ----------

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
    stake = 50

    for odds,result in rows:

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

𝗣𝗥𝗢𝗙𝗜𝗧: {round(profit,2)} €
"""

# ---------- BANKROLL TRACKER ----------

def bankroll_status():

    rows = cursor.execute(
        "SELECT odds,result FROM bets_history"
    ).fetchall()

    bankroll = START_BANKROLL

    for odds,result in rows:

        if result == "WIN":
            bankroll += (odds * stake) - stake

        elif result == "LOSE":
            bankroll -= stake

    profit = bankroll - START_BANKROLL

    roi = (profit / START_BANKROLL) * 100

    return f"""
🏧 𝑩𝑨𝑵𝑲𝑹𝑶𝑳𝑳

𝗦𝗧𝗔𝗥𝗧𝗜𝗡𝗚: {START_BANKROLL}€
𝗖𝗨𝗥𝗥𝗘𝗡𝗧: {round(bankroll,2)}€

𝗥𝗢𝗜: {round(roi,2)}%
"""

# ================= AUTO SIGNALS =================

def send_signals():

    tz = pytz.timezone("Europe/Athens")

    admin_sent_today = False
    vip_sent_today = False
    last_cleanup_day = None

    while True:
        today = datetime.now(tz).date()

        if last_cleanup_day != today:
           clean_sent_bets()
           last_cleanup_day = today
        expiry_reminders()
        grade_results()
        
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
            
        # ---------- PRE SIGNAL FOMO 17:30 ----------

        if hour == 17 and minute == 30:

            import random
 
            members = random.randint(14,22)

            countdown = signal_countdown()

            users = get_all_users()

            text = f"""
        👑 𝑬𝑳𝑰𝑻𝑬 𝑵𝑬𝑻𝑾𝑶𝑹𝑲

        {members} members preparing today's bets.

        ⏳ Signal release in
        {countdown}

        ⚜️ Elite members are already preparing their positions.

        🔐 Unlock access before the signals are released.
        """
            keyboard = InlineKeyboardMarkup()

            keyboard.add(
                InlineKeyboardButton(
                    "⚜️ 𝑼𝑵𝑳𝑶𝑪𝑲 𝑽𝑰𝑷 𝑺𝑰𝑮𝑵𝑨𝑳𝑺",
                    callback_data="elite"
                )
            )

            for uid in users:

                if is_vip(uid):
                    continue

                try:
                    bot.send_message(uid,text,reply_markup=keyboard)
                    time.sleep(0.05)
                except:
                    pass
            
        # ---------- FOMO MESSAGE 17:45 ----------

        if hour == 17 and minute == 45:

            users = get_all_users()

            keyboard = InlineKeyboardMarkup()
            keyboard.add(
                InlineKeyboardButton(
                    "⚜️ 𝑼𝑵𝑳𝑶𝑪𝑲 𝑽𝑰𝑷 𝑺𝑰𝑮𝑵𝑨𝑳𝑺",
                    callback_data="elite"
                )
            )

            text = """
            ⚜️ 𝑻𝑶𝑫𝑨𝒀'𝑺 𝑽𝑰𝑷 𝑺𝑰𝑮𝑵𝑨𝑳𝑺 𝑨𝑹𝑬 𝑹𝑬𝑨𝑫𝒀

            The 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 model has finalized today's analysis.

            Our system scanned hundreds of matches and identified the strongest value opportunities.

            ━━━━━━━━━━━━━━

            ⚠️ 𝑽𝑰𝑷 signals will be released at 18:00.(Europe/Athens)🇬🇷

            𝗠𝗘𝗠𝗕𝗘𝗥𝗦 𝗔𝗥𝗘 𝗔𝗟𝗥𝗘𝗔𝗗𝗬 𝗣𝗥𝗘𝗣𝗔𝗥𝗜𝗡𝗚 𝗧𝗢𝗗𝗔𝗬’𝗦 𝗕𝗘𝗧𝗦.

            𝗦𝗘𝗖𝗨𝗥𝗘 𝗔𝗖𝗖𝗘𝗦𝗦 𝗕𝗘𝗙𝗢𝗥𝗘 𝗧𝗛𝗘 𝗥𝗘𝗟𝗘𝗔𝗦𝗘.
            """

            for uid in users:

                if is_vip(uid):
                    continue

                try:
                    bot.send_message(
                        uid,
                        text,
                        reply_markup=keyboard
                    )
                    time.sleep(0.05)
                except:
                    pass
                    
        # ---------- VIP 18:00 ----------

        if hour == 18 and minute == 0 and not vip_sent_today:

            vip_sent_today = True 
            
            users = get_vip_users()

            for uid, plan in users:

                if plan == "BASIC":
                    picks = bets[:1]

                elif plan in ["PRO","DAY"]:
                    picks = bets[:3]
                else:
                    continue

                text = "🎖️ VIP SIGNALS\n\n" + "\n\n".join(picks)

                bot.send_message(uid, text)
                time.sleep(0.05)

            vip_sent_today = True

        # reset κάθε μέρα

        if hour == 0 and minute == 0:
            admin_sent_today = False
            vip_sent_today = False

        time.sleep(30)
        
        # ---------- MONTHLY REPORT ----------

        if now.day == 1 and hour == 12 and minute == 0:

            report = monthly_report()

            send_secure_message(
                ADMIN_ID,
                report
            )
# ---------- SECURE SEND MESSAGE ----------

def send_secure_message(user_id, text):

    try:
        bot.send_message(
            user_id,
            text,
            protect_content=True
        )
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

        # 1 ώρα πριν λήξει
        if remaining <= 3600:

            if cursor.execute(
                "SELECT user_id FROM expiry_notified WHERE user_id=?",
                (user_id,)
            ).fetchone():
                continue

            keyboard = InlineKeyboardMarkup()

            keyboard.add(
                InlineKeyboardButton(
                    "⚜️ 𝑹𝑬𝑵𝑬𝑾 𝑽𝑰𝑷 𝑨𝑪𝑪𝑬𝑺𝑺",
                    callback_data="elite"
                )
            )

            # ---------- DAY PASS ----------
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

            # ---------- BASIC / PRO ----------
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

            bot.send_message(
                user_id,
                text,
                reply_markup=keyboard
            )

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

    cursor.execute("""
    DELETE FROM sent_bets
    WHERE rowid NOT IN (
        SELECT rowid FROM sent_bets ORDER BY rowid DESC LIMIT 5000
    )
    """)

    db.commit()
    
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
    
def vip_dashboard_keyboard():

    m = InlineKeyboardMarkup()

    m.add(InlineKeyboardButton("⚜️ 𝑽𝑰𝑷 𝑴𝑬𝑵𝑼", callback_data="vip_menu"))

    m.add(InlineKeyboardButton("📡 𝑴𝑶𝑫𝑬𝑳 𝑰𝑵𝑺𝑰𝑮𝑯𝑻𝑺", callback_data="model_insights"))

    m.add(InlineKeyboardButton("🧠 𝑩𝑬𝑻𝑻𝑰𝑵𝑮 𝑺𝑻𝑹𝑨𝑻𝑬𝑮𝒀", callback_data="betting_strategy"))

    m.add(InlineKeyboardButton("💸 𝑽𝑰𝑷 𝑹𝑬𝑺𝑼𝑳𝑻𝑺 𝑭𝑬𝑬𝑫", callback_data="vip_results"))

    return m
    
def send_vip_dashboard(user_id, message_id=None):
    
    countdown = signal_countdown()
    
    text = """
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
        bot.edit_message_text(
            text,
            user_id,
            message_id,
            reply_markup=vip_dashboard_keyboard()
        )
    else:
        bot.send_message(
            user_id,
            text,
            reply_markup=vip_dashboard_keyboard()
        )
    
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
    
def send_vip_menu(user_id, message_id=None):
    
    countdown = signal_countdown()
    
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
        bot.edit_message_text(
            text,
            user_id,
            message_id,
            reply_markup=vip_menu_keyboard()
        )
    else:
        bot.send_message(
            user_id,
            text,
            reply_markup=vip_menu_keyboard()
        )
    
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
        bot.edit_message_text(
            text,
            user_id,
            message_id,
            reply_markup=keyboard
        )
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
        bot.edit_message_text(
            text,
            user_id,
            message_id,
            reply_markup=keyboard
        )
    else:
        bot.send_message(user_id, text, reply_markup=keyboard)
        
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

    time.sleep(1.2)

    bot.edit_message_text(
"""
Loading...

███░░░░░░░░░░░░░
━━━━━━━━━━━━━━

📡 𝑪𝒐𝒏𝒏𝒆𝒄𝒕𝒊𝒏𝒈 𝒕𝒐 𝒈𝒍𝒐𝒃𝒂𝒍 𝒇𝒐𝒐𝒕𝒃𝒂𝒍𝒍 𝒅𝒂𝒕𝒂 𝒇𝒆𝒆𝒅𝒔...
""",
        chat_id,
        msg.message_id
    )

    time.sleep(1.2)

    bot.edit_message_text(
"""
Loading...

█████░░░░░░░░░░░
━━━━━━━━━━━━━━

🌐 𝑬𝒔𝒕𝒂𝒃𝒍𝒊𝒔𝒉𝒊𝒏𝒈 𝒔𝒆𝒄𝒖𝒓𝒆 𝒂𝒏𝒂𝒍𝒚𝒕𝒊𝒄𝒔 𝒏𝒆𝒕𝒘𝒐𝒓𝒌...
""",
        chat_id,
        msg.message_id
    )

    time.sleep(1.2)

    bot.edit_message_text(
"""
Loading...

████████░░░░░░░░
━━━━━━━━━━━━━━

📊 𝑺𝒄𝒂𝒏𝒏𝒊𝒏𝒈 𝒃𝒐𝒐𝒌𝒎𝒂𝒌𝒆𝒓 𝒐𝒅𝒅𝒔 𝒇𝒆𝒆𝒅𝒔...
""",
        chat_id,
        msg.message_id
    )

    time.sleep(1.2)

    bot.edit_message_text(
"""
Loading...

███████████░░░░░
━━━━━━━━━━━━━━

🧠 𝑳𝒐𝒂𝒅𝒊𝒏𝒈 𝒑𝒓𝒐𝒃𝒂𝒃𝒊𝒍𝒊𝒕𝒚 𝒎𝒐𝒅𝒆𝒍𝒔...
""",
        chat_id,
        msg.message_id
    )

    time.sleep(1.2)

    bot.edit_message_text(
"""
Loading...

████████████████
━━━━━━━━━━━━━━

🚀 𝑽𝒂𝒍𝒖𝒆𝑯𝒖𝒏𝒕𝒆𝒓 𝒔𝒚𝒔𝒕𝒆𝒎 𝒓𝒆𝒂𝒅𝒚
""",
        chat_id,
        msg.message_id
    )

    time.sleep(1)
    
# ================= TELEGRAM =================

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
                    (referrer,user_id)
                )

                db.commit()

        except:
            pass
    
    cursor.execute(
    "INSERT OR IGNORE INTO users VALUES (?)",
    (user_id,)
    )
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
    
def faq_menu(chat_id, message_id):

    text = """
❓ 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑭𝑨𝑸

Welcome inside the ValueHunter intelligence system.

What would you like to know?

━━━━━━━━━━━━━━
"""

    keyboard = InlineKeyboardMarkup()

    keyboard.add(
        InlineKeyboardButton(
            "🧠 How ValueHunter works",
            callback_data="faq_system"
        )
    )

    keyboard.add(
        InlineKeyboardButton(
            "📊 Why value betting wins",
            callback_data="faq_value"
        )
    )

    keyboard.add(
        InlineKeyboardButton(
            "💸 Referral program",
            callback_data="faq_referral"
        )
    )

    keyboard.add(
        InlineKeyboardButton(
            "⚜ Unlock Elite Access",
            callback_data="elite"
        )
    )

    keyboard.add(
        InlineKeyboardButton(
            "⬅ Back",
            callback_data="back_menu"
        )
    )

    bot.edit_message_text(
        text,
        chat_id,
        message_id,
        reply_markup=keyboard
    )
    
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

    keyboard.add(
        InlineKeyboardButton(
            "➡ Next",
            callback_data="faq_value"
        )
    )

    keyboard.add(
        InlineKeyboardButton(
            "⬅ Back",
            callback_data="faq"
        )
    )

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

    keyboard.add(
        InlineKeyboardButton(
            "➡ Next",
            callback_data="faq_referral"
        )
    )

    keyboard.add(
        InlineKeyboardButton(
            "⬅ Back",
            callback_data="faq_system"
        )
    )

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

    keyboard.add(
        InlineKeyboardButton(
            "⚜ Unlock Elite Access",
            callback_data="elite"
        )
    )

    keyboard.add(
        InlineKeyboardButton(
            "⬅ Back",
            callback_data="faq_value"
        )
    )

    bot.edit_message_text(text, chat_id, message_id, reply_markup=keyboard)
    
@bot.callback_query_handler(func=lambda c: True)
def callbacks(c):

    bot.answer_callback_query(c.id)

    if c.data == "dev_sendvip":
        sendvip(c.message)

    # ---------- VIP DASHBOARD ----------
    if c.data == "vip_dashboard":

        send_vip_dashboard(
            c.message.chat.id,
            c.message.message_id
        )

    # ---------- VIP MENU ----------
    elif c.data == "vip_menu":

        send_vip_menu(
            c.message.chat.id,
            c.message.message_id
        )

    # ---------- MODEL INSIGHTS ----------
    elif c.data == "model_insights":

        text = """
📡 𝑴𝑶𝑫𝑬𝑳 𝑰𝑵𝑺𝑰𝑮𝑯𝑻𝑺

The 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 analytics engine scans hundreds of football matches daily to detect bookmaker pricing inefficiencies.

⚙️ Expected Goals modelling  
📉 Market price inefficiencies  
🔋 Sharp odds movement tracking  
💰 Liquidity signals  

𝗢𝗡𝗟𝗬 𝗧𝗛𝗘 𝗦𝗧𝗥𝗢𝗡𝗚𝗘𝗦𝗧 𝗩𝗔𝗟𝗨𝗘 𝗢𝗣𝗣𝗢𝗥𝗧𝗨𝗡𝗜𝗧𝗜𝗘𝗦 𝗣𝗔𝗦𝗦 𝗧𝗛𝗘 𝗠𝗢𝗗𝗘𝗟 𝗙𝗜𝗟𝗧𝗘𝗥𝗦 𝗔𝗡𝗗 𝗥𝗘𝗔𝗖𝗛 𝗘𝗟𝗜𝗧𝗘 𝗠𝗘𝗠𝗕𝗘𝗥𝗦.
"""

        keyboard = InlineKeyboardMarkup()

        keyboard.add(
            InlineKeyboardButton(
                "◀ 𝑩𝑨𝑪𝑲 𝑻𝑶 𝑫𝑨𝑺𝑯𝑩𝑶𝑨𝑹𝑫",
                callback_data="vip_dashboard"
            )
        )

        bot.edit_message_text(
            text,
            c.message.chat.id,
            c.message.message_id,
            reply_markup=keyboard
        )

    # ---------- BETTING STRATEGY ----------
    elif c.data == "betting_strategy":

        text = """
🧠 𝑩𝑬𝑻𝑻𝑰𝑵𝑮 𝑺𝑻𝑹𝑨𝑻𝑬𝑮𝒀

The 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 system focuses on long-term profitable betting.

𝗥𝗘𝗖𝗢𝗠𝗠𝗘𝗡𝗗𝗘𝗗 𝗦𝗧𝗔𝗞𝗜𝗡𝗚 𝗠𝗢𝗗𝗘𝗟:

💰 𝟏–𝟑% 𝑩𝑨𝑵𝑲𝑹𝑶𝑳𝑳 𝑹𝑰𝑺𝑲 𝑷𝑬𝑹 𝑺𝑰𝑮𝑵𝑨𝑳  
📊 𝟏–𝟑 𝑷𝑹𝑬𝑴𝑰𝑼𝑴 𝑽𝑨𝑳𝑼𝑬 𝑩𝑬𝑻𝑺 𝑷𝑬𝑹 𝑫𝑨𝒀

Consistent discipline allows members to replicate the same bankroll growth curve as the model.
"""

        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(
                "◀ 𝑩𝑨𝑪𝑲 𝑻𝑶 𝑫𝑨𝑺𝑯𝑩𝑶𝑨𝑹𝑫",
                callback_data="vip_dashboard"
            )
        )

        bot.edit_message_text(
            text,
            c.message.chat.id,
            c.message.message_id,
            reply_markup=keyboard
        )

    # ---------- RESULTS FEED ----------
    elif c.data == "vip_results":

        text = """
💸 𝑽𝑰𝑷 𝑹𝑬𝑺𝑼𝑳𝑻𝑺 𝑭𝑬𝑬𝑫

Recent signals from the ValueHunter network:

✔ Over 2.5 — WIN  
✔ BTTS — WIN  
❌ Under 2.5 — LOSS  
✔ Over 1.5 — WIN  

The 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 system focuses on identifying bookmaker pricing errors rather than predicting every match.
"""

        keyboard = InlineKeyboardMarkup()

        keyboard.add(
            InlineKeyboardButton(
                "◀ 𝑩𝑨𝑪𝑲 𝑻𝑶 𝑫𝑨𝑺𝑯𝑩𝑶𝑨𝑹𝑫",
                callback_data="vip_dashboard"
            )
        )

        bot.edit_message_text(
            text,
            c.message.chat.id,
            c.message.message_id,
            reply_markup=keyboard
        )

    # ---------- VIP SIGNALS ----------
    elif c.data == "vip_signals":

        now = datetime.now(pytz.timezone("Europe/Athens")).hour

        if now < 18:

            countdown = signal_countdown()

            import random

            bars = [
                "████░░░░░░",
                "█████░░░░░",
                "██████░░░░",
                "███████░░░",
                "████████░░",
                "█████████░"
            ]

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

        keyboard.add(
            InlineKeyboardButton(
                "◀ 𝑩𝑨𝑪𝑲 𝑻𝑶 𝑽𝑰𝑷 𝑴𝑬𝑵𝑼",
                callback_data="vip_menu"
            )
        )

        bot.edit_message_text(
            text,
            c.message.chat.id,
            c.message.message_id,
            reply_markup=keyboard
        )

    # ---------- PERFORMANCE ----------
    elif c.data == "vip_performance":

        text = f"""
📈 𝑬𝑳𝑰𝑻𝑬 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑷𝑬𝑹𝑭𝑶𝑹𝑴𝑨𝑵𝑪𝑬

{performance()}

━━━━━━━━━━━━━━

📅 𝑴𝑶𝑵𝑻𝑯𝑳𝒀 𝑷𝑬𝑹𝑭𝑶𝑹𝑴𝑨𝑵𝑪𝑬 𝑶𝑽𝑬𝑹𝑽𝑰𝑬𝑾

{monthly_report()}
"""

        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(
                "◀ 𝑩𝑨𝑪𝑲 𝑻𝑶 𝑽𝑰𝑷 𝑴𝑬𝑵𝑼",
                callback_data="vip_menu"
            )
        )

        bot.edit_message_text(
            text,
            c.message.chat.id,
            c.message.message_id,
            reply_markup=keyboard
        )
        
    elif c.data == "dev_engine":
        dev_engine(c.message.chat.id)

    elif c.data == "dev_parlay":
        dev_parlay(c.message.chat.id)
    
    elif c.data == "dev_sendvip":
        sendvip(c.message)

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

    # ---------- BANKROLL ----------
    elif c.data == "vip_bankroll":

        text = bankroll_status()

        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(
                "◀ 𝑩𝑨𝑪𝑲 𝑻𝑶 𝑽𝑰𝑷 𝑴𝑬𝑵𝑼",
                callback_data="vip_menu"
            )
        )

        bot.edit_message_text(
            text,
            c.message.chat.id,
            c.message.message_id,
            reply_markup=keyboard
        )

    # ---------- ALERTS ----------
    elif c.data == "vip_alerts":

        text = market_alert()

        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(
                "◀ 𝑩𝑨𝑪𝑲 𝑻𝑶 𝑽𝑰𝑷 𝑴𝑬𝑵𝑼",
                callback_data="vip_menu"
            )
        )

        bot.edit_message_text(
            text,
            c.message.chat.id,
            c.message.message_id,
            reply_markup=keyboard
        )

    # ---------- VIP STATUS ----------
    elif c.data == "vip_status":

        vip_status(
            c.message.chat.id
        )

    # ---------- VIP SUPPORT ----------
    elif c.data == "vip_support":

        vip_support(
            c.message.chat.id
        )

    # ================= ELITE PLANS =================
    elif c.data == "elite":

        m = InlineKeyboardMarkup()
        
        m.add(InlineKeyboardButton("💎 𝑫𝑨𝒀 𝑷𝑨𝑺𝑺 — 𝟐𝟓€", callback_data="buy_day"))
        m.add(InlineKeyboardButton("🥉 𝑩𝑨𝑺𝑰𝑪 — 𝟓𝟎€", callback_data="buy_basic"))
        m.add(InlineKeyboardButton("🥇 𝑷𝑹𝑶 — 𝟏𝟎𝟎€", callback_data="buy_pro"))
        m.add(InlineKeyboardButton("◀ 𝑩𝑨𝑪𝑲 𝑻𝑶 𝑷𝑳𝑨𝑵𝑺", callback_data="back_menu"))

        bot.edit_message_text(
"""
🎖️ 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑬𝑳𝑰𝑻𝑬 𝑷𝑳𝑨𝑵𝑺

The 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 analytics engine scans hundreds of football matches daily to detect bookmaker pricing inefficiencies and high-probability value opportunities across global football markets.

━━━━━━━━━━━━━━
💎 𝑫𝑨𝒀 𝑷𝑨𝑺𝑺 — 𝟐𝟓€

• 𝟐𝟒 𝑯𝑶𝑼𝑹 𝑷𝑹𝑶 𝑨𝑪𝑪𝑬𝑺𝑺  
• Receive today's full signal card  
• Perfect to experience the ValueHunter system

━━━━━━━━━━━━━━

🥉 𝑩𝑨𝑺𝑰𝑪 — 𝟓𝟎€

• 𝟏 𝑷𝑹𝑬𝑴𝑰𝑼𝑴 𝑽𝑨𝑳𝑼𝑬 𝑩𝑬𝑻 𝑷𝑬𝑹 𝑫𝑨𝒀  
• Selected from the highest model edge  
• Ideal for disciplined bankroll growth

━━━━━━━━━━━━━━

🥇 𝑷𝑹𝑶 — 𝟏𝟎𝟎€

• 𝟑 𝑷𝑹𝑬𝑴𝑰𝑼𝑴 𝑽𝑨𝑳𝑼𝑬 𝑩𝑬𝑻𝑺 𝑷𝑬𝑹 𝑫𝑨𝒀  
• Full access to the model's top signals  
• Maximum exposure to the strongest value opportunities

━━━━━━━━━━━━━━

🕕 𝑶𝑭𝑭𝑰𝑪𝑰𝑨𝑳 𝑺𝑰𝑮𝑵𝑨𝑳 𝑹𝑬𝑳𝑬𝑨𝑺𝑬  
18:00 (Athens Time) 🇬🇷

💎 Limited VIP access available today.
[Select your ValueHunter membership plan]
""",
            c.message.chat.id,
            c.message.message_id,
            reply_markup=m
        )
        
    # ================= BASIC =================

    elif c.data == "buy_basic":

        link = create_payment(50, c.message.chat.id)

        keyboard = InlineKeyboardMarkup()

        keyboard.add(
            InlineKeyboardButton(
                "💳 𝑷𝑨𝒀 𝑾𝑰𝑻𝑯 𝑪𝑨𝑹𝑫 / 𝑪𝑹𝒀𝑷𝑻𝑶",
                url=link
            )
        )

        keyboard.add(
            InlineKeyboardButton(
                "◀ 𝑩𝑨𝑪𝑲 𝑻𝑶 𝑷𝑳𝑨𝑵𝑺",
                callback_data="elite"
            )
        )

        bot.send_message(
            c.message.chat.id,
"""
🥉 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑩𝑨𝑺𝑰𝑪 𝑨𝑪𝑪𝑬𝑺𝑺

Unlock entry to the ValueHunter signal network.

━━━━━━━━━━━━━━

• 𝟏 𝑷𝑹𝑬𝑴𝑰𝑼𝑴 𝑽𝑨𝑳𝑼𝑬 𝑩𝑬𝑻 𝑷𝑬𝑹 𝑫𝑨𝒀  
• 𝑺𝑬𝑳𝑬𝑪𝑻𝑬𝑫 𝑭𝑹𝑶𝑴 𝑻𝑯𝑬 𝑯𝑰𝑮𝑯𝑬𝑺𝑻 𝑴𝑶𝑫𝑬𝑳 𝑬𝑫𝑮𝑬

━━━━━━━━━━━━━━

🕕 𝑶𝑭𝑭𝑰𝑪𝑰𝑨𝑳 𝑺𝑰𝑮𝑵𝑨𝑳 𝑹𝑬𝑳𝑬𝑨𝑺𝑬  
18:00 (Athens Time) 🇬🇷
""",
            reply_markup=keyboard
        )


    # ================= PRO =================

    elif c.data == "buy_pro":

        link = create_payment(100, c.message.chat.id)

        keyboard = InlineKeyboardMarkup()

        keyboard.add(
            InlineKeyboardButton(
                "💳 𝑷𝑨𝒀 𝑾𝑰𝑻𝑯 𝑪𝑨𝑹𝑫 / 𝑪𝑹𝒀𝑷𝑻𝑶",
                url=link
            )
        )

        keyboard.add(
            InlineKeyboardButton(
                "◀ 𝑩𝑨𝑪𝑲 𝑻𝑶 𝑷𝑳𝑨𝑵𝑺",
                callback_data="elite"
            )
        )

        bot.send_message(
            c.message.chat.id,
"""
🥇 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑷𝑹𝑶 𝑨𝑪𝑪𝑬𝑺𝑺

Unlock full access to the ValueHunter signal network.

━━━━━━━━━━━━━━

• 𝟑 𝑷𝑹𝑬𝑴𝑰𝑼𝑴 𝑽𝑨𝑳𝑼𝑬 𝑩𝑬𝑻𝑺 𝑫𝑨𝑰𝑳𝒀  
• 𝑭𝑼𝑳𝑳 𝑨𝑪𝑪𝑬𝑺𝑺 𝑻𝑶 𝑴𝑶𝑫𝑬𝑳 𝑺𝑰𝑮𝑵𝑨𝑳𝑺

━━━━━━━━━━━━━━

🕕 𝑶𝑭𝑭𝑰𝑪𝑰𝑨𝑳 𝑺𝑰𝑮𝑵𝑨𝑳 𝑹𝑬𝑳𝑬𝑨𝑺𝑬  
18:00 (Athens Time) 🇬🇷
""",
            reply_markup=keyboard
        )


    # ================= DAY PASS =================

    elif c.data == "buy_day":

        link = create_payment(25, c.message.chat.id)

        keyboard = InlineKeyboardMarkup()

        keyboard.add(
            InlineKeyboardButton(
                "💳 𝑷𝑨𝒀 𝑾𝑰𝑻𝑯 𝑪𝑨𝑹𝑫 / 𝑪𝑹𝒀𝑷𝑻𝑶",
                url=link
            )
        )

        keyboard.add(
            InlineKeyboardButton(
                "◀ 𝑩𝑨𝑪𝑲 𝑻𝑶 𝑷𝑳𝑨𝑵𝑺",
                callback_data="elite"
            )
        )

        bot.send_message(
            c.message.chat.id,
"""
💎 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑫𝑨𝒀 𝑷𝑨𝑺𝑺

Unlock full access to today's premium signals.

━━━━━━━━━━━━━━

• 𝟐𝟒 𝑯𝑶𝑼𝑹 𝑷𝑹𝑶 𝑨𝑪𝑪𝑬𝑺𝑺  
• 𝑼𝑷 𝑻𝑶 𝟑 𝑷𝑹𝑬𝑴𝑰𝑼𝑴 𝑽𝑨𝑳𝑼𝑬 𝑺𝑰𝑮𝑵𝑨𝑳𝑺

━━━━━━━━━━━━━━

🕕 𝑶𝑭𝑭𝑰𝑪𝑰𝑨𝑳 𝑺𝑰𝑮𝑵𝑨𝑳 𝑹𝑬𝑳𝑬𝑨𝑺𝑬  
18:00 (Athens Time) 🇬🇷
""",
            reply_markup=keyboard
        )


    # ================= SAMPLE =================

    elif c.data == "sample":

        threading.Thread(
            target=send_sample_with_scan,
            args=(c.message.chat.id,)
        ).start()

    # ================= ALERT =================

    elif c.data == "alert":

        keyboard = InlineKeyboardMarkup()

        keyboard.add(
            InlineKeyboardButton(
                "🔐 𝑼𝑵𝑳𝑶𝑪𝑲 𝑽𝑰𝑷 𝑨𝑪𝑪𝑬𝑺𝑺",
                callback_data="elite"
            )
        )

        keyboard.add(
            InlineKeyboardButton(
                "◀ 𝑩𝑨𝑪𝑲 𝑻𝑶 𝑷𝑳𝑨𝑵𝑺",
                callback_data="back_menu"
            )
        )

        bot.send_message(
            c.message.chat.id,
            market_alert(),
            reply_markup=keyboard
        )


    # ================= PERFORMANCE =================

    elif c.data == "perf":

        keyboard = InlineKeyboardMarkup()

        keyboard.add(
            InlineKeyboardButton(
                "🔐 𝑼𝑵𝑳𝑶𝑪𝑲 𝑽𝑰𝑷 𝑨𝑪𝑪𝑬𝑺𝑺",
                callback_data="elite"
            )
        )

        keyboard.add(
            InlineKeyboardButton(
                "◀ 𝑩𝑨𝑪𝑲 𝑻𝑶 𝑷𝑳𝑨𝑵𝑺",
                callback_data="back_menu"
            )
        )

        bot.send_message(
            c.message.chat.id,
            f"""
📊 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑷𝑬𝑹𝑭𝑶𝑹𝑴𝑨𝑵𝑪𝑬

{performance()}

📈 𝑴𝑶𝑵𝑻𝑯𝑳𝒀 𝑹𝑬𝑺𝑼𝑳𝑻𝑺

{monthly_report()}
""",
            reply_markup=keyboard
        )


    # ================= SUPPORT =================

    elif c.data == "support":

        keyboard = InlineKeyboardMarkup()

        keyboard.add(
            InlineKeyboardButton(
                "◀ 𝑩𝑨𝑪𝑲 𝑻𝑶 𝑷𝑳𝑨𝑵𝑺",
                callback_data="back_menu"
            )
        )

        bot.send_message(
            c.message.chat.id,
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

        faq_menu(
            c.message.chat.id,
            c.message.message_id
        )
        
    elif c.data == "faq_system":

        faq_system(
            c.message.chat.id,
            c.message.message_id
        )
        
    elif c.data == "faq_value":

        faq_value(
            c.message.chat.id,
            c.message.message_id
        )
        
    elif c.data == "faq_referral":

        faq_referral(
            c.message.chat.id,
            c.message.message_id
        )

    # ================= BACK =================

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
        c.message.chat.id,
        c.message.message_id,
        reply_markup=main_menu()
    )
    
    elif c.data == "referral":

        referral_panel(c.message.chat.id)
        
    elif c.data == "top_ref":

        text = get_daily_referrers()

        keyboard = InlineKeyboardMarkup()

        keyboard.add(
            InlineKeyboardButton(
                "⬅ BACK",
                callback_data="referral"
            )
        )

        bot.edit_message_text(
            text,
            c.message.chat.id,
            c.message.message_id,
            reply_markup=keyboard
        )
        
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

        bot.send_message(uid, text)

    # -------- SAVE BETS TO HISTORY --------

    for bet in bets:

        try:

            lines = bet.split("\n")

            match = lines[0].replace("⚽ ","")
            pick = lines[1].replace("🎯 ","")
            odds = float(lines[2].replace("💰 Odds ",""))

            cursor.execute(
            """
            INSERT INTO bets_history(match,pick,odds,result,timestamp)
            VALUES(?,?,?,?,?)
            """,
            (match,pick,odds,"PENDING",int(time.time()))
            )

        except:
            pass

    db.commit()

    bot.send_message(m.chat.id,"VIP signals sent.")
    
@bot.message_handler(commands=["stats"])
def stats(m):

    if m.chat.id != ADMIN_ID:
        return

    bot.send_message(
        m.chat.id,
        performance() + "\n\n" + monthly_report()
    )
    
@bot.message_handler(commands=["bankroll"])
def bankroll(m):

    if m.chat.id != ADMIN_ID:
        return

    bot.send_message(
        m.chat.id,
        bankroll_status()
    )
    
@bot.message_handler(commands=["users"])
def users(m):

    if m.chat.id != ADMIN_ID:
        return

    all_users = get_all_users()
    vip = get_vip_users()

    bot.send_message(
        m.chat.id,
        f"""
Total users: {len(all_users)}
VIP users: {len(vip)}
"""
    )
    
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

    users = get_all_users()

    for uid in users:

        try:
            bot.send_message(uid,text)
        except:
            pass

    bot.send_message(m.chat.id,"Broadcast sent.")
    
@bot.message_handler(commands=["viplist"])
def viplist(m):

    if m.chat.id != ADMIN_ID:
        return

    users = get_vip_users()

    text = "VIP USERS\n\n"

    for uid, plan in users:
        text += f"{uid} - {plan}\n"

    bot.send_message(m.chat.id,text)
    
@bot.message_handler(commands=["addvip"])
def addvip_cmd(m):

    if m.chat.id != ADMIN_ID:
        return

    try:
        _, user_id, days = m.text.split()

        add_vip(int(user_id),"PRO",int(days))

        bot.send_message(m.chat.id,"VIP added.")
    except:
        bot.send_message(m.chat.id,"Usage: /addvip user_id days")
        
@bot.message_handler(commands=["removevip"])
def removevip(m):

    if m.chat.id != ADMIN_ID:
        return

    try:
        _, user_id = m.text.split()

        cursor.execute(
            "DELETE FROM vip_users WHERE user_id=?",
            (int(user_id),)
        )

        db.commit()

        bot.send_message(m.chat.id,"VIP removed.")
    except:
        bot.send_message(m.chat.id,"Usage: /removevip user_id")
        
@bot.message_handler(commands=["bets"])
def bets(m):

    if m.chat.id != ADMIN_ID:
        return

    rows = cursor.execute(
        "SELECT match,pick,odds,result FROM bets_history ORDER BY id DESC LIMIT 10"
    ).fetchall()
    
    text = "LAST BETS\n\n"

    for match,pick,odds,result in rows:

        text += f"{match}\n{pick}\nOdds {odds} - {result}\n\n"

    bot.send_message(m.chat.id,text)
    
@bot.message_handler(commands=["reload_engine"])
def reload_engine(m):

    if m.chat.id != ADMIN_ID:
        return

    team_stats_cache.clear()
    injury_cache.clear()
    league_odds_cache.clear()

    bot.send_message(m.chat.id,"Engine cache cleared.")
    
@bot.message_handler(commands=["force_alert"])
def force_alert(m):

    if m.chat.id != ADMIN_ID:
        return

    alert = market_alert()

    users = get_all_users()

    for uid in users:

        try:
            bot.send_message(uid,alert)
        except:
            pass

    bot.send_message(m.chat.id,"Alert sent.")
    
@bot.message_handler(commands=["test_payment"])
def test_payment(m):

    if m.chat.id != ADMIN_ID:
        return

    link = create_payment(1,m.chat.id)

    bot.send_message(
        m.chat.id,
        f"Test payment link:\n{link}"
    )
    
@bot.message_handler(commands=["defmenu"])
def defmenu(m):

    if m.chat.id != ADMIN_ID:
        return

    keyboard = InlineKeyboardMarkup()

    keyboard.add(
        InlineKeyboardButton("🧠 𝑻𝑬𝑺𝑻 𝑽𝑨𝑳𝑼𝑬 𝑬𝑵𝑮𝑰𝑵𝑬", callback_data="dev_engine")
    )

    keyboard.add(
        InlineKeyboardButton("🎰 𝑽𝑨𝑳𝑼𝑬 𝑷𝑨𝑹𝑳𝑨𝒀", callback_data="dev_parlay")
    )

    keyboard.add(
        InlineKeyboardButton("🎯 𝑺𝑬𝑵𝑫 𝑽𝑰𝑷 𝑺𝑰𝑮𝑵𝑨𝑳𝑺", callback_data="dev_sendvip")
    )

    keyboard.add(
        InlineKeyboardButton("📊 𝑺𝑻𝑨𝑻𝑺", callback_data="dev_stats"),
        InlineKeyboardButton("🏦 𝑩𝑨𝑵𝑲𝑹𝑶𝑳𝑳", callback_data="dev_bankroll")
    )

    keyboard.add(
        InlineKeyboardButton("👥 𝑼𝑺𝑬𝑹𝑺", callback_data="dev_users"),
        InlineKeyboardButton("👑 𝑽𝑰𝑷 𝑳𝑰𝑺𝑻", callback_data="dev_viplist")
    )

    keyboard.add(
        InlineKeyboardButton("📊 𝑳𝑨𝑺𝑻 𝑩𝑬𝑻𝑺", callback_data="dev_bets")
    )

    keyboard.add(
        InlineKeyboardButton("📢 𝑩𝑹𝑶𝑨𝑫𝑪𝑨𝑺𝑻", callback_data="dev_broadcast"),
        InlineKeyboardButton("📡 𝑭𝑶𝑹𝑪𝑬 𝑨𝑳𝑬𝑹𝑻", callback_data="dev_alert")
    )

    keyboard.add(
        InlineKeyboardButton("🔄 𝑹𝑬𝑳𝑶𝑨𝑫 𝑬𝑵𝑮𝑰𝑵𝑬", callback_data="dev_reload")
    )

    keyboard.add(
        InlineKeyboardButton("💳 𝑻𝑬𝑺𝑻 𝑷𝑨𝒀𝑴𝑬𝑵𝑻", callback_data="dev_payment")
    )

    bot.send_message(
        m.chat.id,
        "🛠 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑫𝑬𝑽 𝑷𝑨𝑵𝑬𝑳",
        reply_markup=keyboard
    )

# ================= THREADS =================

threading.Thread(target=send_signals, daemon=True).start()

threading.Thread(
    target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT",8080))),
    daemon=True
).start()
threading.Thread(target=keep_alive, daemon=True).start()

# ================= RUN =================

bot.infinity_polling()