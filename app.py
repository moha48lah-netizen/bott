from flask import Flask, request

app = Flask(__name__)

VERIFY_TOKEN = "26042009"

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
    return "OK", 200


app.run(host="0.0.0.0", port=8080)
