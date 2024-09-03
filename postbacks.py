import json
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
    
def is_options(sender, cur):
    retries.execution_with_backoff(cur, f"""
        SELECT 1
        FROM {os.environ["SCHEMA"]}.questions
        WHERE sender = %s
        """, (sender,))
    return True if cur.fetchone() else False
    
def get_options(sender, cur):
    retries.execution_with_backoff(cur, f"""
        SELECT options
        FROM {os.environ["SCHEMA"]}.questions
        WHERE sender = %s
        """, (sender,))
    options = json.loads(cur.fetchone()[0])
    return options

def get_multiple_choice_question(sender, cur):
    retries.execution_with_backoff(cur, f"""
        SELECT question, options, answer, expression_id
        FROM {os.environ["SCHEMA"]}.questions
        WHERE sender = %s
        """, (sender,))
    question, options, answer, expression_id = cur.fetchone()
    return question, json.loads(options), answer, expression_id

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

def get_response_format():
    conn = sqlite3.connect("expressions.db")
    cur = conn.cursor()
    cur.execute("SELECT content FROM openai WHERE role='explanation_response_format'")
    response_format = json.loads(cur.fetchone()[0])
    cur.close()
    conn.close()
    return response_format

def get_expression(expression_id):
    conn = sqlite3.connect("expressions.db")
    cur = conn.cursor()
    cur.execute(f"SELECT expression FROM expressions WHERE id = ?", (expression_id,))
    expression = cur.fetchone()[0]
    cur.close()
    conn.close()
    return expression

def update_multiple_choice_question(question, options):
    question = f"{question}\n\n{"\n".join([f"({chr(97 + i)}) {option}" for i, option in enumerate(options)])}"
    return question

def get_user_prompt(question, options, answer, expression_id):
    expression = get_expression(expression_id)
    question = update_multiple_choice_question(question, options)
    user_content = f"Content: {expression}\n\nQuestion: {question}\n\nAnswer: {answer}"
    return user_content

def get_question_explanation(question, options, answer, expression_id, app, client):
    system_prompt, response_format = get_system_prompt(), get_response_format()
    user_prompt = get_user_prompt(question, options, answer, expression_id)
    explanation = retries.completion_creation_with_backoff(client, system_prompt, user_prompt, 0, response_format)
    app.logger.debug(f"Thoughts created: {explanation["thoughts"]}")
    explanation = json.loads(explanation)["explanation"]
    return explanation

def process_correct_answer(leitner_system, explanation, expression_id):
    for box in leitner_system:
        if expression_id in leitner_system[box] and box + 1 in leitner_system:
            leitner_system[box].remove(expression_id)
            leitner_system[box + 1].add(expression_id)
            break

    response = f"✔️ Correct! ✔️\n\n{explanation}"

    return response

def process_incorrect_answer(leitner_system, explanation, expression_id):
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

def process_answer(answer, payload, leitner_system, explanation, expression_id, sender, cur):
    if answer == payload:
        response = process_correct_answer(leitner_system, explanation, expression_id)
    else:
        response = process_incorrect_answer(leitner_system, explanation, expression_id)
    
    set_leitner_system(leitner_system, sender, cur)
    
    return response