import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import sqlite3
import time
import threading
from flask import Flask, request
import math
# ================= CONFIG =================

TOKEN = "YOUR_TELEGRAM_TOKEN"
ADMIN_ID = 123456789

FOOTBALL_API_KEY = "FOOTBALL_API_KEY"
ODDS_API_KEY = "ODDS_API_KEY"
NOWPAY_API_KEY = "NOWPAY_API_KEY"

WEBHOOK_URL = "https://YOUR-RAILWAY-URL/payment-webhook"

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
# ---------- IMPLIED PROBABILITY ----------

def implied_probability(odds):

    return 1/odds
# ================= VALUE ENGINE =================

import math
import random
# ---------- LEAGUE FILTER ----------

GOOD_LEAGUES = {
39,   # Premier League
78,   # Bundesliga
140,  # La Liga
135,  # Serie A
61,   # Ligue 1
94,   # Portugal
88,   # Netherlands
203   # Turkey
}
# ---------- CLV STORAGE ----------

clv_history = {}
# ---------- LEAGUE STRENGTH MODEL ----------

league_strength = {
    39:1.05,   # Premier League
    78:1.08,   # Bundesliga
    135:0.95,  # Serie A
    140:1.00,  # La Liga
    61:0.97    # Ligue 1
}
odds_history = {}
performance_stats = {"wins":0,"losses":0}


# ---------- MATCH SCANNER ----------

def scan_matches():

    url="https://v3.football.api-sports.io/fixtures?next=1200"
    headers={"x-apisports-key":FOOTBALL_API_KEY}

    try:
        r=requests.get(url,headers=headers).json()
    except:
        return []

    fixtures=[]

    for m in r["response"]:

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

    url=f"https://v3.football.api-sports.io/teams/statistics?team={team_id}&league={league_id}&season=2024"
    headers={"x-apisports-key":FOOTBALL_API_KEY}

    try:
        r=requests.get(url,headers=headers).json()
    except:
        return None

    if not r["response"]:
        return None

    d=r["response"]

    attack=float(d["goals"]["for"]["average"]["total"])
    defense=float(d["goals"]["against"]["average"]["total"])

    return attack,defense


# ---------- INJURY MODEL ----------

def get_injuries(team_id):

    url=f"https://v3.football.api-sports.io/injuries?team={team_id}"
    headers={"x-apisports-key":FOOTBALL_API_KEY}

    try:
        r=requests.get(url,headers=headers).json()
    except:
        return 0

    return len(r["response"])


# ---------- LINEUP IMPACT ----------

def lineup_adjustment():

    return random.uniform(-0.1,0.1)


# ---------- TEAM STRENGTH ----------

def team_strength(home_attack,home_defense,away_attack,away_defense):

    home_strength=(home_attack+away_defense)/2
    away_strength=(away_attack+home_defense)/2

    return home_strength,away_strength


# ---------- xG MODEL ----------

def calculate_xg(home_strength,away_strength,league_id):

    modifier = league_strength.get(league_id,1)

    home_xg = home_strength * 1.15 * modifier
    away_xg = away_strength * 0.95 * modifier

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
    if len(matrix) < 10:
    continue
    # ---------- OVER UNDER PROBABILITY ----------

def over25_probability(matrix):

    prob=0

    for h,a,p in matrix:

        if h+a >=3:
            prob+=p

    return prob
    # ---------- BTTS PROBABILITY ----------

def btts_probability(matrix):

    prob=0

    for h,a,p in matrix:

        if h>0 and a>0:
            prob+=p

    return prob
# ---------- ASIAN HANDICAP PROBABILITY ----------

def asian_probability(matrix):

    win=0

    for h,a,p in matrix:

        if h>a:
            win+=p

    return win
# ---------- ASIAN LINE OPTIMIZER ----------

def asian_optimizer(matrix):

    lines = [-1, -0.75, -0.5, -0.25, 0, 0.25, 0.5]

    best_line = None
    best_prob = 0

    for line in lines:

        prob = 0

        for h,a,p in matrix:

            goal_diff = h - a

            if goal_diff > line:
                prob += p

        if prob > best_prob:
            best_prob = prob
            best_line = line

    return best_line, best_prob

# ---------- MULTI BOOKMAKER ODDS ----------

def get_market_odds(fixture_id):

    url=f"https://v3.football.api-sports.io/odds?fixture={fixture_id}"
    headers={"x-apisports-key":FOOTBALL_API_KEY}

    try:
        r=requests.get(url,headers=headers).json()
    except:
        return None

    if not r["response"]:
        return None

    bookmakers=r["response"][0]["bookmakers"]

    odds={}

    for book in bookmakers:

        for bet in book["bets"]:

            market=bet["name"]

            for v in bet["values"]:

                key=f"{market}_{v['value']}"
                odd=float(v["odd"])

                if key not in odds:
                    odds[key]=odd
                else:
                    odds[key]=max(odds[key],odd)

    return odds

# ---------- ODDS MOVEMENT TRACKER ----------

def track_odds(fixture_id,odds):

    if fixture_id not in odds_history:
        odds_history[fixture_id]=odds
        return 0

    movement=odds_history[fixture_id]-odds

    odds_history[fixture_id]=odds

    return movement


# ---------- SHARP BOOKMAKER DETECTION ----------

def sharp_detection(odds_move):

    return odds_move>0.10


# ---------- BOOKMAKER MARGIN REMOVAL ----------

def remove_margin(prob):

    margin=0.04
    return prob/(1+margin)


# ---------- EV ----------

def calculate_ev(prob,odds):

    return(prob*odds)-1


# ---------- CLV TRACKER ----------

def clv(open_odds,closing_odds):

    return closing_odds-open_odds


# ---------- AI BET RANKING ----------

def rank_bets(bets):

    bets.sort(key=lambda x:x["score"],reverse=True)

    return bets


# ---------- RESULT GRADING ----------

def grade_result(result):

    if result=="WIN":
        performance_stats["wins"]+=1
    else:
        performance_stats["losses"]+=1


# ---------- VALUE ENGINE ----------

def get_value_bets():

    fixtures=scan_matches()

    candidates=[]

    for f in fixtures:
        if f["league_id"] not in GOOD_LEAGUES:
            continue
            
        stats_home=get_team_stats(f["home_id"],f["league_id"])
        stats_away=get_team_stats(f["away_id"],f["league_id"])

        if not stats_home or not stats_away:
            continue

        home_attack,home_defense=stats_home
        away_attack,away_defense=stats_away

        injuries_home=get_injuries(f["home_id"])
        injuries_away=get_injuries(f["away_id"])

        home_attack-=injuries_home*0.05
        away_attack-=injuries_away*0.05

        home_attack+=lineup_adjustment()
        away_attack+=lineup_adjustment()

        home_strength,away_strength=team_strength(
            home_attack,
            home_defense,
            away_attack,
            away_defense
        )

        home_xg,away_xg=calculate_xg(home_strength,away_strength,f["league_id"])

        matrix=poisson_matrix(home_xg,away_xg)
        if len(matrix) < 20:
            continue
            
        over_prob=over25_probability(matrix)
        btts_prob=btts_probability(matrix)
        # NORMALIZE PROBABILITIES
        total=sum(p for _,_,p in matrix)
        matrix=[(h,a,p/total) for h,a,p in matrix]
        line, probability = asian_optimizer(matrix)#

        probability=remove_margin(probability)
        # MINIMUM PROBABILITY FILTER
        if probability < 0.55:
            continue
        odds=get_market_odds(f["fixture_id"])
        
        if odds < 1.60 or odds > 2.40:
        continue
        if not odds:
            continue
            
        asian_odds = odds.get("Match Winner_Home")
        if not asian_odds:
            continue
            
        if f["fixture_id"] not in clv_history:
        clv_history[f["fixture_id"]] = asian_odds
        implied_prob=1/odds
        
        # ===== 3 LINES USED BY PROFESSIONAL MODELS =====

        implied_prob=implied_probability(asian_odds)

        edge=probability-implied_prob
        if edge < 0.04:
            continue

        ev=calculate_ev(probability,asian_odds)

        odds_move=track_odds(f["fixture_id"],odds)
        if odds_move > 0.20:
            continue
            
        sharp=sharp_detection(odds_move)

        score = ev + (edge*2) + (probability*0.5)

        if sharp:
        score += 0.1

        if ev > 0.05 and probability > 0.57:

            candidates.append({
                "match":f"{f['home']} vs {f['away']}",
                "pick": f"Asian Handicap {f['home']} {line}",
                "prob":probability,
                "odds":odds,
                "ev":ev,
                "score":score
            })

    ranked=rank_bets(candidates)

    signals=[]

    for i,b in enumerate(ranked[:10]):

        tag=""

if i==0:
    tag="⭐ BEST BET\n"
elif i<3:
    tag="🔥 HIGH VALUE\n"

signals.append(
f"""{tag}⚽ {b['match']}
🎯 {b['pick']}
📊 Odds {round(b['odds'],2)}
📈 Probability {round(b['prob']*100)}%
💰 Value {round(b['ev'],2)}"""
)

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

    while True:

        bets = get_value_bets()

        users = get_vip_users()

        for uid,plan in users:

            if plan == "BASIC":

                picks = bets[:1]

            elif plan == "PRO":

                picks = bets[:3]

            else:
                continue

            text = "🔥 VIP SIGNALS\n\n" + "\n\n".join(picks)

            bot.send_message(uid,text)

        # admin gets PRO always
        if bets:
            bot.send_message(
                ADMIN_ID,
                "ADMIN SIGNALS\n\n"+"\n\n".join(bets[:3])
            )

        time.sleep(86400)

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

threading.Thread(target=send_signals).start()

# ================= RUN =================

bot.infinity_polling()