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

    _comments = None
    _comment = None
    _book = None
    _searchTerm = None
    _sensitive = False
    _searchDb = Connect()
    _termOccurrence = []
    _rowOccurrence = None
    _total = None
    _rowCount = None
    _commentUser = None
    _message = None
    
    
    def __init__(self, comments):
        pass
    def parse_comment(self):
        pass
        if _comment.id not in commented and book != NONE:
            _searchTerm = ''.join(re.split(
                                    r'Search(All|AGOT|ACOK|ASOS|AFFC|ADWD)!', 
                                    _searchTerm)[2:]
                                )
            # INSENSITIVE
            search_brackets = re.search('"(.*?)"', _searchTerm)
            if search_brackets:
                _searchTerm = search_brackets.group(0)
                _sensitive = False
            

            # SENSITIVE
            search_tri = re.search('\((.*?)\)', _searchTerm)
            if search_tri:
                _searchTerm = search_tri.group(0)
                _sensitive = True

    def search_db(self):
        pass
        if _sensitive:
            mySqlSearch = (
                'SELECT * FROM {table} WHERE {col1} REGEXP BINARY '
                '"([[:blank:][:punct:]]|^){term}([[:punct:][:blank:]]|$)" '
                '({book})ORDER BY FIELD'
                '({col2}, "AGOT", "ACOK", "ASOS", "AFFC", "ADWD"), 2'
            )
        else:
            mySqlSearch = (
                'SELECT * FROM {table} WHERE lower({col1}) REGEXP '
                '"([[:blank:][:punct:]]|^){term}([[:punct:][:blank:]]|$)" '
                '({book})ORDER BY FIELD'
                '({col2}, "AGOT", "ACOK", "ASOS", "AFFC", "ADWD"), 2'
            )
        

        # omly search that book
        bookSearch = ""
        if _book != ALL:
            bookSearch = _book + " " # needed to seperate next word

        _searchDb.execute(mySqlSearch.format(
                table = table,
                col1 = column1
                term = _searchTerm,
                col2 = column2,
                book = _book
            )
        )
        _rowOccurrence = searchDb.fetchall()

        for row in _rowOccurrence:
            storyLen = story_findall(row[5])
            _listOccurrence.append(
                "| {series}| {book}| {number}| {chapter}| {pov}| {occur}".format(
                    series = row[0],
                    book = row[1],
                    number = row[2],
                    chapter = row[3],
                    pov = row[4],
                    occur = storyLen
                )
            _total += storyLen
                )
            _rowCount += 1 # track of limits
        
        _searchDb.close()
        
    def story_findall(self, story):
        """ 
        Uses the correct regex for search term 
        """
        if _sensitive:
            return len(re.findall("(\W|^)" + _searchTerm +
                            "(\W|$)", story)
        else:
            return len(re.findall("(\W|^)" + _searchTerm.lower() +
                            "(\W|$)", story.lower())
             
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
        if _total > 0:
            visual = (
                "\n[Visualization of the search term]"
                "(http://creative-co.de/labs/songicefire/?terms={term})"
                ).format(term = _searchTerm)
        # Avoids spam, limit amount of rows
        if _rowCount < 31 and _total > 0:
            _message += (
                "| Series| Book| Chapter| Chapter Name| Chapter POV| Occurrence\n"
            )
            _message += "|:{dash}|:{dash}|:{dash}|:{dash}|:{dash}|:{dash}|\n".format(
                dash='-' * 11
            )
            # Each element is changed to one string
            for row in _listOccurrence:
                _message += row + "\n"
        elif _rowCount => 31:
                _message = "**Excess number of chapters.**\n\n"
        elif _total == 0:
                _message = "**Sorry no results.**\n\n"
                
        caseSensitive = "CASE-SENSITIVE" if _sensitive else "CASE-INSENSITIVE"    
        
        _commentUser = commentUser.format(
            caps = caseSensitive,
            term = _searchTerm,
            totalOccur = total,
            message = _message
        )
        
        if _sensitive:
            termHistorySensitive[term] = _message
        else:
            termHistory[term.lower()] = _message
    def reply(self):
        try:
            #comment.reply(_commentUser)
            print _commentUser
        except (HTTPError, ConnectionError, Timeout, timeout) as err:
            print err
        except RateLimitExceeded as err:
            print err
            time.sleep(10)
        except APIException as err: # Catch any less specific API errors
            print err
        else:
            commented.append(comment.id)

    def spoiler_book(self):
        #TODO: add the other regular expressions 
        if re.match(
            "(\(|\[).*(published|(spoiler.*all)|(all.*spoiler)).*(\)|\])", 
            _comment.link_title.lower()
        ):
            _book = ALL
        if re.match(
            "REGEX HERE",
            _comment.link_title.lower()
        ):
            _book = AGOT

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
        try:
            commentCount = 0
            allBooks = Books()
            for comment in praw.helpers.comment_stream(
                reddit, 'asoiaftest', limit = None, verbosity = 0
            ):
                comment_count += 1
                spoiler_book()
                parse_comment()
                # Stops pesky searches like "a"
                if len(allBook._searchTerm) > 3:
                    search_db
                build_message()

        except Exception as err:
            print err
# =============================================================================
# RUNNER
# =============================================================================

if __name__ == '__main__':
    main()
    
