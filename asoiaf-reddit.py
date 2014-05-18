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
from enum import Enum

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

class Title(Enum):
    All = 0
    AGOT = 1
    ACOK = 2
    ASOS = 3
    AFFC = 4
    ADWD = 5


class Books(object):
    """
    Book class, holds methods to find the correct occurrence
    of the given search term in each chapter.
    """
    # commented already messaged are appended to avoid messaging again
    commented = []
    
    # already searched terms
    # TODO: Make this functionality
    termHistory = {}
    termHistorySensitive = {}
        
    def __init__(self, comment):
        self.comment = comment
        self.bookCommand = None
        self.title = None
        self._searchTerm = ""
        self._bookQuery = ""
        self._sensitive = False
        self._listOccurrence = []
        self._rowOccurrence = 0
        self._total = 0
        self._rowCount = 0
        self._commentUser = ""
        self._message = ""

    def parse_comment(self):
        """
        Changes user comment from:
            Lorem ipsum dolor sit amet, consectetur adipiscing elit.
            ullam laoreet volutpat accumsan.
            SearchAll! "SEARCH TERM"
        into finally just:
            Search Term
        """

        # Removes everything before Search.!
        self._searchTerm = ''.join(re.split(
                                r'Search(All|AGOT|ACOK|ASOS|AFFC|ADWD)!', 
                                self.comment.body)[2:]
                            )

        # INSENSITIVE
        search_brackets = re.search('"(.*?)"', self._searchTerm)
        if search_brackets:
            self._searchTerm = search_brackets.group(0)
            self._sensitive = False
            self._searchTerm = self._searchTerm.lower()
        

        # SENSITIVE
        search_tri = re.search('\((.*?)\)', self._searchTerm)
        if search_tri:
            self._searchTerm = search_tri.group(0)
            self._sensitive = True
        
        # quotations at start and end
        self._searchTerm = self._searchTerm[1:-1]
        self._searchTerm = self._searchTerm.strip()
        
    def which_book(self):
        """
        self.title holds the farthest book in the series the 
        SQL statement should go. So if the title is ASOS it will only 
        do every occurence up to ASOS ONLY for SearchAll!
        """

        # Starts from AGOT ends at what self.title is
        # Not needed for All(0) because the SQL does it by default         
        if self.title != 0:
            # First time requires AND, next are ORs
            self._bookQuery += ('AND ({col2} = "{book}" '
                ).format(col2 = column2,
                        book = 'AGOT')
            # start the loop after AGOT
            for x in range(2, self.title+1):
                # assign current loop the name of the enum's value
                curBook = Title(x).name
                # Shouldn't add ORs if it's AGOT
                if Title(x) != 1: 
                    self._bookQuery += ('OR {col2} = "{book}" '
                        ).format(col2 = column2,
                                book = curBook)                    
            self._bookQuery += ")" # close the AND in the MSQL
    def build_query_sensitive(self):
        """
        Uses the correct mySql statement based off user's stated 
        case-sensitive
        """

        if self._sensitive:
            mySqlSearch = (
                'SELECT * FROM {table} WHERE {col1} REGEXP BINARY '
                '"([[:blank:][:punct:]]|^){term}([[:punct:][:blank:]]|$)" '
                '{bookQuery}ORDER BY FIELD'
                '({col2}, "AGOT", "ACOK", "ASOS", "AFFC", "ADWD"), 2'
            )
        else:
            mySqlSearch = (
                'SELECT * FROM {table} WHERE lower({col1}) REGEXP '
                '"([[:blank:][:punct:]]|^){term}([[:punct:][:blank:]]|$)" '
                '{bookQuery}ORDER BY FIELD'
                '({col2}, "AGOT", "ACOK", "ASOS", "AFFC", "ADWD"), 2'
            )
        
        self.search_db(mySqlSearch)
        
    def search_db(self, mySqlSearch):
        """
        Search through the database for which chapter holds the search
        term. Then count each use in said chapter.
        """

        searchDb = Connect()
        
        print mySqlSearch.format(
                table = table,
                col1 = column1,
                term = self._searchTerm,
                col2 = column2,
                bookQuery = self._bookQuery
            )
        
        # Find which chapter the word may appear
        searchDb.execute(mySqlSearch.format(
                table = table,
                col1 = column1,
                term = self._searchTerm,
                col2 = column2,
                bookQuery = self._bookQuery
            )
        )
        
        self._rowOccurrence = searchDb.fetchall()
        storyLen = 0
        # Once the chapter is found where the word appears
        # loop will count occurence for each row
        # builds each row for the table
        for row in self._rowOccurrence:
            
            # Stores each found word as a list of strings
            # len used to count number of elements in the list
            storyLen = len(re.findall("(\W|^)" + self._searchTerm +
                                "(\W|$)", row[5].lower()))
                                
            # Formats each row of the table nicely
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
            self._rowCount += 1
        
        searchDb.close()
        

    def build_message(self):
        """
        Build message that will be sent to the reddit user
        """
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
        # Don't show visual when no results
        visual = ""
        if self._total > 0:
            visual = (
                "\n[Visualization of the search term]"
                "(http://creative-co.de/labs/songicefire/?terms={term})"
                ).format(term = self._searchTerm)
                
        # Avoids spam and builds table heading only when condition is met
        if self._rowCount <= MAX_ROWS and self._total > 0:
            self._message += (
                "| Series| Book| Chapter| Chapter Name| Chapter POV| Occurrence\n"
            )
            self._message += "|:{dash}|:{dash}|:{dash}|:{dash}|:{dash}|:{dash}|\n".format(dash='-' * 11)
            # Each element added as a new row with new line
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
        
        # used for caching
        if self._sensitive:
            self.termHistorySensitive[self._searchTerm] = self._message
        else:
            self.termHistory[self._searchTerm] = self._message
            
            
    def reply(self, spoiler=False):
        """
        Reply to reddit user. If the search would be a spoiler
        Send different message.
        """
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

    def watch_for_spoilers(self):
        """
        Decides what the scope of spoilers based of the title.
        This means that searchADWD! Shouldn't be used in (Spoiler AGOT).
        """
        
        # loop formats each name into the regex
        # then checks regex against the title
        # number used for which_book() loop
        for name, number in Title.__members__.items():
            # Remove first letter incase of cases like GOT
            regex = ("(\(|\[).*({name}|{nameRemove}).*(\)|\])"
                ).format(name = name.lower(), nameRemove = name[1:].lower())
            if re.search(regex, self.comment.link_title.lower()):
                self.title = number.value
    
        # Decides which book the user picked based on the command.
        # SearchAGOT! to SearchADWD!
        for name, number in Title.__members__.items():
            search = ("Search{name}!").format(name = name)
            if search in self.comment.body:
                self.bookCommand = name     



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
            if re.search('Search(All|AGOT|ACOK|ASOS|AFFC|ADWD)!', comment.body):
                allBooks.watch_for_spoilers()
                # Note: None needs to be explict as this evalutes to
                # with Spoilers All as it's 0
                if allBooks.title != None:
                    allBooks.which_book()
                    allBooks.parse_comment()
                    allBooks.build_query_sensitive()
                    allBooks.build_message()
                    allBooks.reply()
                else:
                    # Sends apporiate message if it's a spoiler
                    allBooks.reply(spoiler=True)

        #except Exception as err:
            #print err
# =============================================================================
# RUNNER
# =============================================================================

if __name__ == '__main__':
    main()
