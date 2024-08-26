import os
import retries

from fbmessenger.elements import Text

def get_question(sender, cur):
    retries.execution_with_backoff(
        cur, f"""
        SELECT answer, options, expression_id
        FROM {os.environ["SCHEMA"]}.answers
        WHERE sender = %s
        """, (sender,))
    answer, options, id = cur.fetchone()
    return answer, eval(options), id

def get_leitner_system(sender, cur):
    retries.execution_with_backoff(
        cur, f"""
        SELECT system
        FROM {os.environ["SCHEMA"]}.leitner
        WHERE sender = %s""", (sender,))
    leitner_system = eval(cur.fetchone()[0])
    return leitner_system

def process_correct_response(leitner_system, answer, expression_id):
    for box in leitner_system:
        if expression_id in leitner_system[box] and box + 1 in leitner_system:
            leitner_system[box].remove(expression_id)
            leitner_system[box + 1].add(expression_id)
            break

    response = Text(text=f"✔️ Correct! The answer is: {answer}")

    return response

def process_incorrect_response(leitner_system, answer, expression_id):
    for box in leitner_system:
        if expression_id in leitner_system[box]:
            leitner_system[box].remove(expression_id)
            leitner_system[1].add(expression_id)
            break

    response = Text(text=f"❌ Incorrect. The answer is: {answer}")

    return response

def set_leitner_system(leitner_system, sender, cur):
    retries.execution_with_backoff(cur, f"DELETE FROM {os.environ["SCHEMA"]}.answers WHERE sender = %s", (sender,))
    retries.execution_with_backoff(
        cur, f"""
        UPDATE {os.environ["SCHEMA"]}.leitner
        SET system = %s
        WHERE sender = %s
        """, (repr(leitner_system), sender))