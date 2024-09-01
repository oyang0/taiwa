import collections
import commands
import exceptions
import messages
import os
import postbacks
import random
import retries

from collections.abc import Iterable
from flask import Flask, request
from fbmessenger import BaseMessenger
from fbmessenger.elements import Text, Button
from fbmessenger.templates import ButtonTemplate
from openai import OpenAI

collections.Iterable = Iterable

def process_message(message, cur):
    sender = message["sender"]["id"]
    leitner_system = messages.get_leitner_system(sender, cur)
    box = messages.get_random_box(leitner_system)
    expression_id, expression = messages.get_random_expression(leitner_system, box)
    question = messages.get_multiple_choice_question(expression, expression_id, sender, cur, client)
    question, options = question["question"], question["options"]
    text = Text(text=expression)
    random.shuffle(options)
    buttons = [Button("postback", title=chr(65 + i), payload=option) for i, option in enumerate(options)]
    question = messages.update_multiple_choice_question(question, options)
    button_template = ButtonTemplate(text=question, buttons=buttons)
    return (text.to_dict(), button_template.to_dict())

def process_postback(message, cur):
    sender, payload = message["sender"]["id"], message["postback"]["payload"]
    question, options, answer, expression_id = postbacks.get_multiple_choice_question(sender, cur)
    leitner_system = postbacks.get_leitner_system(sender, cur)
    explanation = postbacks.get_explanation(question, options, answer, expression_id, client)
    response = postbacks.process_answer(answer, payload, leitner_system, explanation, expression_id, sender, cur)
    text = Text(text=response)
    return (text.to_dict(),)

class Messenger(BaseMessenger):
    def __init__(self, page_access_token):
        self.page_access_token = page_access_token
        super(Messenger, self).__init__(self.page_access_token)

    def message(self, message):
        app.logger.debug(f"Message received: {message}")
        conn, cur = retries.get_connection_and_cursor_with_backoff()
        self.send_action("mark_seen")

        if not messages.is_handled(message["message"]["mid"], cur):
            try:
                messages.set_handled(message["message"]["mid"], message["timestamp"], cur)
                retries.commit_with_backoff(conn)
                
                try:
                    self.send_action("typing_on")

                    if commands.is_command(message["message"]):
                        actions = commands.process_command(message, cur)
                    else:
                        actions = process_message(message, cur)

                    retries.commit_with_backoff(conn)
                except Exception as exception:
                    actions = exceptions.process_exception(exception)

                for action in actions:
                    res = self.send(action, "RESPONSE")
                    app.logger.debug(f"Message sent: {action}")
                    app.logger.debug(f"Response: {res}")
                
                self.send_action("typing_off")
            except:
                app.logger.debug(f"Not handled: {message["message"]["mid"]}")
        
        retries.close_cursor_and_connection_with_backoff(cur, conn)
    
    def postback(self, message):
        app.logger.debug(f"Message received: {message}")
        conn, cur = retries.get_connection_and_cursor_with_backoff()
        self.send_action("mark_seen")

        if not postbacks.is_handled(message["postback"]["mid"], cur):
            try:
                postbacks.set_handled(message["postback"]["mid"], message["timestamp"], cur)
                retries.commit_with_backoff(conn)

                try:
                    if postbacks.is_options(message["sender"]["id"], cur):
                        options = postbacks.get_options(message["sender"]["id"], cur)

                        if message["postback"]["payload"] in options:
                            self.send_action("typing_on")
                            actions = process_postback(message, cur)
                            retries.commit_with_backoff(conn)
                    else:
                        actions = ()
                except Exception as exception:
                    actions = exceptions.process_exception(exception)

                for action in actions:
                    res = self.send(action, "RESPONSE")
                    app.logger.debug(f"Message sent: {action}")
                    app.logger.debug(f"Response: {res}")
                
                self.send_action("typing_off")
            except:
                app.logger.debug(f"Not handled: {message["postback"]["mid"]}")
        
        retries.close_cursor_and_connection_with_backoff(cur, conn)
    
    def init_bot(self):
        self.add_whitelisted_domains("https://facebook.com/")
        res = commands.set_commands()
        app.logger.debug("Response: {}".format(res))

app = Flask(__name__)
app.debug = True
messenger = Messenger(os.environ["FB_PAGE_TOKEN"])

client = OpenAI()

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