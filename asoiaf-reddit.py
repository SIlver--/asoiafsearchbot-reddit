#!/usr/bin/env python -O

# =============================================================================
# IMPORTS
# =============================================================================

import ConfigParser
import MySQLdb
import praw
from praw.errors import  APIException, RateLimitExceeded
import re
from requests.exceptions import HTTPError, ConnectionError, Timeout
from socket import timeout
import time

# =============================================================================
# GLOBALS
# =============================================================================

# Reads the config file
config = ConfigParser.ConfigParser()
config.read("asoiafsearchbot.cfg")

user_agent = ("ASOIAFSearchBot -Help you find that comment- by /u/RemindMeBotWrangler")
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
column2 = config.get("SQL","column2")

# commented already messaged are appended to avoid messaging again
commented = []

# =============================================================================
# CLASSES
# =============================================================================


class Connect(object):
    """
    DB connection class
    """
    connection = None
    cursor = None

    def __init__(self):
        self.connection = MySQLdb.connect(
            host=host, user=user, passwd=passwd, db=db
        )
        self.cursor = self.connection.cursor()

    def execute(self, command):
        self.cursor.execute(command)

    def fetchall(self):
        return self.cursor.fetchall()

    def commit(self):
        self.connection.commit()

    def close(self):
        self.connection.close()

# =============================================================================
# PUBLIC FUNCTIONS
# =============================================================================


def parse_comment(comment):
    """
    Parses comment for what term to search for
    Also decides if it's sensitive or insensitive
    """

    searchTerm = ""
    sensitive = False
    # remove everything before SearchAll!
    # Allows quotations to be used before SearchAll!
    originalComment = comment.body
    originalComment = ''.join(originalComment.split('SearchAll!')[1:])
    
    if (comment not in commented):
        commented.append(comment)
        print "in here"
        # INSENSITIVE    
        searchBrackets = re.search('"(.*?)"', originalComment)        
        if searchBrackets:
            searchTerm = searchBrackets.group(0)
            sensitive = False
            
        # SENSITIVE
        searchTri = re.search('\((.*?)\)', originalComment)
        if searchTri:
            searchTerm = searchTri.group(0)
            sensitive = True
        
        # Stop pesky searches like "a"
        if len(searchTerm) > 3:
            search_db(comment, searchTerm, sensitive)


def search_db(comment, term, sensitive):
    """
    Queries through DB counts occurrences for each chapter
    """
    searchDB = Connect()

    # Take away whitespace and quotations at start and end
    term = term[1:]
    term = term[:len(term) - 1]
    term = term.strip()

    
    total = 0 # Total Occurrence 
    rowCount = 0 # How many rows have been searched through
    
    if not sensitive:
        # INSENSITIVE SEARCH
        searchDB.execute('SELECT * FROM %s WHERE lower(%s) REGEXP "([[:blank:][:punct:]]|^)%s([[:punct:][:blank:]]|$)" ORDER BY FIELD(%s, "AGOT", "ACOK", "ASOS", "AFFC", "ADWD")' %(table, column1, term, column2))
        data = searchDB.fetchall()
        listOccurence = []
        
        # Counts occurrences in each row and
        # adds itself to listOccurrence for message
        for row in data:
            listOccurence.append("| " + str(row[0]) + "| " + str(row[1]) + "| " + str(row[3]) + "| " + str(row[4]) + "| " + str(row[5].lower().count(term.lower())))
            total += row[5].lower().count(term.lower())
            rowCount += 1

    else:
        # SENSITIVE SEARCH
        searchDB.execute('SELECT * FROM %s WHERE %s REGEXP BINARY "([[:blank:][:punct:]]|^)%s([[:punct:][:blank:]]|$)" ORDER BY FIELD(%s, "AGOT", "ACOK", "ASOS", "AFFC", "ADWD")' %(table, column1, term, column2))
        data = searchDB.fetchall()
        listOccurence = []
        
        # Counts occurrences in each row and
        # adds itself to listOccurrence for message
        for row in data:
            listOccurence.append("| " + str(row[0]) + "| " + str(row[1]) + "| " + str(row[3]) + "| " + str(row[4]) + "| "  + str(row[5].count(term)))
            total += row[5].count(term)
            rowCount += 1
            
    searchDB.close()
    send_message(comment, listOccurence, rowCount, total, term, sensitive)


def send_message(comment, list, rowCount, total, term, sensitive):
    """
    Sends message to user with the requested information
    """
    
    try:
        message = ""
        comment_to_user = "**SEARCH TERM ({0}): {1}** \n\n Total Occurrence: {2} \n\n{3} [Visualization of the search term](http://creative-co.de/labs/songicefire/?terms={1})\n_____\n ^(Hello, I'm ASOIAFSearchBot, I will display the occurrence of your term and what chapters it was found in.)[^(More Info Here)](http://www.reddit.com/r/asoiaf/comments/25amke/spoilers_all_introducing_asoiafsearchbot_command/)"
        
        # Avoid spam, limit amount of rows
        if rowCount < 30 and total > 0:
            message += "| Series" + "| Book"  + "| Chapter Name" + "| Chapter POV" + "| Occurrence\n"
            message += "|:-----------" + "|:-----------" + "|:-----------" + "|:-----------" + "|:-----------|\n"
            # Each element is changed to one string
            for row in list:
                message += row + "\n"
        elif rowCount > 30:
            message = "**Excess amount of chapters.**\n"
        elif total == 0:
            message = "**Sorry no results.**\n\n"
        
        caseSensitive = ""
        if sensitive:
            caseSensitive = "CASE-SENSITIVE"
        else:
            caseSensitive = "CASE-INSENSITIVE"
        
        comment.reply(comment_to_user.format(caseSensitive, term, total, message))
        print comment_to_user.format(caseSensitive, term, total, message)
    except (HTTPError, ConnectionError, Timeout, timeout), e:
        print e
    except APIException, e:
        print e
    except RateLimitExceeded, e:
        print e
        time.sleep(10)

# =============================================================================
# MAIN
# =============================================================================


def main():
    while True:
        try:
            # Grab all new comments from /r/asoiaf
            comments = praw.helpers.comment_stream(reddit, 'asoiaf', limit=None, verbosity=0)
            comment_count = 0
            # Loop through each comment
            for comment in comments:
                comment_count += 1
                if "SearchAll!" in comment.body:
                    parse_comment(comment)
                # end loop after 50
                if comment_count == 50:
                    break
            print "sleeping"
            time.sleep(25)
        except Exception, e:
            print e

# =============================================================================
# RUNNER
# =============================================================================

if __name__ == '__main__':
    main()


























