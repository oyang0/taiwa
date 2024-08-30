import os
import retries

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
        SELECT options, answer, explanation, expression_id
        FROM {os.environ["SCHEMA"]}.questions
        WHERE sender = %s
        """, (sender,))
    row = cur.fetchone()
    options, answer, explanation, expression_id = row if row else ("None", None, None, None)
    return eval(options), answer, explanation, expression_id

def get_leitner_system(sender, cur):
    retries.execution_with_backoff(cur, f"""
        SELECT system
        FROM {os.environ["SCHEMA"]}.leitner
        WHERE sender = %s""", (sender,))
    leitner_system = eval(cur.fetchone()[0])
    return leitner_system

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