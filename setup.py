import os
import psycopg2

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

for stage in ("taiwa_staging", "taiwa_production"):
	cur.execute(f"CREATE SCHEMA IF NOT EXISTS {stage};")

	cur.execute(f"DROP TABLE IF EXISTS {stage}.leitner")

	cur.execute(f"""
	CREATE TABLE IF NOT EXISTS {stage}.leitner (
		id SERIAL PRIMARY KEY,
		sender TEXT NOT NULL UNIQUE,
		system TEXT NOT NULL
	);
	""")

	cur.execute(f"DROP TABLE IF EXISTS {stage}.answers")

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