import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
import threading
import time

TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_CHANNEL_ID = -1003705705673

VIP_USERS = set()

bot = telebot.TeleBot(TOKEN)

# 🔥 ADMIN TEST
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
        "Το πιο αποκλειστικό σύστημα value betting στο ποδόσφαιρο.",
        reply_markup=markup
    )


# ⭐ FREE PICK
@bot.callback_query_handler(func=lambda call: call.data == "free")
def free(call):
    bot.send_message(
        call.message.chat.id,
        "⭐ FREE VIP PICK\n\n⚽ Ajax vs PSV\n🎯 Over 2.5 Goals"
    )


# 🔥 MANUAL VIP SEND
@bot.message_handler(commands=['sendvip'])
def send_vip(message):
    text = "🔥 TEST VIP BET από ValueHunter"

    for user_id in VIP_USERS:
        bot.send_message(user_id, text)


# 🧠 AUTO SYSTEM — 3 BETS PER DAY
def auto_sender():

    sent_today = set()

    while True:
        current_hour = time.strftime("%H")

        bets = {
            "12": "⚽ BET 1\nOver 2.5 Goals",
            "15": "⚽ BET 2\nUnder 3.5 Goals",
            "18": "⚽ BET 3\nOver 1.5 Goals"
        }

        if current_hour in bets and current_hour not in sent_today:

            text = f"🔥 VIP VALUE BET\n\n{bets[current_hour]}"

            # 👉 Στέλνει στους VIP
            for user_id in VIP_USERS:
                try:
                    bot.send_message(user_id, text)
                except:
                    pass

            # 👉 Στέλνει και στο ADMIN CHANNEL
            bot.send_message(ADMIN_CHANNEL_ID, f"ADMIN COPY:\n{text}")

            sent_today.add(current_hour)

        time.sleep(60)


# 🚀 START AUTO SYSTEM
threading.Thread(target=auto_sender, daemon=True).start()

print("ValueHunter Elite Running...")

bot.infinity_polling()