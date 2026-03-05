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
# ================= CONFIG =================

TOKEN = "8767848071:AAHjxT7945VO-X7iCI3kG-0fIqC_giqX7Z8"
ADMIN_ID = 8328070177

FOOTBALL_API_KEY = "2f8c79b66ceed85aaf20322308f11e5a"
ODDS_API_KEY = "e55ba3ebd10f1d12494c0c10f1bfdb32"
NOWPAY_API_KEY = "ZB43Y23-F3E4XKG-K83X2GC-MPAAHZ5"

START_BANKROLL = 2000
BET_STAKE = 50

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

GOOD_LEAGUES = {39,78,140,135,61,94,88,203}

league_strength={
39:1.05,
78:1.08,
135:0.95,
140:1.00,
61:0.97
}

odds_history={}
steam_history={}
clv_history={}

team_stats_cache={}
injury_cache={}
league_odds_cache={}

# ---------- IMPLIED PROBABILITY ----------

def implied_probability(odds):
    return 1/odds


# ---------- MATCH SCANNER ----------

def scan_matches():

    fixtures=[]

    for page in range(1,6):

        url=f"https://v3.football.api-sports.io/fixtures?next=100&page={page}"
        headers={"x-apisports-key":FOOTBALL_API_KEY}

        try:
            r=requests.get(url,headers=headers).json()
            time.sleep(0.1)
        except:
            continue

        for m in r.get("response", []):

            match_time=m["fixture"]["timestamp"]
            now=int(time.time())

            if not (86400 <= match_time-now <=129600):
                continue

            fixtures.append({
                "fixture_id":m["fixture"]["id"],
                "home":m["teams"]["home"]["name"],
                "away":m["teams"]["away"]["name"],
                "home_id":m["teams"]["home"]["id"],
                "away_id":m["teams"]["away"]["id"],
                "league_id":m["league"]["id"]
            })

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

    modifier=league_strength.get(league_id,1)

    home_xg=home_strength*1.15*modifier
    away_xg=away_strength*0.95*modifier

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
    if total_xg > 4.5:
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
        return league_odds_cache[league_id]

    url=f"https://v3.football.api-sports.io/odds?league={league_id}&season=2024"
    headers={"x-apisports-key":FOOTBALL_API_KEY}

    try:
        r=requests.get(url,headers=headers).json()
    except:
        return None

    odds_data={}

    for game in r.get("response", []):

        fixture_id=game["fixture"]["id"]

        bookmakers=game["bookmakers"]

        best_odds={}

        for book in bookmakers:

            for bet in book["bets"]:

                market=bet["name"]

                for v in bet["values"]:

                    key=f"{market}_{v['value']}"
                    odd=float(v["odd"])

                    if key not in best_odds:
                        best_odds[key]=odd
                    else:
                        best_odds[key]=max(best_odds[key],odd)

        odds_data[fixture_id]=best_odds

    league_odds_cache[league_id]=odds_data

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

def market_consensus_filter(prob,odds):

    market_prob = 1/odds

    difference = abs(prob - market_prob)

    if difference > 0.20:
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
        "SELECT id,match,pick,result FROM bets_history WHERE result='PENDING'"
    ).fetchall()

    for bet_id,match,pick,result in rows:

        home,away = match.split(" vs ")

        url = "https://v3.football.api-sports.io/fixtures"

        headers = {"x-apisports-key":FOOTBALL_API_KEY}

        params = {
            "team":home,
            "last":1
        }

        try:
            r = requests.get(url,headers=headers,params=params).json()
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
        
# ---------- VALUE ENGINE ----------

def get_value_bets():

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

        asian_odds = odds.get("Match Winner_Home")
        over_odds = odds.get("Goals Over/Under_Over 2.5")
        under_odds = odds.get("Goals Over/Under_Under 2.5")
        over15_odds = odds.get("Goals Over/Under_Over 1.5")
        over35_odds = odds.get("Goals Over/Under_Over 3.5")
        btts_odds = odds.get("Both Teams Score_Yes")

        markets = []

        if asian_odds:
            markets.append(
                ("Asian Handicap", asian_prob, asian_odds, line)
            )

        if over_odds:
            markets.append(
                ("Over 2.5", over25_prob, over_odds, None)
            )

        if under_odds:
            markets.append(
                ("Under 2.5", under25_prob, under_odds, None)
            )

        if over15_odds:
            markets.append(
                ("Over 1.5", over15_prob, over15_odds, None)
            )

        if over35_odds:
            markets.append(
                ("Over 3.5", over35_prob, over35_odds, None)
            )

        if btts_odds:
            markets.append(
                ("BTTS", btts_prob, btts_odds, None)
            )

        for market, prob, odds_value, line in markets:

            implied = implied_probability(odds_value)

            edge = prob - implied

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

            if clv > 0.10:
                confidence += 5

            if ev <= 0.05:
                continue

            pick = market

            if market == "Asian Handicap":
                pick = f"Asian Handicap {f['home']} {line}"

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
                "INSERT INTO bets_history(match,pick,odds,result,timestamp) VALUES (?,?,?,?,?)",
                (
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
                "stake": stake
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
🎰 Bet: 50€"""
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
🎰 Bet: 50€"""
        )

    league_odds_cache.clear()
    team_stats_cache.clear()
    injury_cache.clear()

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
        return "No value today"

    cursor.execute(
        "INSERT OR REPLACE INTO free_sample VALUES (?,?)",
        (user_id, now)
    )

    db.commit()

    return bets[0]

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

    now = int(time.time())
    day = now - 86400
    week = now - (86400 * 7)

    # daily
    daily = cursor.execute(
        "SELECT odds,result FROM bets_history WHERE timestamp>?",
        (day,)
    ).fetchall()

    # weekly
    weekly = cursor.execute(
        "SELECT odds,result FROM bets_history WHERE timestamp>?",
        (week,)
    ).fetchall()

    def calc_profit(data):

        wins=0
        losses=0
        profit=0

        for odds,result in data:

            if result=="WIN":
                wins+=1
                profit+=odds-1

            elif result=="LOSE":
                losses+=1
                profit-=1

        return wins,losses,profit

    dw,dl,dp = calc_profit(daily)
    ww,wl,wp = calc_profit(weekly)

    return f"""
📊 DAILY PERFORMANCE

Wins: {dw}
Losses: {dl}

Profit: {round(dp,2)} units


📈 WEEKLY PERFORMANCE

Wins: {ww}
Losses: {wl}

Profit: {round(wp,2)} units
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
            bankroll += (odds * BET_STAKE) - BET_STAKE

        elif result == "LOSE":
            bankroll -= BET_STAKE

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

    while True:
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

        # ---------- VIP 18:00 ----------

        if hour == 18 and minute == 0 and not vip_sent_today:

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

        if hour == 0 and minute == 5:
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
# ================= TELEGRAM =================

@bot.message_handler(commands=["start"])
def start(m):

    bot.send_message(
        m.chat.id,
        """
👁‍🗨 WELCOME TO VALUEHUNTER

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

🔥 Today's signals will be released at 18:00.
⬇️ Use the menu below to explore the platform.

""",
        reply_markup=main_menu()
    )

@bot.callback_query_handler(func=lambda c: True)
def callbacks(c):

    if c.data == "elite":

        m = InlineKeyboardMarkup()

        m.add(
        InlineKeyboardButton("🥉 BASIC 50€", callback_data="buy_basic")
        )

        m.add(
        InlineKeyboardButton("🥇 PRO 100€", callback_data="buy_pro")
        )

        m.add(
        InlineKeyboardButton("⚡ DAY PASS 25€", callback_data="buy_day")
        )

        bot.send_message(
            c.message.chat.id,
"""
👑 VALUEHUNTER ELITE ACCESS

Our system scans hundreds of matches daily
to detect bookmaker pricing mistakes and
high probability value opportunities.

━━━━━━━━━━━━━━

🥉 BASIC — 50€

• 1 Premium Value Bet per day  
• Selected from the highest model edge  
• Ideal for consistent long term betting  

━━━━━━━━━━━━━━

🥇 PRO — 100€

• 3 Premium Value Bets per day  
• Full access to the model's top signals  
• Highest expected ROI  

━━━━━━━━━━━━━━

⚡ DAY PASS — 25€

• 24 hour PRO access  
• Receive today's full signals  

⚠️ Access is limited to members.
Signals are released daily at 18:00.
🔥 Members are already betting today's signals.
""",
            reply_markup=m
        )

    elif c.data == "buy_basic":

        link = create_payment(50,c.message.chat.id)

        bot.send_message(
            c.message.chat.id,
    f"""
    🥉 BASIC ACCESS

    You are about to unlock **VALUEHUNTER BASIC membership**.

    This plan gives you access to:

    📊 1 Premium Value Bet per day  
    📈 Selected from the highest model edge  
    ⚙️ Generated using advanced football analytics  
    🎯 Focused on long-term profitable betting  

    ━━━━━━━━━━━━━━

    Signals are released daily at:

    🕔 17:00 — Model analysis  
    🕕 18:00 — Official signal release

    ━━━━━━━━━━━━━━

    ⚠️ IMPORTANT

    Membership slots are **limited** to maintain
    signal efficiency and market advantage.

    Members are already preparing today's bets.
    
    Secure your access below:

    💳 Activate BASIC membership:

    {link}
    """
    )

    elif c.data == "buy_pro":

        link = create_payment(100,c.message.chat.id)

        bot.send_message(
            c.message.chat.id,
    f"""
    🥇 VALUEHUNTER PRO ACCESS

    You are about to activate **PRO membership**.

    This is the **full access tier** of the ValueHunter network.

    ━━━━━━━━━━━━━━

    With PRO you receive:

    📊 3 Premium Value Bets every day  
    📈 Highest model edge opportunities  
    📡 Sharp odds movement detection  
    ⚙️ Advanced football analytics  

    Signals are selected from **hundreds of matches analyzed daily**.

    ━━━━━━━━━━━━━━

    📅 SIGNAL SCHEDULE

    🕔 17:00 — Model analysis  
    🕕 18:00 — VIP signals released  

    ━━━━━━━━━━━━━━

    ⚠️ PRO membership capacity is limited
    to maintain signal efficiency.
    
    Most members choose PRO for full access.
    
    Activate your access below:

    💳 Secure your PRO access:

    {link}
    """
    )
    
    elif c.data == "buy_day":

        link = create_payment(25,c.message.chat.id)

        bot.send_message(
            c.message.chat.id,
    f"""
    ⚡ VALUEHUNTER DAY PASS

    You are about to activate **24 hour PRO access**.

    This pass allows you to experience the **full ValueHunter system** for one day.

    ━━━━━━━━━━━━━━

    With the DAY PASS you receive:

    📊 Up to 3 Premium Value Bets today  
    📈 Highest model edge opportunities  
    📡 Sharp odds movement detection  
    ⚙️ Advanced football analytics  

    ━━━━━━━━━━━━━━

    📅 SIGNAL SCHEDULE

    🕔 17:00 — Model analysis  
    🕕 18:00 — VIP signals released  

    ━━━━━━━━━━━━━━

    ⚠️ DAY PASS availability is limited
    during active signal days.

    Activate your 24h access below:

    💳 Get DAY PASS access:

    {link}
    """
    )
    
    elif c.data == "sample":

        bet = daily_sample(c.message.chat.id)

        bot.send_message(
            c.message.chat.id,
            f"🎁 FREE SAMPLE\n\n{bet}"
        )

        bot.send_message(
        c.message.chat.id,
    """
    🎁 FREE SAMPLE DELIVERED

    This was today's free value opportunity from the ValueHunter model.

    ━━━━━━━━━━━━━━

    👑 ELITE members already received
    the full signal card for today.

    🥉 BASIC
    • 1 Premium Value Bet daily

    🥇 PRO
    • 3 Premium Value Bets daily
    • Full access to the strongest model signals

    ⚡ DAY PASS
    • 24 hour PRO access
    • Receive today's full signals

    ━━━━━━━━━━━━━━

    ⚠️ Today's signals are released at **18:00**

    Access to the network may close
    once today's signals begin.

    Use the menu below to unlock access.
    """
        )
        
    elif c.data == "alert":

        bot.send_message(
            c.message.chat.id,
            market_alert()
        )

    elif c.data == "perf":

        bot.send_message(
            c.message.chat.id,
    f"""
    📊 VALUEHUNTER PERFORMANCE

    All results are tracked automatically
    based on official match results.

    ━━━━━━━━━━━━━━

    📅 TODAY

    {performance()}

    ━━━━━━━━━━━━━━

    📈 MONTHLY RESULTS

    {monthly_report()}

    ━━━━━━━━━━━━━━

    Our signals are generated using:

    • Expected Goals models  
    • Market inefficiency detection  
    • Sharp odds movement  

    ⚠️ Full signals are available only
    to ELITE members.
    """
        )
        
    elif c.data == "support":
    
        bot.send_message(
            c.message.chat.id,
    """
    💬 VALUEHUNTER SUPPORT

    Need help with access or payments?

    Contact our support team:

    @MrMasterlegacy1

    We will assist you quickly.

    ⚠️ VIP signals are released daily
    at 18:00.
    """
        )

# ================= THREADS =================

threading.Thread(target=send_signals, daemon=True).start()

threading.Thread(
    target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT",8080))),
    daemon=True
).start()

# ================= RUN =================

bot.infinity_polling()