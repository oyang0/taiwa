import os
import psycopg2

from urllib.parse import urlparse

result = urlparse(os.environ["DATABASE_URL"])
conn = psycopg2.connect(
    dbname=result.path[1:],
    user=result.username,
    password=result.password,
    host=result.hostname
)
cur = conn.cursor()
cur = conn.cursor()

for stage in ("taiwa_staging", "taiwa_staging"):
	cur.execute(f"CREATE SCHEMA IF NOT EXISTS {stage};")

	cur.execute(f"""
	CREATE TABLE IF NOT EXISTS {stage}.leitner (
		id SERIAL PRIMARY KEY,
		sender TEXT NOT NULL UNIQUE,
		system TEXT NOT NULL
	);
	""")

	cur.execute(f"""
	CREATE TABLE IF NOT EXISTS {stage}.answers (
		id SERIAL PRIMARY KEY,
		sender TEXT NOT NULL UNIQUE,
		answer TEXT NOT NULL,
		options TEXT NOT NULL,
		expression_id INTEGER NOT NULL
	);
	""")

conn.commit()
cur.close()
conn.close()