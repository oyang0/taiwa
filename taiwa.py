from fbmessenger import BaseMessenger
from fbmessenger.elements import Text
import random
import sqlite3

class Taiwa(BaseMessenger):
    def __init__(self, page_access_token):
        self.page_access_token = page_access_token
        super(Taiwa, self).__init__(self.page_access_token)

    def message(self, message):
        action = message["message"].get("text")
        if action == "taiwa":
            conn = sqlite3.connect("taiwa.db")
            c = conn.cursor()

            c.execute("SELECT message FROM messages")
            messages = [row[0] for row in c.fetchall()]

            random_message = random.choice(messages)
            response = Text(text=random_message)
            self.send(response.to_dict())

            conn.close()

if __name__ == "__main__":
    page_access_token = input("Page access token: ")
    messenger = Taiwa(page_access_token=page_access_token)