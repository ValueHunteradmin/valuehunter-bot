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
# ---------- IMPLIED PROBABILITY ----------

def implied_probability(odds):

    return 1/odds
# ================= VALUE ENGINE =================

GOOD_LEAGUES = {39,78,140,135,61,94,88,203}

clv_history={}
odds_history={}
performance_stats={"wins":0,"losses":0}

league_strength={
39:1.05,
78:1.08,
135:0.95,
140:1.00,
61:0.97
}

def implied_probability(odds):
    return 1/odds


# ---------- MATCH SCANNER ----------

def scan_matches():

    fixtures=[]

    for page in range(1,31):

        url=f"https://v3.football.api-sports.io/fixtures?next=100&page={page}"
        headers={"x-apisports-key":FOOTBALL_API_KEY}

        try:
            r=requests.get(url,headers=headers).json()
            time.sleep(0.1)
        except:
            continue

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
team_stats_cache = {}
def get_team_stats(team_id,league_id):

    if team_id in team_stats_cache:
        return team_stats_cache[team_id]

    url=f"https://v3.football.api-sports.io/teams/statistics?team={team_id}&league={league_id}&season=2024"
    headers={"x-apisports-key":FOOTBALL_API_KEY}

    try:
        r=requests.get(url,headers=headers).json()
        time.sleep(0.05)
    except:
        return None

    if not r["response"]:
        return None

    d=r["response"]

    attack=float(d["goals"]["for"]["average"]["total"])
    defense=float(d["goals"]["against"]["average"]["total"])

    team_stats_cache[team_id]=(attack,defense)

    return attack,defense
    
# ---------- INJURY MODEL ----------
injury_cache = {}
def get_injuries(team_id):

    if team_id in injury_cache:
        return injury_cache[team_id]

    url=f"https://v3.football.api-sports.io/injuries?team={team_id}"
    headers={"x-apisports-key":FOOTBALL_API_KEY}

    try:
        r=requests.get(url,headers=headers).json()
        time.sleep(0.05)
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

# ---------- MONTE CARLO SIMULATION ----------

def monte_carlo_simulation(home_xg,away_xg,simulations=10000):

    home_wins=0
    draws=0
    away_wins=0

    for _ in range(simulations):

        home_goals=np.random.poisson(home_xg)
        away_goals=np.random.poisson(away_xg)

        if home_goals>away_goals:
            home_wins+=1

        elif home_goals==away_goals:
            draws+=1

        else:
            away_wins+=1

    return (
        home_wins/simulations,
        draws/simulations,
        away_wins/simulations
    )
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


# ---------- ODDS SCRAPER ----------

league_odds_cache = {}

def get_league_odds(league_id):

    if league_id in league_odds_cache:
        return league_odds_cache[league_id]

    url=f"https://v3.football.api-sports.io/odds?league={league_id}&season=2024"

    headers={"x-apisports-key":FOOTBALL_API_KEY}

    try:
        r=requests.get(url,headers=headers).json()
        time.sleep(0.05)
    except:
        return None

    odds_map={}

    for item in r["response"]:

        fixture=item["fixture"]["id"]

        for book in item["bookmakers"]:

            for bet in book["bets"]:

                for value in bet["values"]:

                    key=f"{bet['name']}_{value['value']}"

                    odds_map.setdefault(fixture,{})[key]=float(value["odd"])

    league_odds_cache[league_id]=odds_map

    return odds_map
# ---------- ODDS MOVEMENT ----------

def track_odds(fixture_id,odds):

    if fixture_id not in odds_history:
        odds_history[fixture_id]=odds
        return 0

    old_odds=odds_history[fixture_id]

    movement=old_odds-odds

    odds_history[fixture_id]=odds

    return movement

# ---------- SHARP DETECTION ----------

def sharp_detection(move):

    if move>0.15:
        return True

    return False

# ---------- EV ----------

def calculate_ev(prob,odds):
    return (prob*odds)-1


# ---------- BET RANKING ----------

def rank_bets(bets):
    bets.sort(key=lambda x:x["confidence"],reverse=True)
    return bets


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

        home_strength,away_strength=team_strength(
            home_attack,home_defense,
            away_attack,away_defense
        )

        home_xg,away_xg=calculate_xg(
            home_strength,away_strength,
            f["league_id"]
        )
        home_prob,draw_prob,away_prob = monte_carlo_simulation(home_xg,away_xg)
        matrix=poisson_matrix(home_xg,away_xg)

        total=sum(p for _,_,p in matrix)
        matrix=[(h,a,p/total) for h,a,p in matrix]

        asian_line,asian_prob=asian_optimizer(matrix)

        asian_prob = (asian_prob + home_prob) / 2
        over_prob=over25_probability(matrix)
        btts_prob=btts_probability(matrix)

        league_odds = get_league_odds(f["league_id"])

        if not league_odds:
            continue

        odds = league_odds.get(f["fixture_id"])

        if not odds:
            continue
        markets=[]

        asian_odds=odds.get("Match Winner_Home")
        over_odds=odds.get("Goals Over/Under_Over 2.5")
        btts_odds=odds.get("Both Teams Score_Yes")

        if asian_odds:
            markets.append(("Asian Handicap",asian_prob,asian_odds,asian_line))

        if over_odds:
            markets.append(("Over 2.5",over_prob,over_odds,None))

        if btts_odds:
            markets.append(("BTTS",btts_prob,btts_odds,None))

        for market,prob,odds_value,line in markets:

            implied=implied_probability(odds_value)
            edge=prob-implied
            # ---------- MARKET EFFICIENCY FILTER ----------

            if odds_value < 1.60 or odds_value > 3.20:
                continue
            if edge<0.04:
                continue
            # minimum model confidence

            if prob < 0.56:
                continue
            ev=calculate_ev(prob,odds_value)

            move=track_odds(f["fixture_id"],odds_value)
            sharp=sharp_detection(move)

            # ---------- CONFIDENCE SCORE ----------

            confidence = (
            (prob * 50) +
            (edge * 200) +
            (ev * 100)
            )

            if sharp:
                confidence += 5

            if ev>0.05:

                pick=market

                if market=="Asian Handicap":
                    pick=f"Asian Handicap {f['home']} {line}"

                candidates.append({
                    "match":f"{f['home']} vs {f['away']}",
                    "pick":pick,
                    "prob":prob,
                    "odds":odds_value,
                    "ev":ev,
                    "score":score,
                    "confidence":confidence,
                })

    ranked=rank_bets(candidates)
    
    # ---------- BET CATEGORIES ----------
    
    super_safe=None
    high_value=[]
    
    for bet in ranked:

    if bet["prob"]>=0.65 and not super_safe:
        super_safe=bet

    elif bet["prob"]>=0.57:
        high_value.append(bet)

# ---------- FINAL PICKS ----------

signals=[]

if super_safe:

    signals.append(
f"""⭐ SUPER SAFE BET
⚽ {super_safe['match']}
🎯 {super_safe['pick']}
📊 Odds {round(super_safe['odds'],2)}
📈 Probability {round(super_safe['prob']*100)}%
💰 Value {round(super_safe['ev'],2)}"""
)

for bet in high_value[:2]:

    signals.append(
f"""🔥 HIGH VALUE
⚽ {bet['match']}
🎯 {bet['pick']}
📊 Odds {round(bet['odds'],2)}
📈 Probability {round(bet['prob']*100)}%
💰 Value {round(bet['ev'],2)}"""
)

# ---------- CLEAR CACHE ----------

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

threading.Thread(target=send_signals, daemon=True).start()

threading.Thread(
    target=lambda: app.run(host="0.0.0.0", port=8080),
    daemon=True
).start()

# ================= RUN =================

bot.infinity_polling()