from flask import Flask, request
import os
from taiwa import Taiwa

app = Flask(__name__)
bot = Taiwa(os.environ['PAGE_ACCESS_TOKEN'])

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        if (request.args.get("hub.verify_token") == os.environ['VERIFY_TOKEN']):
            return request.args.get("hub.challenge")
        else:
            return "Error, wrong validation token"
    else:
        message = request.get_json()
        bot.handle(message)
        return "Message processed"

if __name__ == "__main__":
    app.run(debug=True)