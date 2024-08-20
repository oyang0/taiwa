from fbmessenger import BaseMessenger
from fbmessenger.elements import Text
import os
import random
import sqlite3

class Taiwa(BaseMessenger):
    def __init__(self, page_access_token):
        self.page_access_token = page_access_token
        super(Taiwa, self).__init__(self.page_access_token)

    def message(self, message):
        action = message["message"].get("text")
        action = "".join(c for c in action if c.isalnum() or c.isspace())

        if "taiwa" in action.lower().split():
            conn = sqlite3.connect("taiwa.db")
            c = conn.cursor()

            c.execute("SELECT expression FROM expressions")
            messages = [row[0] for row in c.fetchall()]

            random_message = random.choice(messages)
            response = Text(text=random_message)
            self.send(response.to_dict())

            conn.close()

if __name__ == "__main__":
    messenger = Taiwa(page_access_token=os.environ['PAGE_ACCESS_TOKEN'])