import collections
import commands
import exceptions
import messages
import os
import postbacks
import random
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

def process_message(message):
    conn, cur = retries.get_connection_and_cursor_with_backoff()
    leitner_system = messages.get_leitner_system(message["sender"]["id"], cur)
    box = messages.get_random_box(leitner_system)
    id, expression = messages.get_random_expression(leitner_system, box)
    thread = retries.thread_creation_with_backoff(client)
    retries.message_creation_with_backoff(client, thread, expression)
    question = retries.get_question_with_backoff(client, thread)

    with suppress(RetryError):
        retries.thread_deletion_with_backoff(client, thread)

    text = Text(text=expression)
    random.shuffle(question["options"])
    buttons = [Button("postback", title=option, payload=option) for option in question["options"]]
    button_template = ButtonTemplate(text=question["question"], buttons=buttons)
    responses = [text.to_dict(), button_template.to_dict()]
    messages.set_question(message["sender"]["id"], question["answer"], question["options"], id, cur)
    retries.commit_with_backoff(conn)
    retries.close_cursor_and_connection_with_backoff(cur, conn)

    return responses

def process_postback(message):
    conn, cur = retries.get_connection_and_cursor_with_backoff()
    answer, options, id = postbacks.get_question(message["sender"]["id"], cur)

    if options and message["postback"]["payload"] in options:
        leitner_system = postbacks.get_leitner_system(message["sender"]["id"], cur)
        response = (postbacks.process_correct_response(leitner_system, answer, id) if
                    message["postback"]["payload"] == answer else
                    postbacks.process_incorrect_response(leitner_system, answer, id))
        responses = [response.to_dict()]
        postbacks.set_leitner_system(leitner_system, message["sender"]["id"], cur)
        retries.commit_with_backoff(conn)
    else:
        responses = []

    retries.close_cursor_and_connection_with_backoff(cur, conn)

    return responses

class Messenger(BaseMessenger):
    def __init__(self, page_access_token):
        self.page_access_token = page_access_token
        super(Messenger, self).__init__(self.page_access_token)
        commands.set_commands(app)

    def message(self, message):
        app.logger.debug(f"Message received: {message}")
        self.send_action("mark_seen")
        self.send_action("typing_on")

        try:
            actions = process_message(message)
        except Exception as exception:
            actions = exceptions.process_exception(exception)

        for action in actions:
            res = self.send(action, "RESPONSE")
            app.logger.debug(f"Message sent: {action}")
            app.logger.debug(f"Response: {res}")
        
        self.send_action("typing_off")
    
    def postback(self, message):
        app.logger.debug(f"Message received: {message}")
        self.send_action("mark_seen")
        self.send_action("typing_on")

        try:
            actions = process_postback(message)
        except Exception as exception:
            actions = exceptions.process_exception(exception)

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