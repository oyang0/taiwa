from flask import Flask, request
from taiwa import Taiwa

app = Flask(__name__)
bot = None
verify_token = None

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        # Facebook uses a GET request to verify your server
        if (request.args.get("hub.verify_token") == verify_token):
            return request.args.get("hub.challenge")
        else:
            return "Error, wrong validation token"
    else:
        # Facebook sends a POST request when a message is sent to your bot
        message = request.get_json()
        bot.handle(message)
        return "Message processed"

if __name__ == "__main__":
    page_access_token = input("Page access token: ")
    bot = Taiwa(page_access_token)
    verify_token = input("Verify token: ")
    app.run(debug=True)