import os
import psycopg2

from main import messenger

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

cur.execute(f"CREATE SCHEMA IF NOT EXISTS {os.environ["SCHEMA"]};")

cur.execute(f"DROP TABLE IF EXISTS {os.environ["SCHEMA"]}.leitner")
cur.execute(f"DROP TABLE IF EXISTS {os.environ["SCHEMA"]}.questions")
cur.execute(f"DROP TABLE IF EXISTS {os.environ["SCHEMA"]}.problems")
cur.execute(f"DROP TABLE IF EXISTS {os.environ["SCHEMA"]}.messages")

cur.execute(f"""
CREATE TABLE IF NOT EXISTS {os.environ["SCHEMA"]}.leitner (
	id SERIAL PRIMARY KEY,
	sender TEXT NOT NULL UNIQUE,
	system TEXT NOT NULL
)
""")

cur.execute(f"""
CREATE TABLE IF NOT EXISTS {os.environ["SCHEMA"]}.questions (
	id SERIAL PRIMARY KEY,
	sender TEXT NOT NULL UNIQUE,
    question TEXT NOT NULL,
    options TEXT NOT NULL,
	answer TEXT NOT NULL,
	expression_id SMALLINT NOT NULL
)
""")

cur.execute(f"""
CREATE TABLE IF NOT EXISTS {os.environ["SCHEMA"]}.problems (
	id SERIAL PRIMARY KEY,
	sender TEXT NOT NULL,
	problem TEXT NOT NULL
)
""")

cur.execute(f"""
CREATE TABLE IF NOT EXISTS {os.environ["SCHEMA"]}.messages (
	id SERIAL PRIMARY KEY,
	message TEXT NOT NULL UNIQUE,
    timestamp BIGINT
)
""")

conn.commit()
cur.close()
conn.close()

messenger.init_bot()