import os
import psycopg2

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

cur.execute(f"CREATE SCHEMA IF NOT EXISTS {os.environ["SCHEMA"]};")

cur.execute(f"""
CREATE TABLE IF NOT EXISTS {os.environ["SCHEMA"]}.leitner (
	id SERIAL PRIMARY KEY,
	sender TEXT NOT NULL UNIQUE,
	system TEXT NOT NULL
);
""")

cur.execute(f"""
CREATE TABLE IF NOT EXISTS {os.environ["SCHEMA"]}.answers (
	id SERIAL PRIMARY KEY,
	sender TEXT NOT NULL UNIQUE,
	answer TEXT NOT NULL,
	options TEXT NOT NULL,
	expression_id INTEGER NOT NULL
);
""")

cur.execute(f"""
CREATE TABLE IF NOT EXISTS {os.environ["SCHEMA"]}.problems (
	id SERIAL PRIMARY KEY,
	sender TEXT NOT NULL,
	problem TEXT NOT NULL
);
""")

conn.commit()
cur.close()
conn.close()