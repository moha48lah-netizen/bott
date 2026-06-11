from flask import Flask, request
import requests

app = Flask(__name__)

VERIFY_TOKEN = "26042009"
PAGE_ACCESS_TOKEN = "YOUR_PAGE_ACCESS_TOKEN"


def send_message(user_id, text):
    url = "https://graph.facebook.com/v19.0/me/messages"

    payload = {
        "recipient": {"id": user_id},
        "message": {"text": text}
    }

    params = {
        "EAAVlUUUccQUBRkRn2ewom7yxhDi3R7u0Pk92QZCTTVZC1CGmwEux9t6SmsPsyrSPgj2aWuY8ZC5OD7ZBxojYDT9I0Gvuv5xyD24YvaUQbzjhA6jtSpgFazR956KdX4gUE6YHqIrA3CjgSHUDdrOxbilRGfUmOugL8d5vsGnz8gKGyrJUibT6XYVV5c9wRkHuYINjuaNKCJBity9QrZBVBws5iFjAG7LHq9K3i59rDt7eoSQAl96TTpz7nJJTHx1gSmrZBdP2ZCisvStkxZADNUD2": PAGE_ACCESS_TOKEN
    }

    requests.post(url, json=payload, params=params)


@app.route("/", methods=["GET"])
def home():
    return "Bot is running"


@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200

    return "Forbidden", 403


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    print(data)

    try:
        messaging = data["entry"][0]["messaging"][0]

        if "message" in messaging and "text" in messaging["message"]:
            message = messaging["message"]["text"]
            user_id = messaging["sender"]["id"]

            if "سلام" in message:
                send_message(user_id, "وعليكم السلام 👋")
            else:
                send_message(user_id, "وصلت رسالتك 👍")

    except Exception as e:
        print("Error:", e)

    return "OK", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
