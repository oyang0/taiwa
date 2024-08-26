import collections
import exceptions
import messages
import os
import psycopg2
import postbacks
import random
import re
import retries

from collections.abc import Iterable
from contextlib import suppress
from flask import Flask, request
from fbmessenger import BaseMessenger
from fbmessenger.elements import Text, Button
from fbmessenger.templates import ButtonTemplate
from openai import OpenAI
from tenacity import RetryError

collections.Iterable = Iterable

def process_message(message, cur):
    leitner_system = messages.get_leitner_system(message["sender"]["id"], cur)
    box = messages.get_random_box(leitner_system)
    id, expression = messages.get_random_expression(leitner_system, box)
    thread = retries.thread_creation_with_backoff(client)
    retries.message_creation_with_backoff(client, thread, expression)
    question = retries.get_question_with_backoff(client, thread)

    with suppress(RetryError):
        retries.thread_deletion_with_backoff(client, thread)

    messages.set_question(message["sender"]["id"], question["answer"], question["options"], id, cur)
    random.shuffle(question["options"])
    buttons = [Button("postback", title=option, payload=option) for option in question["options"]]
    response = ButtonTemplate(text=question["question"], buttons=buttons)
    responses = [Text(text=expression).to_dict(), response.to_dict()]

    return responses

def process_postback(message, cur):
    answer, options, id = postbacks.get_question(message["sender"]["id"])

    if message["postback"]["payload"] in options:
        leitner_system = postbacks.get_leitner_system(message["sender"]["id"], cur)

        if message["postback"]["payload"] == answer:
            responses = [postbacks.process_correct_response(leitner_system, answer, id)]
        else:
            responses = [postbacks.process_incorrect_response(leitner_system, answer, id)]

        postbacks.set_leitner_system(leitner_system, message["sender"]["id"], cur)
    else:
        responses = []
    
    return responses

class Messenger(BaseMessenger):
    def __init__(self, page_access_token):
        self.page_access_token = page_access_token
        super(Messenger, self).__init__(self.page_access_token)

    def message(self, message):
        app.logger.debug(f"Message received: {message}")
        self.send_action("mark_seen")

        if "text" in message["message"]:
            msg = message["message"]["text"].lower()
            msg = re.sub(r"[^a-z0-9]", " ", msg)

            if "taiwa" in msg.split():
                self.send_action("typing_on")
                conn = psycopg2.connect(os.environ["DATABASE_URL"])
                cur = conn.cursor()

                try:
                    actions = process_message(message, cur)
                    conn.commit()
                except Exception as exception:
                    actions = exceptions.process_exception(exception)
                
                cur.close()
                conn.close()

                for action in actions:
                    res = self.send(action, "RESPONSE")
                    app.logger.debug(f"Message sent: {action}")
                    app.logger.debug(f"Response: {res}")
                
                self.send_action("typing_off")
    
    def postback(self, message):
        app.logger.debug(f"Message received: {message}")
        self.send_action("mark_seen")
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cur = conn.cursor()

        try:
            actions = process_postback(message, cur)
            conn.commit()
        except Exception as exception:
            actions = exceptions.process_exception(exception)

        cur.close()
        conn.close()

        for action in actions:
            res = self.send(action, "RESPONSE")
            app.logger.debug(f"Message sent: {action}")
            app.logger.debug(f"Response: {res}")

        self.send_action("typing_off")

app = Flask(__name__)
app.debug = True
messenger = Messenger(os.environ["FB_PAGE_TOKEN"])

client = OpenAI()

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == os.environ.get("FB_VERIFY_TOKEN"):
            return request.args.get("hub.challenge")
        raise ValueError("FB_VERIFY_TOKEN does not match.")
    elif request.method == "POST":
        messenger.handle(request.get_json(force=True))
    return ""

if __name__ == "__main__":
    app.run(host="0.0.0.0")