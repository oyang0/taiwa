import messages
import os
import psycopg2

from tenacity import retry, stop_after_attempt, wait_random_exponential

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6), reraise=True)
def connection_with_backoff():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    return conn

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6), reraise=True)
def get_cursor_with_backoff(conn):
    cur = conn.cursor()
    return cur

def get_connection_and_cursor_with_backoff():
    conn = connection_with_backoff()
    cur = get_cursor_with_backoff(conn)
    return conn, cur

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6), reraise=True)
def execution_with_backoff(cur, query, vars = None):
    cur.execute(query, vars)

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6), reraise=True)
def commit_with_backoff(conn):
    conn.commit()

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6), reraise=True)
def close_cursor_with_backoff(cur):
    cur.close()

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6), reraise=True)
def close_connection_with_backoff(conn):
    conn.close()

def close_cursor_and_connection_with_backoff(cur, conn):
    close_connection_with_backoff(cur)
    close_connection_with_backoff(conn)

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6), reraise=True)
def completion_creation_with_backoff(client, system_prompt, content, temperature=None, response_format=None):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": content
            }
        ],
        temperature=temperature,
        response_format=response_format
    )
    return response.choices[0].message.content

def set_character_limit(sender, cur):
    character_limit = 20
    execution_with_backoff(cur, f"""
        INSERT INTO {os.environ["SCHEMA"]}.characters (sender, limit)
        VALUES (%s, %s)
        """, (sender, character_limit))
    return character_limit

def get_character_limit(sender, cur):
    execution_with_backoff(cur, f"SELECT limit FROM {os.environ["SCHEMA"]}.characters WHERE sender = %s", (sender,))
    row = cur.fetchone()
    return row[0] if row else set_character_limit(sender, cur)

def is_correct(question, sender, cur):
    character_limit = get_character_limit(sender, cur)

    if len(question) > 640:
        return False
    elif len(question["options"]) > 3:
        return False
    elif any([len(option) > character_limit for option in question["options"]]):
        return False
    elif question["answer"] not in question["options"]:
        return False

    return True

def get_question(expression, sender, cur, client):
    question, attempt, attempts = None, 0, 6

    while (not question or not messages.is_correct(question, sender, cur)) and attempt < attempts: 
        question = messages.get_question(expression, client)
        attempt += 1
    
    if attempt == attempts:
        raise Exception("Failed to create multiple choice question")
    
    return question
