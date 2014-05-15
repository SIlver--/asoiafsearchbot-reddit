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


# commented already messaged are appended to avoid messaging again
commented = []

# already searched terms
term_history = {}
term_history_sensitive = {}

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

    _comments=None
    _comment=None
    _book=None
    _searchTerm=None
    _sensitive=False

    def __init__(self, comments):
        pass
    def parse_comment(self):
        pass
        if _comment.id not in commented and book != NONE:
            _searchTerm=''.join(re.split(
                                    r'Search(All|AGOT|ACOK|ASOS|AFFC|ADWD)!', 
                                    _searchTerm)[2:]
                                )
            # INSENSITIVE
            search_brackets=re.search('"(.*?)"', _searchTerm)
            if search_brackets:
                _searchTerm=search_brackets.group(0)
                _sensitive=False
            

            # SENSITIVE
            search_tri=re.search('\((.*?)\)', _searchTerm)
            if search_tri:
                _searchTerm=search_tri.group(0)
                _sensitive=True

    def search_db():
        pass
        searchDb=Connect()


    def spoiler_book(self):
        #TODO: add the other regular expressions 
        if re.match(
            "(\(|\[).*(published|(spoiler.*all)|(all.*spoiler)).*(\)|\])", 
            _comment.link_title.lower()
        ):
            _book=ALL
        if re.match(
            "REGEX HERE",
            _comment.link_title.lower()
        ):
            _book=AGOT

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
        reddit=praw.Reddit(user_agent=user_agent)
        reddit_user=config.get("Reddit", "username")
        reddit_pass=config.get("Reddit", "password")
        reddit.login(reddit_user, reddit_pass)

    except Exception as err:
        print err

    while True:
        try:
            commentCount=0
            allBooks=Books()
            for comment in praw.helpers.comment_stream(
                reddit, 'asoiaf', limit=None, verbosity=0
            ):
                comment_count += 1
                spoiler_book()
                parse_comment()
                # Stops pesky searches like "a"
                if len(allBook._searchTerm) > 3:
                    search_db


        except Exception as err:
            print err
# =============================================================================
# RUNNER
# =============================================================================

if __name__ == '__main__':
    main()
