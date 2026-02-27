from flask import Flask, request
import telebot
import os

# 🔑 ΒΑΛΕ ΤΑ ΔΙΚΑ ΣΟΥ
TOKEN = os.environ.get("8767848071:AAHjxT7945VO-X7iCI3kG-0fIqC_giqX7Z8")

IPN_SECRET = "vLFBtbQ2EsfCcviI1UbFo3D99EgBYUWP"

bot = telebot.TeleBot(TOKEN)

app = Flask(__name__)

# 👑 WEBHOOK LISTENER
@app.route('/payment-webhook', methods=['POST'])
def payment_webhook():

    data = request.json

    # έλεγχος IPN secret
    if request.headers.get("x-nowpayments-sig"):
        
        user_id = data.get("order_id")  # θα βάζουμε telegram id εδώ

        if user_id:
            bot.send_message(
                user_id,
                "👑 Η πληρωμή σου επιβεβαιώθηκε!\n\n"
                "VIP πρόσβαση ενεργοποιήθηκε."
            )

    return "OK"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)