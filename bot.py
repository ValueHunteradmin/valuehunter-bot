import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import os

TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_CHANNEL_ID = -1003705705673
VIP_USERS = set()
bot = telebot.TeleBot(TOKEN)
@bot.message_handler(commands=['testadmin'])
def test_admin(message):
    bot.send_message(ADMIN_CHANNEL_ID, "🔥 Test message από ValueHunter")

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
        InlineKeyboardButton("ℹ️ ΣΧΕΤΙΚΑ", callback_data="about")
    ]

    markup.add(*buttons)

    bot.send_message(
        message.chat.id,
        "👑 Καλώς ήρθες στο ValueHunter Elite\n\n"
        "Το πιο αποκλειστικό σύστημα value betting στο ποδόσφαιρο.\n\n"
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
        "⚽ Match: Ajax vs PSV\n"
        "🎯 Pick: Over 2.5 Goals\n"
        "💰 Odds: 1.62\n"
        "👑 Confidence: HIGH\n\n"
        "Για πλήρη πρόσβαση ενεργοποίησε VIP."
    )

# 🏆 RESULTS
@bot.callback_query_handler(func=lambda call: call.data == "results")
def results(call):
    bot.send_message(
        call.message.chat.id,
        "🏆 VALUEHUNTER RESULTS\n\n"
        "Win Rate: 74%\n"
        "ROI: +18%"
    )

# 📊 STATS
@bot.callback_query_handler(func=lambda call: call.data == "stats")
def stats(call):
    bot.send_message(
        call.message.chat.id,
        "📊 VALUEHUNTER STATS\n\n"
        "Average Odds: 1.55\n"
        "Hit Rate: 72%"
    )

# 🎯 STRATEGY
@bot.callback_query_handler(func=lambda call: call.data == "strategy")
def strategy(call):
    bot.send_message(
        call.message.chat.id,
        "🎯 STRATEGY\n\n"
        "Value betting σε Over/Under αγορές\n"
        "με advanced goal models."
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
        "ℹ️ ValueHunter Elite\n\n"
        "Premium football value betting intelligence."
    )

print("ValueHunter Elite Running...") 
@bot.message_handler(commands=['sendvip'])
def send_vip(message):
    text = "🔥 TEST VIP BET από ValueHunter"

    for user_id in VIP_USERS:
        bot.send_message(user_id, text) 
        import threading
import time

def auto_sender():
    while True:
        text = "🔥 AUTO VIP BET από ValueHunter"

        for user_id in VIP_USERS:
            try:
                bot.send_message(user_id, text)
            except:
                pass

        time.sleep(60)  # κάθε 60 δευτερόλεπτα

# ξεκινά το auto system
threading.Thread(target=auto_sender).start()
bot.infinity_polling()
