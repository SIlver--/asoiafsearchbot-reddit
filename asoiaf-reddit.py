import praw
import MySQLdb
import ConfigParser
import re
import time
from requests.exceptions import HTTPError, ConnectionError, Timeout
from praw.errors import ExceptionList, APIException, InvalidCaptcha, InvalidUser, RateLimitExceeded
from socket import timeout

# Reads the config file
config = ConfigParser.ConfigParser()
config.read("asoiafsearchbot.cfg")

user_agent = ("ASOIAFSearchBot v1.0 by /u/RemindMeBotWrangler")
reddit = praw.Reddit(user_agent = user_agent)

# Reddit Info
reddit_user =  config.get("Reddit", "username")
reddit_pass = config.get("Reddit", "password")
reddit.login(reddit_user, reddit_pass)

# Database info
host = config.get("SQL", "host")
user = config.get("SQL", "user")
passwd = config.get("SQL", "passwd")
db = config.get("SQL", "db")
table = config.get("SQL", "table")
column1 = config.get("SQL","column1")

# commented already messaged are appended to avoid messaging again
commented = []

class Connect:
	"""
	DB connection class
	"""
	connection = None
	cursor = None

	def __init__(self):
		self.connection = MySQLdb.connect(host= host, user = user, passwd= passwd, db= db)
		self.cursor = self.connection.cursor()

	def execute(self, command):
		self.cursor.execute(command)

	def fetchall(self):
		return self.cursor.fetchall()

	def commit(self):
		self.connection.commit()

	def close(self):
		self.connection.close()

def parse_comment(comment):
	"""
	Parses comment for what term to search for
	Also decides if it's sensitive or insensitive
	"""

	searchTerm = ""
	sensitive = False
	if (comment not in commented):
		
		#INSENSITIVE
		searchTri = re.search('\((.*?)\)', comment.body)
		if searchTri:
			searchTerm = searchTri.group(0)
			sensitive = False
		
		#SENSITIVE	
		searchBrackets = re.search('\[(.*?)\]', comment.body)		
		if searchBrackets:
			searchTerm = searchBrackets.group(0)
			sensitive = True

	search_db(comment, searchTerm, sensitive)

def search_db(comment, term, sensitive):
	"""
	Queries through DB counts occurrences for each chapter
	"""
	searchDB = Connect()
	
	# Take away whitespace and '(' && '[' at start and end
	term = term[1:]
	term = term[:len(term) - 1]
	term = term.strip()

	
	
	total = 0 # Total Occurrence 
	rowCount = 0 # How many rows have been searched through
	
	if not sensitive:
		# INSENSITIVE SEARCH
		searchDB.execute("SELECT * FROM %s WHERE %s REGEXP '[[:<:]]%s[[:>:]]'" %(table, column1, term))
		data = searchDB.fetchall()
		listOccurence = []
		
		# Counts occurrences in each row and
		# adds itself to listOccurrence for message
		for row in data:
			listOccurence.append(str(row[0]) + "-" + str(row[1]) + "-" + str(row[2]) + "-" + str(row[3]) + "-" + str(row[4]) + "- Occurrence:" + str(row[5].lower().count(term.lower())))
			total += row[5].lower().count(term.lower())
			rowCount += 1

	else:
		# SENSITIVE SEARCH
		searchDB.execute("SELECT * FROM %s WHERE %s REGEXP BINARY '[[:<:]]%s[[:>:]]'" %(table, column1, term))
		data = searchDB.fetchall()
		listOccurence = []
		
		# Counts occurrences in each row and
		# adds itself to listOccurrence for message
		for row in data:
			listOccurence.append(str(row[0]) + "-" + str(row[1]) + "-" + str(row[2]) + "-" + str(row[3]) + "-" + str(row[4]) + "- Occurrence:" + str(row[5].count(term)))
			total += row[5].count(term)
			rowCount += 1
			
	searchDB.close()
	send_message(comment, listOccurence, rowCount, term, sensitive)
	
def send_message(comment, list, rowCount, term, sensitive):
	"""
	Sends message to user with the requested information
	"""
	
	try:
		message = ""
		comment_to_user = "**SEARCH TERM ({0}): {1}** \n\n Total Occurrence: {2} \n\n {3}"
		
		# Avoid spam, limit amount of rows
		if rowCount < 30:
			# Each element is changed to one string
			for row in list:
				message += row + "\n\n"
		else:
			message = "Sorry, excess amount of different chapters."
		
		caseSensitive = ""
		if sensitive:
			caseSensitive = "CASE-SENSTIVE"
		else:
			caseSensitive = "CASE-INSENSTIVE"
		comment.reply(comment_to_user.format(caseSensitive, term, rowCount, message))
	except (HTTPError, ConnectionError, Timeout, timeout), e:
		print e
	except APIException, e:
		print e
	except RateLimitExceeded, e:
		print e
		time.sleep(10)
		
def main():
	while True:

		# Grab all new comments from /r/asoiaf
		comments = praw.helpers.comment_stream(reddit, 'all', limit=None, verbosity=0)
		comment_count = 0
		# Loop through each comment
		for comment in comments:
			comment_count += 1
			if "SearchAll!" in comment.body:
				print "Found it!"
				parse_comment(comment)
			# end loop after 1000
			if comment_count == 1000:
				break
		time.sleep(25)

			
main()






























