import os
import retries
import sqlite3

def is_handled(mid, cur):
    retries.execution_with_backoff(cur, f"SELECT 1 FROM {os.environ["SCHEMA"]}.messages WHERE message = %s", (mid,))
    return True if cur.fetchone() else False

def set_handled(mid, timestamp, cur):
    retries.execution_with_backoff(cur, f"""
        INSERT INTO {os.environ["SCHEMA"]}.messages (message, timestamp)
        VALUES (%s, %s)
        """, (mid, timestamp))

def get_question(sender, cur):
    retries.execution_with_backoff(cur, f"""
        SELECT question, options, answer, expression_id
        FROM {os.environ["SCHEMA"]}.questions
        WHERE sender = %s
        """, (sender,))
    row = cur.fetchone()
    question, options, answer, expression_id = row if row else (None, "None", None, None)
    return question, eval(options), answer, expression_id

def get_leitner_system(sender, cur):
    retries.execution_with_backoff(cur, f"""
        SELECT system
        FROM {os.environ["SCHEMA"]}.leitner
        WHERE sender = %s""", (sender,))
    leitner_system = eval(cur.fetchone()[0])
    return leitner_system

def get_system_prompt():
    conn = sqlite3.connect("expressions.db")
    cur = conn.cursor()
    cur.execute("SELECT content FROM openai WHERE role='explanation_system_prompt'")
    system_prompt = cur.fetchone()[0]
    cur.close()
    conn.close()
    return system_prompt

def get_expression(expression_id):
    conn = sqlite3.connect("expressions.db")
    cur = conn.cursor()
    cur.execute(f"SELECT expression FROM expressions WHERE id = ?", (expression_id,))
    expression = cur.fetchone()[0]
    cur.close()
    conn.close()
    return expression

def get_user_message(question, options, answer, expression_id):
    expression = get_expression(expression_id)
    options = repr(question["options"]).replace("'", "\"").replace(" ", "")
    user_message = ("{\"context\":\"%s\",\"question\":\"%s\",\"options\":%s,\"answer\":\"%s\"" % 
        (expression, question, options, answer))
    return user_message

def get_explanation(question, options, answer, expression_id, client):
    system_prompt = get_system_prompt()
    user_message = get_user_message(question, options, answer, expression_id)
    explanation = retries.completion_creation_with_backoff(client, system_prompt, user_message, 0)
    return explanation

def process_correct_response(leitner_system, answer, explanation, expression_id):
    for box in leitner_system:
        if expression_id in leitner_system[box] and box + 1 in leitner_system:
            leitner_system[box].remove(expression_id)
            leitner_system[box + 1].add(expression_id)
            break

    response = f"✔️ Correct! ✔️\n\n{explanation}"

    return response

def process_incorrect_response(leitner_system, answer, explanation, expression_id):
    for box in leitner_system:
        if expression_id in leitner_system[box] and box - 1 in leitner_system:
            leitner_system[box].remove(expression_id)
            leitner_system[box - 1].add(expression_id)
            break

    response = f"❌ Incorrect. ❌\n\n{explanation}"

    return response

def set_leitner_system(leitner_system, sender, cur):
    retries.execution_with_backoff(cur, f"DELETE FROM {os.environ["SCHEMA"]}.questions WHERE sender = %s", (sender,))
    retries.execution_with_backoff(cur, f"""
        UPDATE {os.environ["SCHEMA"]}.leitner
        SET system = %s
        WHERE sender = %s
        """, (repr(leitner_system), sender))