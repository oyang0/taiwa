import os
import requests
import retries

def set_commands():
    url = f"https://graph.facebook.com/v20.0/me/messenger_profile?access_token={os.environ["FB_PAGE_TOKEN"]}"
    json = {"commands": [{"locale": "default", "commands": 
                         [{key: command[key] for key in ("name", "description")} for command in commands]}]}
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, json=json, headers=headers)
    return response

def is_command(message):
    return ("text" in message["message"] and 
            any([command["name"] in message["message"]["text"] for command in commands]))

def delete_conversation(message, cur):
    retries.execution_with_backoff(
        cur, f"""
        DELETE FROM {os.environ["SCHEMA"]}.leitner
        WHERE sender = %s
        """, (message["sender"]["id"],))
    retries.execution_with_backoff(
        cur, f"""
        DELETE FROM {os.environ["SCHEMA"]}.answers
        WHERE sender = %s
        """, (message["sender"]["id"],))

def report_technical_problem(message, cur):
    retries.execution_with_backoff(
        cur, f"""
        INSERT INTO {os.environ["SCHEMA"]}.problems (sender, problem)
        VALUES (%s, %s)
        """, (message["sender"]["id"], message["message"]["text"]))

def process_command(message):
    conn, cur = retries.get_connection_and_cursor_with_backoff()
    indices = {message["message"]["text"].find(command["name"]): command["function"] for command in commands}
    indices.pop(-1, None)
    indices[min(indices)](message, cur)
    retries.commit_with_backoff(conn)
    retries.close_cursor_and_connection_with_backoff(cur, conn)

commands = [{"name": "delete",
             "description": "Delete this entire conversation",
             "function": delete_conversation},
            {"name": "report",
             "description": "Briefly explain what happened and how to repoduce the problem",
             "function": report_technical_problem}]