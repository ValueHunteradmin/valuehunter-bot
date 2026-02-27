from flask import Flask, request
import telebot

TOKEN = "8767848071:AAHjxT7945VO-X7iCI3kG-0fIqC_giqX7Z8"

bot = telebot.TeleBot(TOKEN)

app = Flask(__name__)

VIP_USERS = set()


@app.route('/payment-webhook', methods=['POST'])
def payment_webhook():

    data = request.json
    user_id = data.get("order_id")

    if user_id:
        VIP_USERS.add(int(user_id))

        bot.send_message(
            int(user_id),
            "👑 Η πληρωμή σου επιβεβαιώθηκε!\nVIP ενεργοποιήθηκε."
        )

    return "OK"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
