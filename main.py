import os
import random
import sqlite3

from flask import Flask, request
from fbmessenger import BaseMessenger
from fbmessenger.elements import Text

def process_message(message):
    conn = sqlite3.connect("JPN_CommunicationPatterns.db")
    c = conn.cursor()

    c.execute("SELECT expression FROM expressions")
    expressions = [row[0] for row in c.fetchall()]

    expression = random.choice(expressions)
    response = Text(text=expression)

    conn.close()
    
    return response.to_dict()

class Messenger(BaseMessenger):
    def __init__(self, page_access_token):
        self.page_access_token = page_access_token
        super(Messenger, self).__init__(self.page_access_token)

    def message(self, message):
        app.logger.debug("Message received: {}".format(message))

        if "text" in message["message"]:
            msg = message["message"]["text"].lower()
            msg = "".join(c for c in msg if c.isalnum() or c.isspace())

            if "taiwa" in msg.split():
                action = process_message(message)
                res = self.send(action, "RESPONSE")
                app.logger.debug("Message sent: {}".format(action))
                app.logger.debug("Response: {}".format(res))

app = Flask(__name__)
app.debug = True
messenger = Messenger(os.environ["FB_PAGE_TOKEN"])

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == os.environ.get("FB_VERIFY_TOKEN"):
            if request.args.get("init") and request.args.get("init") == "true":
                messenger.init_bot()
                return ""
            return request.args.get("hub.challenge")
        raise ValueError("FB_VERIFY_TOKEN does not match.")
    elif request.method == "POST":
        messenger.handle(request.get_json(force=True))
    return ""

if __name__ == "__main__":
    app.run(host="0.0.0.0")