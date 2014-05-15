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

# Reads the config file
config = ConfigParser.ConfigParser()
config.read("asoiafsearchbot.cfg")

user_agent = ("ASOIAFSearchBot -Help you find that comment- by /u/RemindMeBotWrangler")
reddit = praw.Reddit(user_agent=user_agent)

# Reddit Info
reddit_user = config.get("Reddit", "username")
reddit_pass = config.get("Reddit", "password")
reddit.login(reddit_user, reddit_pass)

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
term_history = {}
term_history_sensitive = {}

# books
ALL = 'ALL'
AGOT = 'AGOT'
ACOK = 'ACOK'
ASOS = 'ASOS'
AFFC = 'AFFC'
ADWD = 'ADWD'

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

def parse_comment(comment, book):
    """
    Parses comment for what term to search for
    Also decides if it's sensitive or insensitive
    """
    if comment.id not in commented:
        search_term = ""
        sensitive = False
        # remove everything before SearchCommand!
        # Allows quotations to be used before SearchCommand!
        original_comment = comment.body

        if (book == ALL):
            original_comment = ''.join(original_comment.split('SearchAll!')[1:])
        elif (book == AGOT):
            original_comment = ''.join(original_comment.split('SearchAGOT!')[1:])
        elif (book == ACOK):
            original_comment = ''.join(original_comment.split('SearchACOK!')[1:])
        elif (book == ASOS):
            original_comment = ''.join(original_comment.split('SearchASOS!')[1:])
        elif (book == AFFC):
            original_comment = ''.join(original_comment.split('SearchAFFC!')[1:])
        elif (book == ADWD):
            original_comment = ''.join(original_comment.split('SearchADWD!')[1:])

        # Only reply to threads with Spoiler All
        # TODO: Expand to each book spoiler tag scope
        if re.match("(\(|\[).*(published|(spoiler.*all)|(all.*spoiler)).*(\)|\])", comment.link_title.lower()):
            # INSENSITIVE
            search_brackets = re.search('"(.*?)"', original_comment)
            if search_brackets:
                search_term = search_brackets.group(0)
                sensitive = False

            # SENSITIVE
            search_tri = re.search('\((.*?)\)', original_comment)
            if search_tri:
                search_term = search_tri.group(0)
                sensitive = True

            # Stop pesky searches like "a"
            if len(search_term) > 3:
                search_db(comment, search_term, sensitive, book)

        else:
            message = (
                "######&#009;\n\n####&#009;\n\n#####&#009;\n\n"
                ">**Sorry, fulfilling this request would be a spoiler.**\n\n"
                "_____\n"
                "^(I'm ASOIAFSearchBot, I will display the occurrence of your "
                "search term throughout the books. Only currently working in Spoiler All topics.) "
                "[^(More Info Here)]"
                "(http://www.reddit.com/r/asoiaf/comments/25amke/"
                "spoilers_all_introducing_asoiafsearchbot_command/)\n\n"
            )
            reply(comment, message)
 

def search_db(comment, term, sensitive, book):
    """
    Queries through DB counts occurrences for each chapter
    """
    search_database = Connect()

    # Take away whitespace and quotations at start and end
    term = term[1:-1]
    term = term.strip()

    total = 0  # Total Occurrence
    row_count = 0  # How many rows have been searched through

    if not sensitive:

        # INSENSITIVE SEARCH
        if book == ALL:
            search_database.execute(
                'SELECT * FROM {table} WHERE lower({col1}) REGEXP '
                '"([[:blank:][:punct:]]|^){term}([[:punct:][:blank:]]|$)" '
                'ORDER BY FIELD'
                '({col2}, "AGOT", "ACOK", "ASOS", "AFFC", "ADWD"), 2'.format(
                    table=table,
                    col1=column1,
                    term=term,
                    col2=column2
                )
            )

       # Searches through individual books
        else:
            search_database.execute(
            'SELECT * FROM {table} WHERE lower({col1}) REGEXP '
            '"([[:blank:][:punct:]]|^){term}([[:punct:][:blank:]]|$)" '
            'AND {col2} = "{book}" '
            'ORDER BY FIELD'
            '({col2}, "AGOT", "ACOK", "ASOS", "AFFC", "ADWD"), 2'.format(
                    table=table,
                    col1=column1,
                    term=term,
                    col2=column2,
                    book=book
                )
            )

        data = search_database.fetchall()
        list_occurrence = []

        # Counts occurrences in each row and
        # adds itself to listOccurrence for message
        for row in data:
            list_occurrence.append(
                "| {series}| {book}| {number}| {chapter}| {pov}| {occur}".format(
                    series=row[0],
                    book=row[1],
                    number=row[2],
                    chapter=row[3],
                    pov=row[4],
                    occur=len(
                        re.findall("(\W|^)" + term.lower() +
                                   "(\W|$)", row[5].lower())
                    )
                )
            )
            total += len(
                re.findall("(\W|^)" + term.lower() +
                           "(\W|$)", row[5].lower())
            )
            row_count += 1

    else:

        # SENSITIVE SEARCH
        if book == ALL:

            search_database.execute(
                'SELECT * FROM {table} WHERE {col1} REGEXP BINARY '
                '"([[:blank:][:punct:]]|^){term}([[:punct:][:blank:]]|$)" '
                'ORDER BY FIELD'
                '({col2}, "AGOT", "ACOK", "ASOS", "AFFC", "ADWD"), 2'.format(
                    table=table,
                    col1=column1,
                    term=term,
                    col2=column2
                )
            )

        # Searches through individual books
        else:
            search_database.execute(
                'SELECT * FROM {table} WHERE {col1} REGEXP BINARY '
                '"([[:blank:][:punct:]]|^){term}([[:punct:][:blank:]]|$)" '
                'AND {col2} = "{book}" '
                'ORDER BY FIELD'
                '({col2}, "AGOT", "ACOK", "ASOS", "AFFC", "ADWD"), 2'.format(
                    table=table,
                    col1=column1,
                    term=term,
                    col2=column2,
                    book=book
                )
            )

        data = search_database.fetchall()
        list_occurrence = []
        # Counts occurrences in each row and
        # adds itself to listOccurrence for message
        for row in data:
            list_occurrence.append(
                "| {series}| {book}| {number}| {chapter}| {pov}| {occur}".format(
                    series=row[0],
                    book=row[1],
                    number=row[2],
                    chapter=row[3],
                    pov=row[4],
                    occur=len(
                        re.findall("(\W|^)" + term +
                                   "(\W|$)", row[5])
                    )
                )
            )
            total += len(
                re.findall("(\W|^)" + term +
                           "(\W|$)", row[5])
            )
            row_count += 1

    search_database.close()
    build_message(comment, list_occurrence, row_count, total, term, sensitive)



def build_message(comment, occurrence, row_count, total, term, sensitive):
    """
    Sends message to user with the requested information
    """

    message = ""
    comment_to_user = (
        "######&#009;\n\n####&#009;\n\n#####&#009;\n\n"
        "**SEARCH TERM ({caps}): {term}** \n\n "
        "Total Occurrence: {occur} \n\n"
        ">{message}"
        "\n[Visualization of the search term]"
        "(http://creative-co.de/labs/songicefire/?terms={term})"
        "\n_____\n "
        "^(I'm ASOIAFSearchBot, I will display the occurrence of your "
        "search term throughout the books. Only currently working in Spoiler All topics.) "
        "[^(More Info Here)]"
        "(http://www.reddit.com/r/asoiaf/comments/25amke/"
        "spoilers_all_introducing_asoiafsearchbot_command/)"
    )

    # Avoid spam, limit amount of rows
    if row_count < 31 and total > 0:
        message += (
            "| Series| Book| Chapter| Chapter Name| Chapter POV| Occurrence\n"
        )
        message += "|:{dash}|:{dash}|:{dash}|:{dash}|:{dash}|:{dash}|\n".format(
            dash='-' * 11
        )
        # Each element is changed to one string
        for row in occurrence:
            message += row + "\n"
    elif row_count > 31:
        message = "**Excess number of chapters.**\n\n"
    elif total == 0:
        message = "**Sorry no results.**\n\n"

    case_sensitive = "CASE-SENSITIVE" if sensitive else "CASE-INSENSITIVE"

    comment_to_user = comment_to_user.format(
        caps=case_sensitive,
        term=term,
        occur=total,
        message=message
    )

    if sensitive:
        term_history_sensitive[term] = comment_to_user
    else:
        term_history[term.lower()] = comment_to_user

    reply(comment, comment_to_user)




def reply(comment, full_reply):
    """Replies to a comment with the text provided"""
    try:
        comment.reply(full_reply)
        print full_reply
    except (HTTPError, ConnectionError, Timeout, timeout) as err:
        print err
    except RateLimitExceeded as err:
        print err
        time.sleep(10)
    except APIException as err:  # Catch any less specific API errors
        print err
    else:
        commented.append(comment.id)
        

# =============================================================================
# MAIN
# =============================================================================


def main():
    """Main runner"""
    while True:
        try:
            print "start"
            # Grab all new comments from /r/asoiaf
            comments = praw.helpers.comment_stream(
                reddit, 'asoiaf', limit=None, verbosity=0
            )
            comment_count = 0
            # Loop through each comment
            for comment in comments:
                comment_count += 1
                
                if "SearchAll!" in comment.body:
                    parse_comment(comment, ALL)
                elif "SearchAGOT!" in comment.body:
                    parse_comment(comment, AGOT)
                elif "SearchACOK!" in comment.body:
                    parse_comment(comment, ACOK)
                elif "SearchASOS!" in comment.body:
                    parse_comment(comment, ASOS)
                elif "SearchAFFC!" in comment.body:
                    parse_comment(comment, AFFC)
                elif "SearchADWD!" in comment.body:
                    parse_comment(comment, ADWD)

                if comment_count == 1000:
                    break
            print "sleeping"
            time.sleep(25)
        except Exception as err:
            print err

# =============================================================================
# RUNNER
# =============================================================================

if __name__ == '__main__':
    main()