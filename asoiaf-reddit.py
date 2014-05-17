#!/usr/bin/env python -O

# =============================================================================
# IMPORTS
# =============================================================================

import ConfigParser
import MySQLdb
import praw
from praw.errors import APIException, RateLimitExceeded
import re
from requests.exceptions import HTTPError, ConnectionError, Timeout
from socket import timeout
import time

# =============================================================================
# GLOBALS
# =============================================================================

config = ConfigParser.ConfigParser()
config.read("asoiafsearchbot.cfg")

# Database info
host = config.get("SQL", "host")
user = config.get("SQL", "user")
passwd = config.get("SQL", "passwd")
db = config.get("SQL", "db")
table = config.get("SQL", "table")
column1 = config.get("SQL", "column1")
column2 = config.get("SQL", "column2")

# books
ALL = 'ALL'
AGOT = 'AGOT'
ACOK = 'ACOK'
ASOS = 'ASOS'
AFFC = 'AFFC'
ADWD = 'ADWD'

MAX_ROWS = 30

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

class Books(object):
    # commented already messaged are appended to avoid messaging again
    commented = []
    
    # already searched terms
    # TODO: Make this functionality
    termHistory = {}
    termHistorySensitive = {}
        
    def __init__(self, comment):
        self.comment = comment
        self._book = None
        self._searchTerm = ""
        self._sensitive = False
        self._listOccurrence = []
        self._rowOccurrence = 0
        self._total = 0
        self._rowCount = 0
        self._commentUser = ""
        self._message = ""

    def parse_comment(self):

        # Leaves only Search.! "Term"
        self._searchTerm = ''.join(re.split(
                                r'Search(All|AGOT|ACOK|ASOS|AFFC|ADWD)!', 
                                self.comment.body)[2:]
                            )

        # INSENSITIVE
        search_brackets = re.search('"(.*?)"', self._searchTerm)
        if search_brackets:
            self._searchTerm = search_brackets.group(0)
            self._sensitive = False
        

        # SENSITIVE
        search_tri = re.search('\((.*?)\)', self._searchTerm)
        if search_tri:
            self._searchTerm = search_tri.group(0)
            self._sensitive = True
        
        # Take away whitespace and quotations at start and end
        self._searchTerm = self._searchTerm[1:-1]
        self._searchTerm = self._searchTerm.strip()
        
        
    def build_query_sensitive(self):

        bookSearch = ""
        if self._book != ALL:
            bookSearch = ('AND {col2} = "{book}" ').format(self._book)

        if self._sensitive:
            mySqlSearch = (
                'SELECT * FROM {table} WHERE {col1} REGEXP BINARY '
                '"([[:blank:][:punct:]]|^){term}([[:punct:][:blank:]]|$)" '
                '{bookSearch}ORDER BY FIELD'
                '({col2}, "AGOT", "ACOK", "ASOS", "AFFC", "ADWD"), 2'
            )
        else:
            mySqlSearch = (
                'SELECT * FROM {table} WHERE lower({col1}) REGEXP '
                '"([[:blank:][:punct:]]|^){term}([[:punct:][:blank:]]|$)" '
                '{bookSearch}ORDER BY FIELD'
                '({col2}, "AGOT", "ACOK", "ASOS", "AFFC", "ADWD"), 2'
            )
        
        self.search_db(mySqlSearch)
        
    def search_db(self, mySqlSearch):

        searchDb = Connect()
        searchDb.execute(mySqlSearch.format(
                table = table,
                col1 = column1,
                term = self._searchTerm,
                col2 = column2,
                bookSearch = bookSearch
            )
        )
        
        self._rowOccurrence = searchDb.fetchall()
        storyLen = 0
        
        for row in self._rowOccurrence:

            if self._sensitive:
                storyLen = len(re.findall("(\W|^)" + self._searchTerm +
                                "(\W|$)", row[5]))
            else:
                storyLen = len(re.findall("(\W|^)" + self._searchTerm.lower() +
                                "(\W|$)", row[5]))
             
            self._listOccurrence.append(
                "| {series}| {book}| {number}| {chapter}| {pov}| {occur}".format(
                    series = row[0],
                    book = row[1],
                    number = row[2],
                    chapter = row[3],
                    pov = row[4],
                    occur = storyLen
                )
            )
            self._total += storyLen
            self._rowCount += 1 # track of limits
        
        searchDb.close()
        

    def build_message(self):
        commentUser = (
                "######&#009;\n\n####&#009;\n\n#####&#009;\n\n"
                "**SEARCH TERM ({caps}): {term}** \n\n "
                "Total Occurrence: {totalOccur} \n\n"
                ">{message}"
                "{visual}"
                "\n_____\n^(I'm ASOIAFSearchBot, I will display the occurrence "
                "of your search term throughout the books. " 
                "Only currently working in Spoiler All topics.) "
                "[^(More Info Here)]"
                "(http://www.reddit.com/r/asoiaf/comments/25amke/"
                "spoilers_all_introducing_asoiafsearchbot_command/)"
            )
        # Don't show eleement when no results
        visual = ""
        if self._total > 0:
            visual = (
                "\n[Visualization of the search term]"
                "(http://creative-co.de/labs/songicefire/?terms={term})"
                ).format(term = self._searchTerm)
                
        # Avoids spam
        if self._rowCount <= MAX_ROWS and self._total > 0:
            self._message += (
                "| Series| Book| Chapter| Chapter Name| Chapter POV| Occurrence\n"
            )
            self._message += "|:{dash}|:{dash}|:{dash}|:{dash}|:{dash}|:{dash}|\n".format(dash='-' * 11)
            # Each element added as a new row
            for row in self._listOccurrence:
                self._message += row + "\n"
        elif self._rowCount > MAX_ROWS:
                self._message = "**Excess number of chapters.**\n\n"
        elif self._total == 0:
                self._message = "**Sorry no results.**\n\n"
                
        caseSensitive = "CASE-SENSITIVE" if self._sensitive else "CASE-INSENSITIVE"    
        
        self._commentUser = commentUser.format(
            caps = caseSensitive,
            term = self._searchTerm,
            totalOccur = self._total,
            message = self._message,
            visual = visual
        )
        
        if self._sensitive:
            termHistorySensitive[self._searchTerm] = self._message
        else:
            termHistory[self._searchTerm.lower()] = self._message
            
            
    def reply(self, spoiler=False):
        try:
            if spoiler:
                self._commentUser = (
                    "######&#009;\n\n####&#009;\n\n#####&#009;\n\n"
                    ">**Sorry, fulfilling this request would be a spoiler.**\n\n"
                    "\n_____\n^(I'm ASOIAFSearchBot, I will display the occurrence "
                    "of your search term throughout the books. " 
                    "Only currently working in Spoiler All topics.) "
                    "[^(More Info Here)]"
                    "(http://www.reddit.com/r/asoiaf/comments/25amke/"
                    "spoilers_all_introducing_asoiafsearchbot_command/)"
                )
            print self._commentUser
            self.comment.reply(self._commentUser)

        except (HTTPError, ConnectionError, Timeout, timeout) as err:
            print err
        except RateLimitExceeded as err:
            print err
            time.sleep(10)
        except APIException as err: # Catch any less specific API errors
            print err
        else:
            self.commented.append(self.comment.id)

    def spoilerbook(self):
        #TODO: add the other regular expressions

        if re.match(
            "(\(|\[).*(published|(spoiler.*all)|"
            "(all.*spoiler)).*(\)|\])", 
            self.comment.link_title.lower()
        ):
            self._book = ALL
# =============================================================================
# MAIN
# =============================================================================


def main():
    """Main runner"""
    try:
        # Reddit Info
        user_agent = (
                "ASOIAFSearchBot -Help you find that comment"
                "- by /u/RemindMeBotWrangler")
        reddit = praw.Reddit(user_agent = user_agent)
        reddit_user = config.get("Reddit", "username")
        reddit_pass = config.get("Reddit", "password")
        reddit.login(reddit_user, reddit_pass)

    except Exception as err:
        print err

    while True:
        #try:
        commentCount = 0
        comments = praw.helpers.comment_stream(
            reddit, 'asoiaftest', limit = 100, verbosity = 0
        )
        
        for comment in comments:

            allBooks = Books(comment)
            commentCount += 1
            # Bot can't post in no spoilers
            # Bot will not reply to same message
            if re.search('Search(All|AGOT|ACOK|ASOS|AFFC|ADWD)!', 
                comment.body) is not None and 
                comment.id not in allBooks.commented:

                allBooks.spoiler_book()
                allBooks.parse_comment()
                allBooks.build_query_sensitive()
                allBooks.build_message()
                allBooks.reply()

            else:
                allBooks.reply(True)
 

        #except Exception as err:
            #print err
# =============================================================================
# RUNNER
# =============================================================================

if __name__ == '__main__':
    main()
