import collections
import os
import psycopg2
import random
import re
import sqlite3

from collections.abc import Iterable
from contextlib import suppress
from flask import Flask, request
from fbmessenger import BaseMessenger
from fbmessenger.elements import Text, Button
from fbmessenger.templates import ButtonTemplate
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_random_exponential, RetryError

collections.Iterable = Iterable

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
def execution_with_backoff(cur, query, vars = None):
    cur.execute(query, vars)

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
def thread_creation_with_backoff():
    thread = client.beta.threads.create()
    return thread

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
def thread_deletion_with_backoff(thread):
    client.beta.threads.delete(thread.id)

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
def message_creation_with_backoff(thread, content):
    client.beta.threads.messages.create(thread_id=thread.id, role="user", content=content)

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
def message_listing_with_backoff(thread):
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    return messages

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
def message_deletion_with_backoff(message, thread):
    client.beta.threads.messages.delete(message_id=message.id, thread_id=thread.id)

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
def creation_and_polling_with_backoff(thread):
    run = client.beta.threads.runs.create_and_poll(thread_id=thread.id, assistant_id=os.environ["ASSISTANT_ID"])

    while run.status == "in_progress":
        pass

    if run.status == "failed":
        raise RetryError(run.last_error.message)
    elif run.status == "incomplete":
        raise RetryError(run.incomplete_details.reason)
    
    return run

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
def get_question_with_backoff(thread):
    try:
        run = creation_and_polling_with_backoff(thread)
    except RetryError as e:
        return e
    
    if run.status == "completed":
        try:
            messages = message_listing_with_backoff(thread)
        except RetryError as e:
            return e

        try:
            question = eval(messages.data[0].content[0].text.value)
            evaluate_question(question)
        except (SyntaxError, Exception) as e:
            try:
                message_deletion_with_backoff(messages.data[0], thread)
                raise e
            except RetryError as e:
                return e
    else:
        question = RetryError(run.status)

    return question

def evaluate_question(question):
    if "question" not in question:
        raise Exception("attribute \"question\" not in JSON")
    elif type(question["question"]) is not str:
        raise Exception("value \"question\" is not string")
    elif "options" not in question:
        raise Exception("attribute \"options\" not in JSON")
    elif type(question["options"]) is not list:
        raise Exception("value \"options\" is not array")
    elif "answer" not in question:
        raise Exception("attribute \"answer\" not in JSON")
    elif type(question["answer"]) is not str:
        raise Exception("value \"answer\" is not string")
    elif len(question["options"]) > 3:
        raise Exception("value \"options\" has length greater than 3")
    elif question["answer"] not in question["options"]:
        raise Exception("value \"answer\" not in value \"options\"")
    
    for i, option in enumerate(question["options"]):
        if type(option) is not str:
            raise Exception(f"value \"options\"[{i}] is not string")

def init_leitner_system():
    conn = sqlite3.connect("expressions.db")
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT type FROM expressions")
    leitner_system = {box: [] for box in [type for row in cur.fetchall() for type in row]}
    cur.execute("SELECT id, type FROM expressions")

    for id, type in cur.fetchall():
        leitner_system[type].append(id)

    cur.close()
    conn.close()

    return leitner_system

def set_leitner_system(sender, conn, cur):
    leitner_system = init_leitner_system()

    try:
        execution_with_backoff(
            cur, f"""
            INSERT INTO {os.environ["SCHEMA"]}.leitner (sender, system)
            VALUES (%s, %s)
            ON CONFLICT (sender) DO NOTHING
            """, (sender, repr(leitner_system)))
        conn.commit()
    except RetryError as e:
        return e

    return leitner_system

def get_leitner_system(sender, conn, cur):
    try:
        execution_with_backoff(
            cur, f"""
            SELECT system
            FROM {os.environ["SCHEMA"]}.leitner
            WHERE sender = %s
            """, (sender,))
    except RetryError as e:
        return e
    
    row = cur.fetchone()
    leitner_system = eval(row[0]) if row else set_leitner_system(sender, conn, cur)

    return leitner_system

def get_random_box(leitner_system):
    remaining_boxes = sorted([box for box, ids in leitner_system.items() if ids])
    weights = [weight for weight in range(2 * len(remaining_boxes) - 1, 0, -2)]
    box = random.choices(remaining_boxes, weights)[0]
    return box

def get_random_expression(leitner_system, box):
    conn = sqlite3.connect("expressions.db")
    cur = conn.cursor()
    expression_id = random.choice(leitner_system[box])
    cur.execute(f"SELECT expression FROM expressions WHERE id = ?", (expression_id,))
    expression = cur.fetchone()[0]
    cur.close()
    conn.close()
    return expression_id, expression

def select_expression(sender, conn, cur):
    leitner_system = get_leitner_system(sender, conn, cur)

    if type(leitner_system) is RetryError:
        return leitner_system, leitner_system

    box = get_random_box(leitner_system)
    expression_id, expression = get_random_expression(leitner_system, box)

    return expression_id, expression

def select_question(sender, expression, expression_id, conn, cur):
    try:
        thread = thread_creation_with_backoff()
    except RetryError as e:
        return e
    
    try:
        message_creation_with_backoff(thread, expression)
    except RetryError as e:
        return e

    question = get_question_with_backoff(thread)

    with suppress(RetryError):
        thread_deletion_with_backoff(thread)

    if type(question) is RetryError:
        return question

    try:
        execution_with_backoff(
            cur, f"""
            INSERT INTO {os.environ["SCHEMA"]}.answers (sender, answer, options, expression_id)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (sender)
            DO UPDATE SET
                answer = EXCLUDED.answer,
                options = EXCLUDED.options,
                expression_id = EXCLUDED.expression_id
            """, (sender, question["answer"], repr(question["options"]), expression_id))
        conn.commit()
    except RetryError as e:
        return e
    
    return question

def process_message(message, conn, cur):
    expression_id, expression = select_expression(message["sender"]["id"], conn, cur)

    if type(expression) is RetryError:
        return [Text(text=f"{expression}").to_dict()]
    
    question = select_question(message["sender"]["id"], expression, expression_id, conn, cur)

    if type(question) is RetryError:
        return [Text(text=f"{question}").to_dict()]

    random.shuffle(question["options"])
    buttons = [Button("postback", title=option, payload=option) for option in question["options"]]
    response = ButtonTemplate(text=question["question"], buttons=buttons)
    responses = [Text(text=expression).to_dict(), response.to_dict()]

    return responses

def process_correct_response(leitner_system, answer, expression_id):
    for box in leitner_system:
        if expression_id in leitner_system[box] and box + 1 in leitner_system:
            leitner_system[box + 1].append(expression_id)
            leitner_system[box].remove(expression_id)

    response = Text(text=f"✔️ Correct! The answer is: {answer}")

    return response

def process_incorrect_response(leitner_system, answer, expression_id):
    for box in leitner_system:
        if expression_id in leitner_system[box] and box - 1 in leitner_system:
            leitner_system[box - 1].append(expression_id)
            leitner_system[box].remove(expression_id)

    response = Text(text=f"❌ Incorrect. The answer is: {answer}")

    return response

def update_leitner_system(sender, payload, answer, expression_id, conn, cur):
    leitner_system = get_leitner_system(sender, conn, cur)

    if payload == answer:
        response = process_correct_response(leitner_system, answer, expression_id)
    else:
        response = process_incorrect_response(leitner_system, answer, expression_id)

    try:
        execution_with_backoff(cur, f"DELETE FROM {os.environ["SCHEMA"]}.answers WHERE sender = %s", (sender,))
        execution_with_backoff(
            cur, f"""
            UPDATE {os.environ["SCHEMA"]}.leitner
            SET system = %s
            WHERE sender = %s
            """, (repr(leitner_system), sender))
        conn.commit()
    except RetryError as e:
        return [Text(text=f"{e}").to_dict()]
    
    return [response.to_dict()]

def process_postback(message, conn, cur):
    try:
        execution_with_backoff(
            cur, f"""
            SELECT answer, options, expression_id
            FROM {os.environ["SCHEMA"]}.answers
            WHERE sender = %s
            """, (message["sender"]["id"],))
    except RetryError as e:
        return [Text(text=f"{e}").to_dict()]
    
    row = cur.fetchone()

    if row and message["postback"]["payload"] in eval(row[1]):
        responses = update_leitner_system(
            message["sender"]["id"],
            message["postback"]["payload"],
            row[0],
            row[2],
            conn,
            cur)
    else:
        responses = []
    
    return responses

class Messenger(BaseMessenger):
    def __init__(self, page_access_token):
        self.page_access_token = page_access_token
        super(Messenger, self).__init__(self.page_access_token)

    def message(self, message):
        app.logger.debug("Message received: {}".format(message))
        self.send_action("mark_seen")

        if "text" in message["message"]:
            msg = message["message"]["text"].lower()
            msg = re.sub(r"[^a-z0-9]", " ", msg)

            if "taiwa" in msg.split():
                self.send_action("typing_on")
                conn = psycopg2.connect(os.environ["DATABASE_URL"])
                cur = conn.cursor()
                actions = process_message(message, conn, cur)
                cur.close()
                conn.close()

                for action in actions:
                    res = self.send(action, "RESPONSE")
                    app.logger.debug("Message sent: {}".format(action))
                    app.logger.debug("Response: {}".format(res))
                
                self.send_action("typing_off")
    
    def postback(self, message):
        app.logger.debug("Postback received: {}".format(message))
        self.send_action("mark_seen")

        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cur = conn.cursor()
        actions = process_postback(message, conn, cur)
        cur.close()
        conn.close()

        for action in actions:
            res = self.send(action, "RESPONSE")
            app.logger.debug("Message sent: {}".format(action))
            app.logger.debug("Response: {}".format(res))

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