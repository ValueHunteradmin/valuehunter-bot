import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import os
import threading
import time
from flask import Flask, request

TOKEN = "8767848071:AAHjxT7945VO-X7iCI3kG-0fIqC_giqX7Z8"
ADMIN_CHANNEL_ID = -1003705705673
API_KEY = "2f8c79b66ceed85aaf20322308f11e5a"

VIP_USERS = set()
PENDING_PAYMENTS = set()  # 👈 ΠΡΟΣΘΗΚΗ

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
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


# 💳 CREATE PAYMENT LINK
def create_payment_link(amount, user_id):

    url = "https://api.nowpayments.io/v1/invoice"

    headers = {
        "x-api-key": "ZB43Y23-F3E4XKG-K83X2GC-MPAAHZ5",
        "Content-Type": "application/json"
    }

    data = {
        "price_amount": amount,
        "price_currency": "eur",
        "pay_currency": "sol",
        "order_id": str(user_id),
        "order_description": "ValueHunter VIP Subscription"
    }

    response = requests.post(url, json=data, headers=headers)
    result = response.json()

    return result.get("invoice_url")


# 👑 START MENU
@bot.message_handler(commands=['start'])
def start(message):

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
        "Το πιο αποκλειστικό σύστημα εντοπισμού value betting ευκαιριών.",
        reply_markup=markup
    )


# 💳 VIP PAYMENT MENU
@bot.callback_query_handler(func=lambda call: call.data == "vip")
def vip(call):

    markup = InlineKeyboardMarkup(row_width=1)

    buttons = [
        InlineKeyboardButton("🥉 Πλήρωσε BASIC VIP — 50€", callback_data="pay_basic"),
        InlineKeyboardButton("🥇 Πλήρωσε PRO VIP — 100€", callback_data="pay_pro"),
        InlineKeyboardButton("⚡ Πλήρωσε DAY PASS — 15€", callback_data="pay_day")
    ]

    markup.add(*buttons)

    bot.send_message(
        call.message.chat.id,
        "💎 Επίλεξε πακέτο για ενεργοποίηση VIP:",
        reply_markup=markup
    )


# 💳 PAYMENT HANDLERS (με pending)
@bot.callback_query_handler(func=lambda call: call.data == "pay_basic")
def pay_basic(call):
    PENDING_PAYMENTS.add(call.message.chat.id)  # 👈 ΠΡΟΣΘΗΚΗ

    link = create_payment_link(50, call.message.chat.id)
    bot.send_message(call.message.chat.id, f"💳 Πληρωμή BASIC VIP\n\n🔗 {link}")


@bot.callback_query_handler(func=lambda call: call.data == "pay_pro")
def pay_pro(call):
    PENDING_PAYMENTS.add(call.message.chat.id)

    link = create_payment_link(100, call.message.chat.id)
    bot.send_message(call.message.chat.id, f"💳 Πληρωμή PRO VIP\n\n🔗 {link}")


@bot.callback_query_handler(func=lambda call: call.data == "pay_day")
def pay_day(call):
    PENDING_PAYMENTS.add(call.message.chat.id)

    link = create_payment_link(15, call.message.chat.id)
    bot.send_message(call.message.chat.id, f"💳 Πληρωμή DAY PASS\n\n🔗 {link}")


# 🔒 VIP LOCK — BETS
@bot.callback_query_handler(func=lambda call: call.data == "bets")
def bets(call):

    if call.message.chat.id not in VIP_USERS:
        bot.send_message(
            call.message.chat.id,
            "🔒 Απαιτείται ενεργή VIP συνδρομή."
        )
        return

    bot.send_message(
        call.message.chat.id,
        "🔥 VIP BETS θα εμφανιστούν εδώ."
    )


# ⭐ FREE PICK
@bot.callback_query_handler(func=lambda call: call.data == "free")
def free(call):
    bot.send_message(
        call.message.chat.id,
        "⭐ FREE VIP PICK\n\n⚽ Ajax vs PSV\n🎯 Over 2.5 Goals"
    )


# 💬 SUPPORT
@bot.callback_query_handler(func=lambda call: call.data == "support")
def support(call):
    bot.send_message(call.message.chat.id, "💬 Support:\n👉 @MrMasterlegacy1")

@app.route('/payment-webhook', methods=['POST'])
def payment_webhook():

    data = request.json
    user_id = data.get("order_id")

    if user_id:
        VIP_USERS.add(int(user_id))

        bot.send_message(
            int(user_id),
            "👑 Η πληρωμή επιβεβαιώθηκε!\nVIP ενεργοποιήθηκε 🔓"
        )

    return "OK"
# 🧠 AUTO REAL BETS — ΜΟΝΟ VIP
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
                    bot.send_message(user_id, text)

                bot.send_message(ADMIN_CHANNEL_ID, f"ADMIN COPY:\n{text}")

            sent_today = True

        if current_hour == "00":
            sent_today = False

        time.sleep(60)


# 🚀 START AUTO SYSTEM
threading.Thread(target=auto_sender, daemon=True).start()

print("ValueHunter Elite Running...")
def run_web():
    app.run(host="0.0.0.0", port=8000)

threading.Thread(target=run_web).start()
bot.infinity_polling()