import os
import requests

def set_commands():
    url = f"https://graph.facebook.com/v20.0/me/messenger_profile?access_token={os.environ["FB_PAGE_TOKEN"]}"
    json = {
        "commands": [
            {
                "locale": "default",
                "commands": [
                    {"name": "flights", "description": "Find real-time flights and fares"},
                    {"name": "hotels", "description": "Find real-time hotel rooms and rates"},
                    {"name": "currency", "description": "Find real-time currency exchange rates"},
                    {"name": "weather", "description": "Find real-time weather reports and forecasts"}
                ]
            }
        ]
    }
    response = requests.post(url, json=json, headers={"Content-Type": "application/json"})