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
def completion_creation_with_backoff(client, system_prompt, user_prompt, temperature=None, response_format=None):
    response = client.chat.completions.create(
        model="gpt-4o-2024-08-06",
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        temperature=temperature,
        response_format=response_format
    )
    return response.choices[0].message.content