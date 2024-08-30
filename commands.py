import os
import requests
import retries

from fbmessenger.elements import Text

def set_commands():
    url = f"https://graph.facebook.com/v20.0/me/messenger_profile?access_token={os.environ["FB_PAGE_TOKEN"]}"
    json = {"commands": [{"locale": "default", "commands": 
                         [{key: command[key] for key in ("name", "description")} for command in commands]}]}
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, json=json, headers=headers)
    return response

def is_command(message):
    return "text" in message and any([command["name"] in message["text"] for command in commands])

def set_character_limit(message, cur):
    try:
        character_limit = int(message["message"]["text"].lower().replace("limit", ""))

        if character_limit < 1 or character_limit > 20:
            raise ValueError("character limit is less than 1 or greater than 20")

        retries.execution_with_backoff(cur, f"""
            INSERT INTO {os.environ["SCHEMA"]}.characters (sender, limit)
            VALUES (%s, %s)
            """, (message["sender"]["id"], character_limit))
        response = "Character limit set"
    except ValueError:
        response = "Missing character limit"
    
    return response

def delete_conversation(message, cur):
    retries.execution_with_backoff(cur, f"""
        DELETE FROM {os.environ["SCHEMA"]}.leitner
        WHERE sender = %s
        """, (message["sender"]["id"],))
    retries.execution_with_backoff(cur, f"""
        DELETE FROM {os.environ["SCHEMA"]}.questions
        WHERE sender = %s
        """, (message["sender"]["id"],))
    response = "Conversation deleted"
    return response

def report_technical_problem(message, cur):
    if message["message"]["text"].lower().replace("report", ""):
        retries.execution_with_backoff(cur, f"""
            INSERT INTO {os.environ["SCHEMA"]}.problems (sender, problem)
            VALUES (%s, %s)
            """, (message["sender"]["id"], message["message"]["text"]))
        response = "Technical problem reported"
    else:
        response = "Missing technical problem"

    return response

def process_command(message, cur):
    indices = {message["message"]["text"].find(command["name"]): command["function"] for command in commands}
    indices = {index: function for index, function in indices.items() if index != -1}
    response = indices[min(indices)](message, cur)
    response = Text(text=response)
    return (response.to_dict(),)

commands = [{"name": "limit",
             "description": "Set character limit for multiple choice options",
             "function": set_character_limit},
            {"name": "delete",
             "description": "Delete this entire conversation",
             "function": delete_conversation},
            {"name": "report",
             "description": "Briefly explain what happened and how to repoduce the problem",
             "function": report_technical_problem}]