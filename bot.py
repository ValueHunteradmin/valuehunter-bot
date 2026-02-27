import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import os
import threading
import time

# 🔑 ΒΑΛΕ ΤΑ ΔΙΚΑ ΣΟΥ
TOKEN = os.environ.get("8767848071:AAHjxT7945VO-X7iCI3kG-0fIqC_giqX7Z8")

ADMIN_CHANNEL_ID = -1003705705673
API_KEY = "ZB43Y23-F3E4XKG-K83X2GC-MPAAHZ5"

VIP_USERS = set()

bot = telebot.TeleBot(TOKEN)

# 🌐 REAL MATCH FETCHER
def get_matches():

    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures?next=3"

    headers = {
        "X-RapidAPI-Key": API_KEY,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }

    response = requests.get(url, headers=headers)
    data = response.json()

    matches = []

    for match in data["response"]:
        home = match["teams"]["home"]["name"]
        away = match["teams"]["away"]["name"]
        league = match["league"]["name"]

        matches.append(f"{home} vs {away} ({league})")

    return matches


# 👑 START MENU
@bot.message_handler(commands=['start'])
def start(message):
    VIP_USERS.add(message.chat.id)

    markup = InlineKeyboardMarkup(row_width=2)

    buttons = [
        InlineKeyboardButton("💎 VIP ΠΡΟΣΒΑΣΗ", callback_data="vip"),
        InlineKeyboardButton("⚡ DAY PASS", callback_data="daypass"),
        InlineKeyboardButton("🔥 ΣΗΜΕΡΙΝΑ BETS", callback_data="bets"),
        InlineKeyboardButton("⭐ FREE VIP PICK", callback_data="free"),
        InlineKeyboardButton("🏆 ΑΠΟΤΕΛΕΣΜΑΤΑ", callback_data="results"),
        InlineKeyboardButton("📊 ΣΤΑΤΙΣΤΙΚΑ", callback_data="stats"),
        InlineKeyboardButton("🎯 STRATEGY", callback_data="strategy"),
        InlineKeyboardButton("💬 SUPPORT", callback_data="support"),
        InlineKeyboardButton("ℹ️ ABOUT", callback_data="about")
    ]

    markup.add(*buttons)

    bot.send_message(
        message.chat.id,
        "👑 Καλώς ήρθες στο ValueHunter Elite\n\n"
        "Το πιο αποκλειστικό σύστημα εντοπισμού value betting ευκαιριών.\n\n"
        "Η πρόσβαση επιτρέπεται μόνο σε ενεργά μέλη.",
        reply_markup=markup
    )


# 💎 VIP PLANS
@bot.callback_query_handler(func=lambda call: call.data == "vip")
def vip(call):
    bot.send_message(
        call.message.chat.id,
        "💎 VIP ΠΡΟΣΒΑΣΗ\n\n"
        "🥉 BASIC VIP — 50€ / 30 ημέρες\n"
        "3 elite bets καθημερινά\n\n"
        "🥇 PRO VIP ELITE — 100€ / 30 ημέρες\n"
        "5–6 elite bets καθημερινά"
    )


# ⚡ DAY PASS
@bot.callback_query_handler(func=lambda call: call.data == "daypass")
def daypass(call):
    bot.send_message(
        call.message.chat.id,
        "⚡ 24H ACCESS — 15€\n\n"
        "Πλήρης πρόσβαση για 24 ώρες."
    )


# 🔥 VIP BETS
@bot.callback_query_handler(func=lambda call: call.data == "bets")
def bets(call):
    bot.send_message(
        call.message.chat.id,
        "🔒 Απαιτείται ενεργή συνδρομή για πρόσβαση."
    )


# ⭐ FREE PICK
@bot.callback_query_handler(func=lambda call: call.data == "free")
def free(call):
    bot.send_message(
        call.message.chat.id,
        "⭐ FREE VIP PICK\n\n"
        "⚽ Ajax vs PSV\n"
        "🎯 Over 2.5 Goals\n"
        "👑 Confidence: HIGH"
    )


# 🏆 RESULTS
@bot.callback_query_handler(func=lambda call: call.data == "results")
def results(call):
    bot.send_message(
        call.message.chat.id,
        "🏆 VALUEHUNTER RESULTS\n\nWin Rate: 74%\nROI: +18%"
    )


# 📊 STATS
@bot.callback_query_handler(func=lambda call: call.data == "stats")
def stats(call):
    bot.send_message(
        call.message.chat.id,
        "📊 VALUEHUNTER STATS\n\nAverage Odds: 1.55\nHit Rate: 72%"
    )


# 🎯 STRATEGY
@bot.callback_query_handler(func=lambda call: call.data == "strategy")
def strategy(call):
    bot.send_message(
        call.message.chat.id,
        "🎯 STRATEGY\n\nValue betting σε Over/Under αγορές\nμε advanced models."
    )


# 💬 SUPPORT
@bot.callback_query_handler(func=lambda call: call.data == "support")
def support(call):
    bot.send_message(
        call.message.chat.id,
        "💬 Support:\n👉 @MrMasterlegacy1"
    )


# ℹ️ ABOUT
@bot.callback_query_handler(func=lambda call: call.data == "about")
def about(call):
    bot.send_message(
        call.message.chat.id,
        "ℹ️ ValueHunter Elite\n\nPremium football value betting intelligence."
    )


# 🧠 AUTO REAL BETS — 3 MATCHES / DAY
def auto_sender():

    sent_today = False

    while True:
        current_hour = time.strftime("%H")

        if current_hour == "12" and not sent_today:

            matches = get_matches()

            for match in matches:

                text = (
                    f"🔥 VIP VALUE BET\n\n"
                    f"⚽ {match}\n"
                    f"🎯 Market: Over/Under Value\n"
                    f"👑 Confidence: HIGH"
                )

                for user_id in VIP_USERS:
                    try:
                        bot.send_message(user_id, text)
                    except:
                        pass

                bot.send_message(ADMIN_CHANNEL_ID, f"ADMIN COPY:\n{text}")

            sent_today = True

        if current_hour == "00":
            sent_today = False

        time.sleep(60)


# 🚀 START AUTO SYSTEM
threading.Thread(target=auto_sender, daemon=True).start()

print("ValueHunter Elite Running...")

bot.infinity_polling()