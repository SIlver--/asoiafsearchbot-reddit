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

# commented already messaged are appended to avoid messaging again
commented = []

# already searched terms
termHistory = {}
termHistorySensitive = {}

# books
ALL = 'ALL'
AGOT = 'AGOT'
ACOK = 'ACOK'
ASOS = 'ASOS'
AFFC = 'AFFC'
ADWD = 'ADWD'
NONE = 'NONE'

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

    _book = None
    _searchTerm = None
    _sensitive = False
    _listOccurrence = []
    _rowOccurrence = None
    _total = 0
    _rowCount = 0
    _commentUser = None
    _message = None

    def parse_comment(self, comment):
        if comment.id not in commented and self._book != NONE:
            self._searchTerm = ''.join(re.split(
                                    r'Search(All|AGOT|ACOK|ASOS|AFFC|ADWD)!', 
                                    comment.body)[2:]
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

    def search_db(self):
        searchDb = Connect()
        # Take away whitespace and quotations at start and end
        self._searchTerm = self._searchTerm[1:-1]
        self._searchTerm = self._searchTerm.strip()
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
        

        # only search that book
        # needed to seperate next word
        """
        print mySqlSearch.format(
                table = table,
                col1 = column1,
                term = self._searchTerm,
                col2 = column2,
                bookSearch = bookSearch
            )"""
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
            storyLen = self.story_findall(row[5])
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
        
    def story_findall(self, story):
        """ 
        Uses the correct regex for search term 
        """
        if self._sensitive:
            return len(re.findall("(\W|^)" + self._searchTerm +
                            "(\W|$)", story))
        else:
            return len(re.findall("(\W|^)" + self._searchTerm.lower() +
                            "(\W|$)", story.lower()))
             
    def build_message(self):
        commentUser = (
                "######&#009;\n\n####&#009;\n\n#####&#009;\n\n"
                "**SEARCH TERM ({caps}): {term}** \n\n "
                 "Total Occurrence: {totalOccur} \n\n"
                 ">{message}"
                 "\n_____\n "
                 "{visual}"
                 "^(I'm ASOIAFSearchBot, I will display the occurrence of your "
                 "search term throughout the books. Only currently working in Spoiler All topics.) "
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
        # Avoids spam, limit amount of rows
        if self._rowCount < 31 and self._total > 0:
            self._message += (
                "| Series| Book| Chapter| Chapter Name| Chapter POV| Occurrence\n"
            )
            self._message += "|:{dash}|:{dash}|:{dash}|:{dash}|:{dash}|:{dash}|\n".format(
                dash='-' * 11
            )
            # Each element is changed to one string
            for row in self._listOccurrence:
                self._message += row + "\n"
        elif self._rowCount >= 31:
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
    def reply(self, comment):
        try:
            #comment.reply(_commentUser)
            print self._commentUser
        except (HTTPError, ConnectionError, Timeout, timeout) as err:
            print err
        except RateLimitExceeded as err:
            print err
            time.sleep(10)
        except APIException as err: # Catch any less specific API errors
            print err
        else:
            commented.append(comment.id)

    def spoiler_book(self, comment):
        #TODO: add the other regular expressions

        if re.match(
            "(\(|\[).*(published|(spoiler.*all)|(all.*spoiler)).*(\)|\])", 
            comment.link_title.lower()
        ):
            self._book = ALL
        if re.match(
            "REGEX HERE",
            comment.link_title.lower()
        ):
            self._book = AGOT
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
        allBooks = Books()
        for comment in comments:
            commentCount += 1
            allBooks.spoiler_book(comment)
            allBooks.parse_comment(comment)
            # Stops pesky searches like "a"
            if len(allBooks._searchTerm) > 3:
                allBooks.search_db()
                allBooks.build_message()
                allBooks.reply(comment)

        #except Exception as err:
            #print err
# =============================================================================
# RUNNER
# =============================================================================

if __name__ == '__main__':
    main()
    
