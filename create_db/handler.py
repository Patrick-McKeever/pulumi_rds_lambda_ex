from datetime import datetime
import pymysql
import os

db_endpoint = os.environ['DB_ENDPOINT']
db_user = os.environ['DB_USER']
db_pass = os.environ['DB_PASS']
db_name = os.environ['DB_NAME']

db_ip = db_endpoint.split(':')[0]
db_port = int(db_endpoint.split(':')[1])
conn = pymysql.connect(host=db_ip, user=db_user, port=db_port,
						passwd=db_pass, db=db_name,
						connect_timeout=5)

def handler(event, context):
	cur = conn.cursor()
	cur.execute("""CREATE TABLE IF NOT EXISTS users(
					user_id INT AUTO_INCREMENT PRIMARY KEY,
					name VARCHAR(30),
					email VARCHAR(30)
				)""")
	cur.execute("""CREATE TABLE IF NOT EXISTS jobs(
					job_id INT AUTO_INCREMENT PRIMARY KEY,
					submitter_id INT NOT NULL,
					date_submitted DATE,
					amt_offered DECIMAL(10, 2),
					FOREIGN KEY (submitter_id) REFERENCES users(user_id)
				)""")
	cur.execute("""CREATE TABLE IF NOT EXISTS materials(
					job_id INT NOT NULL,
					material VARCHAR(20),
					FOREIGN KEY (job_id) REFERENCES jobs(job_id)
				)""")
	cur.execute("""CREATE TABLE IF NOT EXISTS contracts(
					job_id INT NOT NULL,
					recipient_id INT NOT NULL,
					FOREIGN KEY (job_id) REFERENCES jobs(job_id),
					FOREIGN KEY (recipient_id) REFERENCES users(user_id),
					PRIMARY KEY (job_id, recipient_id)
				)""")