import json
import os
import random
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

def create_leitner_system():
    conn = sqlite3.connect("expressions.db")
    cur = conn.cursor()
    cur.execute("SELECT type FROM types")
    leitner_system = {box: set() for box in [type for row in cur.fetchall() for type in row]}
    cur.execute("SELECT id, type FROM expressions")

    for expression_id, type in cur.fetchall():
        leitner_system[type].add(expression_id)

    cur.close()
    conn.close()

    return leitner_system

def set_leitner_system(sender, cur):
    leitner_system = create_leitner_system()
    retries.execution_with_backoff(cur, f"""
        INSERT INTO {os.environ["SCHEMA"]}.leitner (sender, system)
        VALUES (%s, %s)
        ON CONFLICT (sender) DO NOTHING
        """, (sender, repr(leitner_system)))
    return leitner_system

def get_leitner_system(sender, cur):
    retries.execution_with_backoff(cur, f"""
        SELECT system
        FROM {os.environ["SCHEMA"]}.leitner
        WHERE sender = %s""", (sender,))
    row = cur.fetchone()
    leitner_system = eval(row[0]) if row else set_leitner_system(sender, cur)
    return leitner_system

def get_random_box(leitner_system):
    remaining_boxes = sorted([box for box, ids in leitner_system.items() if ids])[:5]
    weights = [weight for weight in range(2 * len(remaining_boxes) - 1, 0, -2)]
    box = random.choices(remaining_boxes, weights)[0]
    return box

def get_random_expression(leitner_system, box):
    conn = sqlite3.connect("expressions.db")
    cur = conn.cursor()
    expression_id = random.choice([expression_id for expression_id in leitner_system[box]])
    cur.execute(f"SELECT expression FROM expressions WHERE id = ?", (expression_id,))
    expression = cur.fetchone()[0]
    cur.close()
    conn.close()
    return expression_id, expression

def get_system_prompt():
    conn = sqlite3.connect("expressions.db")
    cur = conn.cursor()
    cur.execute("SELECT content FROM openai WHERE role='question_system_prompt'")
    system_prompt = cur.fetchone()[0]
    cur.close()
    conn.close()
    return system_prompt

def get_response_format():
    conn = sqlite3.connect("expressions.db")
    cur = conn.cursor()
    cur.execute("SELECT content FROM openai WHERE role='question_response_format'")
    response_format = json.loads(cur.fetchone()[0])
    cur.close()
    conn.close()
    return response_format

def get_evaluation_format():
    conn = sqlite3.connect("expressions.db")
    cur = conn.cursor()
    cur.execute("SELECT content FROM openai WHERE role='question_evaluation_format'")
    response_format = json.loads(cur.fetchone()[0])
    cur.close()
    conn.close()
    return response_format

def update_multiple_choice_question(question, options):
    return f"{question}\n\n{"\n".join([f"({chr(97 + i)}) {option}" for i, option in enumerate(options)])}"

def is_correct_question(question):
    if len(update_multiple_choice_question(question["question"], question["options"])) > 640:
        return False
    elif len(question["options"]) > 3:
        return False
    elif question["answer"] not in question["options"]:
        return False
    return True

def get_input_messages(system_prompt, user_content, assistant_contents = []):
    initial_messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}]
    final_messages = [{"role": "assistant", "content": content} for content in assistant_contents]
    return initial_messages + final_messages

def set_multiple_choice_question(question, sender, expression_id, cur):
    question, options, answer = question["question"], json.dumps(question["options"]), question["answer"]
    retries.execution_with_backoff(cur, f"""
        INSERT INTO {os.environ["SCHEMA"]}.questions (sender, question, options, answer, expression_id)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (sender)
        DO UPDATE SET
            question = EXCLUDED.question,
            options = EXCLUDED.options,
            answer = EXCLUDED.answer,
            expression_id = EXCLUDED.expression_id
        """, (sender, question, options, answer, expression_id))

def get_multiple_choice_question(expression, expression_id, sender, cur, client):
    is_correct, assistant_contents = False, []
    system_prompt = get_system_prompt()
    response_format = get_response_format()
    evaluation_format = get_evaluation_format()

    while not is_correct:
        messages = get_input_messages(system_prompt, expression)
        question = retries.completion_creation_with_backoff(client, messages, 1, response_format)
        assistant_contents.append(question)
        messages = get_input_messages(system_prompt, expression, assistant_contents)
        evaluation = retries.completion_creation_with_backoff(client, messages, 0, evaluation_format)
        assistant_contents.append(evaluation)
        is_correct = json.loads(evaluation)["evaluation_answer"] == "Correct"
    
    question = json.loads(question)

    if not is_correct_question(question):
        raise Exception("Failed to get valid multiple choice question")
    
    set_multiple_choice_question(question, sender, expression_id, cur)
    
    return question