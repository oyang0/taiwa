import os
import random
import retries
import sqlite3

def create_leitner_system():
    conn = sqlite3.connect("expressions.db")
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT type FROM expressions")
    leitner_system = {box: set() for box in [type for row in cur.fetchall() for type in row]}
    cur.execute("SELECT id, type FROM expressions")

    for id, type in cur.fetchall():
        leitner_system[type].add(id)

    cur.close()
    conn.close()

    return leitner_system

def set_leitner_system(sender, cur):
    leitner_system = create_leitner_system()
    retries.execution_with_backoff(
        cur, f"""
        INSERT INTO {os.environ["SCHEMA"]}.leitner (sender, system)
        VALUES (%s, %s)
        ON CONFLICT (sender) DO NOTHING
        """, (sender, repr(leitner_system)))
    return leitner_system

def get_leitner_system(sender, cur):
    retries.execution_with_backoff(
        cur, f"""
        SELECT system
        FROM {os.environ["SCHEMA"]}.leitner
        WHERE sender = %s""", (sender,))
    row = cur.fetchone()
    leitner_system = eval(row[0]) if row else set_leitner_system(sender, cur)
    return leitner_system

def get_random_box(leitner_system):
    remaining_boxes = sorted([box for box, ids in leitner_system.items() if ids])
    weights = [weight for weight in range(2 * len(remaining_boxes) - 1, 0, -2)]
    box = random.choices(remaining_boxes, weights)[0]
    return box

def get_random_expression(leitner_system, box):
    conn = sqlite3.connect("expressions.db")
    cur = conn.cursor()
    id = random.choice(sorted(leitner_system[box]))
    cur.execute(f"SELECT expression FROM expressions WHERE id = ?", (id,))
    expression = cur.fetchone()[0]
    cur.close()
    conn.close()
    return id, expression

def set_question(sender, answer, options, id, cur):
    retries.execution_with_backoff(
        cur, f"""
        INSERT INTO {os.environ["SCHEMA"]}.answers (sender, answer, options, expression_id)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (sender)
        DO UPDATE SET
            answer = EXCLUDED.answer,
            options = EXCLUDED.options,
            expression_id = EXCLUDED.expression_id
        """, (sender, answer, repr(options), id))