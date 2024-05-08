from datetime import datetime
import pymysql
import json
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
	try:
		event = event['queryStringParameters']
		if event == None:
			return {
				'statusCode': 500,
				'body': 'No request params offered'
			}

		with conn.cursor() as cursor:
			# Construct the SQL query based on the provided parameters
			sql = "SELECT * FROM jobs WHERE amt_offered >= %s"
			params = [event['amt_offered']]

			if 'materials' in event:
				sql += " AND job_id IN (SELECT job_id FROM materials WHERE material IN (%s))"
				params.append(",".join(["'%s'" % material for material in event['materials']]))

			sql += " ORDER BY date_submitted"

			# Execute the query
			cursor.execute(sql, params)

			# Fetch all results
			result = cursor.fetchall()

			# Convert the results to a list of dictionaries
			jobs = []
			for row in result:
				job = {
					'job_id': row[0],
					'submitter_id': row[1],
					'date_submitted': str(row[2]),
					'amt_offered': float(row[3])
					# Add more fields if needed
				}
				jobs.append(job)
	except Exception as e:
		return {
			'statusCode': 500,
			'body': json.dumps(str(e))
		}



	# Return the list of jobs as JSON
	return {
		'statusCode': 200,
		'body': json.dumps(jobs)
	}
