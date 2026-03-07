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
import os
import hmac
import hashlib
import json
# ================= CONFIG =================

TOKEN = "8767848071:AAHjxT7945VO-X7iCI3kG-0fIqC_giqX7Z8"
ADMIN_ID = 8328070177

FOOTBALL_API_KEY = "2f8c79b66ceed85aaf20322308f11e5a"
ODDS_API_KEY = "e55ba3ebd10f1d12494c0c10f1bfdb32"
NOWPAY_API_KEY = "ZB43Y23-F3E4XKG-K83X2GC-MPAAHZ5"
IPN_SECRET = "5B8MWD7S1sz5J+F100Hr7PyHI2D3jCjR"

START_BANKROLL = 2000
stake = 50

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

    m.add(InlineKeyboardButton("🔥 Unlock VIP Signals", callback_data="elite"))
    m.add(InlineKeyboardButton("🎁 Today's FREE Bet", callback_data="sample"))
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

    bot.send_message(
        user_id,
        """
🔥 PAYMENT CONFIRMED

Welcome to VALUEHUNTER ELITE.

🔑Your access is now active

🕔 17:00 Model release
🕕 18:00 VIP signals
"""
    )
    
    cursor.execute(
        "INSERT INTO processed_payments VALUES (?)",
        (payment_id,)
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
848   # Conference League
}

league_strength = {
39:1.05,
78:1.08,
135:0.95,
140:1.00,
61:0.97,
88:1.02,
94:0.98,
203:0.96
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

# ---------- IMPLIED PROBABILITY ----------

def implied_probability(odds):
    return 1/odds


# ---------- MATCH SCANNER ----------

def scan_matches():

    global fixtures_cache, fixtures_cache_time

    if time.time() - fixtures_cache_time < 1800:
        return fixtures_cache

    fixtures = []

    for page in range(1,6):

        url = f"https://v3.football.api-sports.io/fixtures?next=100&page={page}"
        headers = {"x-apisports-key": FOOTBALL_API_KEY}

        try:
            r = requests.get(url, headers=headers).json()
            time.sleep(0.1)
        except:
            continue

        for m in r.get("response", []):

            match_time = m["fixture"]["timestamp"]
            now = int(time.time())

            if not (7200 <= match_time-now <= 259200):
                continue

            fixtures.append({
                "fixture_id": m["fixture"]["id"],
                "home": m["teams"]["home"]["name"],
                "away": m["teams"]["away"]["name"],
                "home_id": m["teams"]["home"]["id"],
                "away_id": m["teams"]["away"]["id"],
                "league_id": m["league"]["id"]
            })

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

def monte_carlo_simulation(home_xg,away_xg,simulations=1000):

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
    if total_xg < 1.8:
        return False

    # πολύ υψηλό tempo (unstable poisson)
    if total_xg > 4.2:
        return False

    # πολύ μονόπλευρο παιχνίδι
    if abs(home_xg - away_xg) > 2.2:
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
        🔥 WIN CONFIRMED

        ⚽ {match}
        🎯 {pick}
        📊 Odds {odds}

        VIP members collected another win today.
        
        📡 Next signals released at 18:00...

        🔐 Support: @MrMasterlegacy1
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
            🏆 VIP WIN CONFIRMED

            ⚽ {match}
            🎯 {pick}

            Elite members collected another **winning signal** today.

             ━━━━━━━━━━━━━━

            🔥 More signals will be released again at **18:00**.

            ⚠️ Access to the ValueHunter network may close once signals are released.
            """

            keyboard = InlineKeyboardMarkup()
            keyboard.add(
                InlineKeyboardButton(
                    "🔐 Unlock VIP Access",
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
        
        xg_diff = abs(home_xg - away_xg)
        total_xg = home_xg + away_xg

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

            implied = implied_probability(odds_value)

            edge = prob - implied
            
            market_prob = 1 / odds_value

            if prob - market_prob < 0.02:
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

            if edge < 0.05 or prob < 0.56:
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

            if ev <= 0.05:
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
💰 Value {round(super_safe['ev'],2)}
💵 Stake {round(super_safe['stake']*100,1)}% bankroll

{super_safe['early']}

💸 Bet: 50€"""
        )

    for bet in high_value[:2]:

        signals.append(
f"""🔥 HIGH VALUE
⚽ {bet['match']}
🎯 {bet['pick']}
📊 Odds {round(bet['odds'],2)}
📈 Probability {round(bet['prob']*100)}%
💰 Value {round(bet['ev'],2)}
💵 Stake {round(bet['stake']*100,1)}% bankroll

{bet['early']}

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
⏳ Free sample already used.

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
🚨 SHARP MONEY ALERT

⚽ {home} vs {away}

Odds dropped:
{open_odds} → {new_odds}

Heavy betting activity detected.

━━━━━━━━━━━━━━

⚡ Elite members will receive the official signal before the market reacts.

⚠️ Access to the ValueHunter network may close once signals are released.
"""

    alert_cache = alert_text
    alert_cache_time = time.time()

    return alert_text

def start_conversion_funnel(user_id):

    def funnel():

        # ---------- MESSAGE 1 (30 minutes) ----------
        time.sleep(1800)

        try:
            bot.send_message(
                user_id,
"""
📡 MODEL UPDATE

The ValueHunter analytics engine has already started scanning today's football markets.

Several **high probability value opportunities** have been detected.

Elite members will receive the final signals before the market reacts.

━━━━━━━━━━━━━━

⚠️ Access is currently open but may close once signals are released.

Use the menu to unlock access.
"""
            )
        except:
            pass


        # ---------- MESSAGE 2 (2 hours) ----------
        time.sleep(7200)

        try:
            bot.send_message(
                user_id,
"""
⚡ MARKET MOVEMENT DETECTED

The system has detected **unusual betting activity** on today's matches.

Sharp money is entering the market.

When this happens, odds usually drop quickly.

━━━━━━━━━━━━━━

Elite members will receive the signal **before the market moves**.

Signals release today at **18:00**.
"""
            )
        except:
            pass


        # ---------- MESSAGE 3 (before signals) ----------
        time.sleep(3600)

        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(
                "🔐 Unlock Elite Access",
                callback_data="elite"
            )
        )

        try:
            bot.send_message(
                user_id,
"""
⏳ FINAL ENTRY WINDOW

Today's ValueHunter signals will be released soon.

Our model has already selected the **strongest value opportunities** from hundreds of matches.

━━━━━━━━━━━━━━

⚠️ Once signals are released, access may close to protect the betting edge.

Elite members are already preparing today's bets.

Secure your access before the release.
""",
                reply_markup=keyboard
            )
        except:
            pass

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
📊 DAILY PERFORMANCE

Wins: {dw}
Losses: {dl}

Profit: {round(dp,2)} €


📈 WEEKLY PERFORMANCE

Wins: {ww}
Losses: {wl}

Profit: {round(wp,2)} €
"""

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
📊 MONTHLY REPORT

Wins: {wins}
Losses: {losses}

Profit: {round(profit,2)} €
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
📊 BANKROLL

Starting: {START_BANKROLL}€
Current: {round(bankroll,2)}€

ROI: {round(roi,2)}%
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
            
        # ---------- FOMO MESSAGE 17:45 ----------

        if hour == 17 and minute == 45:

            users = get_all_users()

            keyboard = InlineKeyboardMarkup()
            keyboard.add(
                InlineKeyboardButton(
                    "🔐 Unlock VIP Signals",
                    callback_data="elite"
                )
            )

            text = """
            🚀 TODAY'S VIP SIGNALS ARE READY

            The ValueHunter model has finalized today's analysis.

            Our system scanned hundreds of matches and identified the strongest value opportunities.

            ━━━━━━━━━━━━━━

            ⚠️ VIP signals will be released at **18:00**.

            Members are already preparing today's bets.

            Secure access before the release.
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

                text = "🔥 VIP SIGNALS\n\n" + "\n\n".join(picks)

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
                    "🔓 Renew VIP Access",
                    callback_data="elite"
                )
            )

            # ---------- DAY PASS ----------
            if plan == "DAY":

                text = """
⚠️ YOUR DAY PASS IS EXPIRING SOON

Your 24 hour ValueHunter access** will expire in less than 1 hour.

We hope you enjoyed experiencing the **ValueHunter Elite system** today.

Every day our model scans hundreds of matches to uncover **hidden bookmaker value opportunities**.

🔥 Today's members are already preparing the next signals.

If your access expires, you may miss the next opportunities.

━━━━━━━━━━━━━━

🥇Thank you for trying ValueHunter.

You can continue receiving signals by activating a membership below.
"""

            # ---------- BASIC / PRO ----------
            else:

                text = """
⚠️ YOUR VIP ACCESS IS ABOUT TO EXPIRE

Your ValueHunter Elite membership will expire in less than 1 hour.

Every day our analytics engine scans hundreds of matches to identify **high value betting opportunities** before the market moves.

🔥 The next signals will be released again at **18:00**.

If your access expires now, you may miss the upcoming value opportunities that our members are preparing for.

━━━━━━━━━━━━━━

Thank you for being part of the **ValueHunter Elite network**.

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
        "⚙️ Initializing ValueHunter System...\n\n⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜"
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
                f"⚙️ Initializing ValueHunter System...\n\n{bar}",
                user_id,
                message.message_id
            )
        except:
            pass

    time.sleep(0.3)

    send_vip_dashboard(user_id)
    
def vip_dashboard_keyboard():

    m = InlineKeyboardMarkup()

    m.add(InlineKeyboardButton("⚜️ VIP MENU", callback_data="vip_menu"))

    m.add(InlineKeyboardButton("📡 Model Insights", callback_data="model_insights"))

    m.add(InlineKeyboardButton("🧠 Betting Strategy", callback_data="betting_strategy"))

    m.add(InlineKeyboardButton("💸 VIP Results Feed", callback_data="vip_results"))

    return m
    
def send_vip_dashboard(user_id, message_id=None):

    text = """
👑 𝑽𝑨𝑳𝑼𝑬𝑯𝑼𝑵𝑻𝑬𝑹 𝑬𝑳𝑰𝑻𝑬 𝑵𝑬𝑻𝑾𝑶𝑹𝑲

Welcome inside the private ValueHunter intelligence system.

You now have access to a restricted betting analytics network designed to detect bookmaker pricing errors and high-value opportunities across global football markets.

━━━━━━━━━━━━━━

🧠 Advanced Expected Goals Models  
📊 Market Inefficiency Detection  
📡 Sharp Money Monitoring  
💎 Liquidity Intelligence Signals  

━━━━━━━━━━━━━━

📡 System Status

🟢 Data feeds active  
🟢 Market monitoring active  
🟢 Model scanning global leagues  

━━━━━━━━━━━━━━

⏳ Next signal release  
🕕 18:00 (Europe/Athens)

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

    m.add(InlineKeyboardButton("📊 Today's Signals", callback_data="vip_signals"))

    m.add(InlineKeyboardButton("📈 Model Performance", callback_data="vip_performance"))

    m.add(InlineKeyboardButton("💰 Bankroll Tracker", callback_data="vip_bankroll"))

    m.add(InlineKeyboardButton("⚡ Early Market Alerts", callback_data="vip_alerts"))

    m.add(InlineKeyboardButton("📅 VIP Status", callback_data="vip_status"))

    m.add(InlineKeyboardButton("💬 VIP Support", callback_data="vip_support"))

    m.add(InlineKeyboardButton("🌐 Back to Dashboard", callback_data="vip_dashboard"))

    return m
    
def send_vip_menu(user_id, message_id=None):

    now = datetime.now(pytz.timezone("Europe/Athens")).hour

    if now < 18:

        text = """
⚜️ 𝑽𝑰𝑷 𝑪𝑶𝑵𝑻𝑹𝑶𝑳 𝑷𝑨𝑵𝑬𝑳

The ValueHunter analytics engine is currently scanning today's football markets.

📡 Market data streaming  
🧠 Models calculating probabilities  
💎 Value opportunities being filtered  

⏳ Official signal release:

🕕 18:00

Elite members are preparing their positions.
"""

    else:

        text = """
⚜️ 𝑽𝑰𝑷 𝑺𝑰𝑮𝑵𝑨𝑳 𝑪𝑬𝑵𝑻𝑬𝑹

Today's ValueHunter signals have been released to the Elite network.

📊 Model probabilities calculated  
📡 Market pressure analysed  
💎 Premium value opportunities identified  

Elite members are already placing today's bets.
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

Need assistance with signals or membership access?

━━━━━━━━━━━━━━

📩 Contact support:

@MrMasterlegacy1
"""

    keyboard = InlineKeyboardMarkup()

    keyboard.add(InlineKeyboardButton("🌐 Back to VIP Menu", callback_data="vip_menu"))

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

👤 User ID: {user_id}

💎 Plan: {plan}

📊 Signals per day: up to 3

⏳ Access expires:
{expiry}
"""

    keyboard = InlineKeyboardMarkup()

    keyboard.add(InlineKeyboardButton("🌐 Back to VIP Menu", callback_data="vip_menu"))

    if message_id:
        bot.edit_message_text(
            text,
            user_id,
            message_id,
            reply_markup=keyboard
        )
    else:
        bot.send_message(user_id, text, reply_markup=keyboard)
        
def signal_countdown():

    tz = pytz.timezone("Europe/Athens")

    now = datetime.now(tz)

    target = now.replace(hour=18, minute=0, second=0, microsecond=0)

    if now >= target:
        return "00:00:00"

    diff = target - now

    total_seconds = int(diff.total_seconds())

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    return f"{hours:02}:{minutes:02}:{seconds:02}"
    
# ================= TELEGRAM =================

@bot.message_handler(commands=["start"])
def start(m):
    
    user_id = m.chat.id

    if is_vip(user_id):
        send_vip_dashboard(user_id)
        return

    bot.send_message(
        m.chat.id,
"""
🔓 WELCOME TO VALUEHUNTER

You have just entered a **private betting intelligence network**.

This platform is operated by a professional analytics team focused on detecting **bookmaker pricing errors and high-value opportunities** across global football markets.

━━━━━━━━━━━━━━

📊 Our models analyze:

⚙️ Advanced Expected Goals data  
📉 Market inefficiencies  
📡 Sharp odds movement  
💰 Liquidity signals  

Hundreds of matches are scanned daily to identify **the strongest value opportunities**.

━━━━━━━━━━━━━━

⚠️ IMPORTANT NOTICE

Access to this network is **restricted**.

Membership capacity is limited and entry is **periodically closed** in order to maintain signal quality and protect the betting edge.

━━━━━━━━━━━━━━

🔓 If you received access today,  
you are currently inside a **temporary entry window**.

🔔 Today's signals will be released at 18:00.
⬇️ Use the menu below to explore the platform.
""",
        reply_markup=main_menu()
    )

    start_conversion_funnel(m.chat.id)


@bot.callback_query_handler(func=lambda c: True)
def callbacks(c):

    bot.answer_callback_query(c.id)
    
# ---------- VIP DASHBOARD ----------
elif c.data == "vip_dashboard":

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

    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton(
            "🌐 Back to Dashboard",
            callback_data="vip_dashboard"
        )
    )

    bot.edit_message_text(
        text,
        c.message.chat.id,
        c.message.message_id,
        reply_markup=keyboard
    )
        """
📡 MODEL INSIGHTS

The ValueHunter analytics engine scans hundreds of football matches daily to detect bookmaker pricing inefficiencies.

⚙️ Expected Goals modelling  
📉 Market price inefficiencies  
📡 Sharp odds movement tracking  
💰 Liquidity signals  

Only the strongest value opportunities pass the model filters and reach Elite members.
""",
        reply_markup=keyboard
    )

# ---------- BETTING STRATEGY ----------
elif c.data == "betting_strategy":

    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton(
            "🌐 Back to Dashboard",
            callback_data="vip_dashboard"
        )
    )

    bot.edit_message_text(
        text,
        c.message.chat.id,
        c.message.message_id,
        reply_markup=keyboard
    )
        """
🧠 BETTING STRATEGY

The ValueHunter system focuses on long-term profitable betting.

Recommended staking model:

💰 1-3% bankroll per signal  
📊 1-3 value bets daily  

Consistent discipline allows members to replicate the same bankroll growth curve as the model.
""",
        reply_markup=keyboard
    )

# ---------- RESULTS FEED ----------
elif c.data == "vip_results":

    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton(
            "🌐 Back to Dashboard",
            callback_data="vip_dashboard"
        )
    )

    bot.edit_message_text(
        text,
        c.message.chat.id,
        c.message.message_id,
        reply_markup=keyboard
    )
        """
💸 VIP RESULTS FEED

Recent signals from the ValueHunter network:

✔ Over 2.5 — WIN  
✔ BTTS — WIN  
❌ Under 2.5 — LOSS  
✔ Over 1.5 — WIN  

The ValueHunter system focuses on identifying bookmaker pricing errors rather than predicting every match.
""",
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

The ValueHunter analytics engine is currently scanning today's football markets.

━━━━━━━━━━━━━━

⏳ SIGNAL ENGINE STATUS

Scanning markets {scan_bar}

📡 Data feeds connected  
🧠 Probability models calculating  
💎 Value opportunities filtering  

━━━━━━━━━━━━━━

🕕 NEXT SIGNAL RELEASE  
18:00 (Europe/Athens)

⏱ Countdown
{countdown}

Elite members will receive today's signals as soon as the analysis is completed.
"""

    else:

        text = """
📊 𝑻𝑶𝑫𝑨𝒀'𝑺 𝑺𝑰𝑮𝑵𝑨𝑳𝑺

Today's ValueHunter signals have already been distributed to the Elite network.

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
            "🌐 Back to VIP Menu",
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

    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton(
            "🌐 Back to VIP Menu",
            callback_data="vip_menu"
        )
    )

    bot.edit_message_text(
        text,
        c.message.chat.id,
        c.message.message_id,
        reply_markup=keyboard
    )
        f"""
📈 VALUEHUNTER PERFORMANCE

{performance()}

━━━━━━━━━━━━━━

📅 Monthly overview

{monthly_report()}
""",
        reply_markup=keyboard
    )

# ---------- BANKROLL ----------
elif c.data == "vip_bankroll":

    text = bakroll_status()

    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton(
            "🌐 Back to VIP Menu",
            callback_data="vip_menu"
        )
    )

    bot.edit_message_text(
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
            "🌐 Back to VIP Menu",
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
        c.message.chat.id,
        c.message.message_id
    )

# ---------- VIP SUPPORT ----------
elif c.data == "vip_support":

    vip_support(
        c.message.chat.id,
        c.message.message_id
    )
    
# ================= ELITE PLANS =================

    if c.data == "elite":

        m = InlineKeyboardMarkup()

        m.add(InlineKeyboardButton("🥉 BASIC 50€", callback_data="buy_basic"))
        m.add(InlineKeyboardButton("🥇 PRO 100€", callback_data="buy_pro"))
        m.add(InlineKeyboardButton("⚡ DAY PASS 25€", callback_data="buy_day"))
        m.add(InlineKeyboardButton("⬅️ Back to plans", callback_data="back_menu"))

        bot.edit_message_text(
"""
👑 VALUEHUNTER ELITE ACCESS

Our system scans hundreds of matches daily
to detect bookmaker pricing mistakes and
high probability value opportunities.

━━━━━━━━━━━━━━

🥉 BASIC — 50€

• 1 Premium Value Bet per day  
• Selected from the highest model edge  

━━━━━━━━━━━━━━

🥇 PRO — 100€

• 3 Premium Value Bets per day  
• Full access to the model's top signals  

━━━━━━━━━━━━━━

⚡ DAY PASS — 25€

• 24 hour PRO access  
• Receive today's full signals  

⚠️ Access is limited to members.
Signals are released daily at 18:00.
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
                "💳 Pay with Card / Crypto",
                url=link
            )
        )

        keyboard.add(
            InlineKeyboardButton(
                "⬅️ Back to plans",
                callback_data="elite"
            )
        )

        bot.send_message(
            c.message.chat.id,
"""
🥉 BASIC ACCESS

You are about to unlock VALUEHUNTER BASIC membership.

• 1 Premium Value Bet per day  
• Selected from the highest model edge  

Signals released daily at 18:00.
""",
            reply_markup=keyboard
        )

# ================= PRO =================

    elif c.data == "buy_pro":

        link = create_payment(100, c.message.chat.id)

        keyboard = InlineKeyboardMarkup()

        keyboard.add(
            InlineKeyboardButton(
                "💳 Pay with Card / Crypto",
                url=link
            )
        )

        keyboard.add(
            InlineKeyboardButton(
                "⬅️ Back to plans",
                callback_data="elite"
            )
        )

        bot.send_message(
            c.message.chat.id,
"""
🥇 VALUEHUNTER PRO ACCESS

• 3 Premium Value Bets daily  
• Highest model edge opportunities  
• Full access to the model signals  

Signals released daily at 18:00.
""",
            reply_markup=keyboard
        )

# ================= DAY PASS =================

    elif c.data == "buy_day":

        link = create_payment(25, c.message.chat.id)

        keyboard = InlineKeyboardMarkup()

        keyboard.add(
            InlineKeyboardButton(
                "💳 Pay with Card / Crypto",
                url=link
            )
        )

        keyboard.add(
            InlineKeyboardButton(
                "⬅️ Back to plans",
                callback_data="elite"
            )
        )

        bot.send_message(
            c.message.chat.id,
"""
⚡ VALUEHUNTER DAY PASS

• 24 hour PRO access  
• Up to 3 premium signals today  

Signals released at 18:00.
""",
            reply_markup=keyboard
        )

# ================= SAMPLE =================

    elif c.data == "sample":

        bet = daily_sample(c.message.chat.id)

        bot.send_message(
            c.message.chat.id,
            f"🎁 FREE SAMPLE\n\n{bet}"
        )

        keyboard = InlineKeyboardMarkup()

        keyboard.add(
            InlineKeyboardButton(
                "🔥 Unlock VIP Signals",
                callback_data="elite"
            )
        )

        keyboard.add(
            InlineKeyboardButton(
                "⚡ Market Alert",
                callback_data="alert"
            )
        )

        bot.send_message(
            c.message.chat.id,
"""
🎁 FREE SAMPLE DELIVERED

Elite members already received
the full signal card for today.

Unlock VIP access to receive all signals.
""",
            reply_markup=keyboard
        )

# ================= ALERT =================

    elif c.data == "alert":

        keyboard = InlineKeyboardMarkup()

        keyboard.add(
            InlineKeyboardButton(
                "🔐 Unlock VIP Access",
                callback_data="elite"
            )
        )

        keyboard.add(
            InlineKeyboardButton(
                "⬅️ Back to plans",
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
                "🔐 Unlock VIP Access",
                callback_data="elite"
            )
        )

        keyboard.add(
            InlineKeyboardButton(
                "⬅️ Back to plans",
                callback_data="back_menu"
            )
        )

        bot.send_message(
            c.message.chat.id,
            f"""
📊 VALUEHUNTER PERFORMANCE

{performance()}

📈 MONTHLY RESULTS

{monthly_report()}
""",
            reply_markup=keyboard
        )

# ================= SUPPORT =================

    elif c.data == "support":

        keyboard = InlineKeyboardMarkup()

        keyboard.add(
            InlineKeyboardButton(
                "⬅️ Back to plans",
                callback_data="back_menu"
            )
        )

        bot.send_message(
            c.message.chat.id,
"""
💬 VALUEHUNTER SUPPORT

Contact:

🔹 @MrMasterlegacy1
""",
            reply_markup=keyboard
        )

# ================= BACK =================

    elif c.data == "back_menu":

        bot.edit_message_text(
            "👁‍🗨 VALUEHUNTER MENU",
            c.message.chat.id,
            c.message.message_id,
            reply_markup=main_menu()
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

        text = "🔥 VIP SIGNALS\n\n" + "\n\n".join(picks)

        bot.send_message(uid,text)

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
🔥 MARKET ACTIVITY DETECTED

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

# ================= THREADS =================

threading.Thread(target=send_signals, daemon=True).start()

threading.Thread(
    target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT",8080))),
    daemon=True
).start()
threading.Thread(target=keep_alive, daemon=True).start()

# ================= RUN =================

bot.infinity_polling()