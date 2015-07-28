import sys
import base64
import time
from datetime import datetime
import re

from storm.locals import Int, DateTime, Unicode, Reference, Desc

from bicho.config import Config
from bicho.backends import Backend
from bicho.db.database import DBIssue, DBBackend, DBTracker, get_database
from bicho.common import Tracker, Issue, People, Change, Attachment, Comment
from bicho.utils import create_dir, printdbg, printout, printerr


import urllib2
import json
import HTMLParser
from BeautifulSoup import BeautifulSoup



class DBTracIssueExt(object):
    """
    """
    __storm_table__ = 'issues_ext_trac'

    id = Int(primary=True)
    cc = Unicode()
    keywords = Unicode()
    keywords = Unicode()
    version = Unicode()
    component = Unicode()
    milestone = Unicode()
    priority = Unicode()
    status = Unicode()
    modified_at = DateTime()
    closed_at = DateTime()

    # updated_at = datetime()

    # Same as id, what is the purpose of this field
    issue_id = Int()

    issue = Reference(issue_id, DBIssue.id)

    def __init__(self, issue_id):
        self.issue_id = issue_id


class DBTracIssueExtMySQL(DBTracIssueExt):
    """
    """

    __sql_table__ = 'CREATE TABLE IF NOT EXISTS issues_ext_trac ( \
                     id INTEGER NOT NULL AUTO_INCREMENT, \
                     issue_id INTEGER NOT NULL, \
                     status VARCHAR(64) NOT NULL, \
                     modified_at DATETIME, \
                     closed_at DATETIME, \
                     keywords VARCHAR(256) NOT NULL, \
                     version VARCHAR(32) NOT NULL, \
                     component VARCHAR(32) NOT NULL, \
                     milestone VARCHAR(32) NOT NULL, \
                     priority VARCHAR(32) NOT NULL, \
                     cc VARCHAR(100) NOT NULL, \
                     PRIMARY KEY(id), \
                     UNIQUE KEY(issue_id), \
                     INDEX ext_issue_idx(issue_id), \
                     FOREIGN KEY(issue_id) \
                       REFERENCES issues(id) \
                         ON DELETE CASCADE \
                         ON UPDATE CASCADE \
                     ) ENGINE=MYISAM;'


class DBTracBackend(DBBackend):
    """
    Adapter for Trac Backend
    """

    def __init__(self):
        self.MYSQL_EXT = [DBTracIssueExtMySQL]

    def insert_issue_ext(self, store, issue, issue_id):
        """
        """
        newissue = False
        printdbg("This is not a new issue")
        try:

            db_issue_ext = store.find(DBTracIssueExt, DBTracIssueExt.issue_id == issue_id).one()

            if not db_issue_ext:
                newissue = True
                printdbg("This is a new issue")
                db_issue_ext = DBTracIssueExt(issue_id)

            db_issue_ext.cc = self.__return_unicode(issue.cc)
            db_issue_ext.component = self.__return_unicode(issue.component)
            db_issue_ext.keywords = self.__return_unicode(issue.keywords)
            db_issue_ext.milestone = self.__return_unicode(issue.milestone)
            db_issue_ext.priority = self.__return_unicode(issue.priority)
            db_issue_ext.status = self.__return_unicode(issue.status)
            db_issue_ext.version = self.__return_unicode(issue.version)
            db_issue_ext.modified_at = issue.modified_at
            db_issue_ext.closed_at = issue.closed_at

            if newissue is True:
                store.add(db_issue_ext)

            store.flush()
            return db_issue_ext

        except:
            store.rollback()
            raise

    def insert_comment_ext(self, store, comment, comment_id):
        """
        """

    def insert_attachment_ext(self, store, comment, comment_id):
        """
        """

    def insert_change_ext(self, store, change, change_id):
        """
        """

    def get_last_modification(self, store, tracker_id):
        """
        """

    def __return_unicode(self,str):
        """
        Decodes string and pays attention to empty ones
        """
        if str:
            return unicode(str)
        else:
            return unicode('')


class TracIssue(Issue):
    """
    Ad-hoc Issue extension for Trac's issue
    """

    def __init__(self, issue, type, summary, description, submitted_by, submitted_on):
        Issue.__init__(self, issue, type, summary, description, submitted_by, submitted_on)

        self.component = None
        self.version = None
        self.keywords = None
        self.milestone = None
        self.cc = None
        self.assigned_to = None
        self.resolution = None
        self.priority = None
        self.status = None
        self.modified_at = None
        self.closed_at = None

    def setComponent(self,component):
        self.component = component

    def setVersion(self,version):
        self.version = version

    def setKeywords(self,keywords):
        self.keywords = keywords

    def setMilestone(self,milestone):
        self.milestone = milestone

    def setCc(self,cc):
        self.cc = cc

    def setResolution(self,resolution):
        self.resolution = resolution

    def setPriority(self,priority):
        self.priority = priority

    def setStatus(self,status):
        self.status = status

    def setModified_at(self,modified_at):
        self.modified_at = modified_at

    def set_closed_at(self, closed_at):
        self.closed_at = closed_at


class TracBackend(Backend):

    def __init__(self):
    #    self.url = Config.url
    #    self.delay = Config.delay
        # self.url = 'http://trac.plumi.org/'
        # self.url = 'http://10.137.2.15:8000/test/'
        self.delay = 3.0

    def choose_what_to_analyze(self, arg1, arg2):
        """Dispatch method"""
        method_name = 'analyze_' + str(arg1)
        method = getattr(self, method_name)
        return method(arg2)

    def analyze_milestone(self, arg2):

        """
        :type arg2: basestring
        """

        printdbg("We're analyzing milestones")

        # Get the time-date of the event
        tempdate = re.search("See timeline at\s(.*)\">", str(arg2))
        td = datetime.strptime(tempdate.group(1), "%b %d, %Y %I:%M:%S %p")

        # Get the author of the event
        bytemp = re.search("Changed\s.*\sby\s(.*)", str(arg2)).group(1).decode('UTF-8')
        by = People(bytemp)
        # print "analyzing {}".format(arg2)

        mr = re.search('\s+<em>(.*)</em>\s(?=deleted)', str(arg2))
        mc = re.search('(?<=\schanged\sfrom\s)<em>(.*)</em>\sto\s<em>(.*)</em>\s', str(arg2))
        ms = re.search('(?<=\sset\sto\s)<em>(.*)</em>', str(arg2))

        # If a milestone is deleted, added = ''
        # If a milestone is added, removed = ''
        if mr is not None:
            removed = mr.group(1).decode('UTF-8')
            added = u''
        elif mc is not None:
            removed = mc.group(1).decode('UTF-8')
            added = mc.group(2).decode('UTF-8')
        elif ms is not None:
            removed = u''
            added = ms.group(1).decode('UTF-8')
        else:
            printdbg("Milestone unknown case. Error ?")

        ch = Change(u'milestone', removed, added, by, td)
        return ch

    def analyze_keywords(self, arg2):

        """
        :type arg2: basestring
        """

        printdbg("We're analyzing keywords")
        # Get the time-date of the event
        tempdate = re.search("See timeline at\s(.*)\">", str(arg2))
        td = datetime.strptime(tempdate.group(1), "%b %d, %Y %I:%M:%S %p")

        # Get the author of the event
        bytemp = re.search("Changed\s.*\sby\s(.*)", str(arg2)).group(1).decode('UTF-8')
        by = People(bytemp)

        # We check which form of keywords modification we have
        # possible cases are
        # 1) tag1 tag2 tag3 added
        # 2) tag1 tag2 tag3 removed
        # 3) tag4 tag5 tag6 added; tag1 tag2 tag3 removed

        kw_a = re.search('(<em>.*)\sadded', str(arg2))
        kw_r = re.search('(<em>.*)\sremoved', str(arg2))
        kw_ar = re.search('(<em>.*)\sadded;(.*)\sremoved', str(arg2))

        if kw_ar is not None:
            # Case 3
            removed = kw_ar.group(2).replace('<em>', '').replace('</em>', '').decode('UTF-8')
            added = kw_ar.group(1).replace('<em>', '').replace('</em>', '').decode('UTF-8')

        elif kw_r is not None:
            removed = kw_r.group(1).replace('<em>', '').replace('</em>', '').decode('UTF-8')
            added = u''

        elif kw_a is not None:
            removed = u''
            added = kw_a.group(1).replace('<em>', '').replace('</em>', '').decode('UTF-8')

        else:
            printdbg("Milestone unknown case. Error ?")

        ch = Change(u'keywords', removed, added, by, td)
        return ch

    def analyze_status(self, arg2):

        """
        :type arg2: basestring
        """

        printdbg("We're analyzing statuses")
        # Get the time-date of the event
        tempdate = re.search("See timeline at\s(.*)\">", arg2)
        td = datetime.strptime(tempdate.group(1), "%b %d, %Y %I:%M:%S %p")

        # Get the author of the event
        bytemp = re.search("Changed\s.*\sby\s(.*)", arg2).group(1).decode('UTF-8')
        by = People(bytemp)

        # The pattern that we look for is:
        # changed from <em><status1></em> to <em><status2></em>
        st = re.search('changed\sfrom\s<em>(.*)</em>\sto\s<em>(.*)</em>', arg2)

        if st is not None:
            removed = st.group(1).decode('UTF-8')
            added = st.group(2).decode('UTF-8')
            printdbg("removed: {}, added: {}".format(removed, added))

        else:
            printdbg("Status unknown case. Error ?")

        ch = Change(u'status', removed, added, by, td)
        return ch

    def analyze_owner(self, arg2):

        printdbg("We're analyzing owners")
        # Get the time-date of the event
        tempdate = re.search("See timeline at\s(.*)\">", arg2)
        td = datetime.strptime(tempdate.group(1), "%b %d, %Y %I:%M:%S %p")

        # Get the author of the event
        bytemp = re.search("Changed\s.*\sby\s(.*)", arg2).group(1).decode('UTF-8')
        by = People(bytemp)

        # The pattern that we look for is:
        # changed from <em><status1></em> to <em><status2></em>
        st = re.search('changed\sfrom\s<em>(.*)</em>\sto\s<em>(.*)</em>', arg2)

        if st is not None:
            removed = st.group(1).decode('UTF-8')
            added = st.group(2).decode('UTF-8')
            printdbg("removed: {}, added: {}".format(removed, added))
        else:
            printdbg("Status unknown case. Error ?")

        ch = Change(u'owner', removed, added, by, td)
        return ch

    def analyze_version(self, arg2):
        printdbg("We're analyzing version")

        # Get the time-date of the event
        tempdate = re.search("See timeline at\s(.*)\">", arg2)
        td = datetime.strptime(tempdate.group(1), "%b %d, %Y %I:%M:%S %p")

        # Get the author of the event
        bytemp = re.search("Changed\s.*\sby\s(.*)", arg2).group(1).decode('UTF-8')
        by = People(bytemp)
        # print "analyzing {}".format(arg2)

        vr = re.search('\s+<em>(.*)</em>\s(?=deleted)', arg2)
        vc = re.search('(?<=\schanged\sfrom\s)<em>(.*)</em>\sto\s<em>(.*)</em>\s', arg2)
        vs = re.search('(?<=\sset\sto\s)<em>(.*)</em>', arg2)

        # If a milestone is deleted, added = ''
        # If a milestone is added, removed = ''
        if vr is not None:
            removed = vr.group(1).decode('UTF-8')
            added = u''
        elif vc is not None:
            removed = vc.group(1).decode('UTF-8')
            added = vc.group(2).decode('UTF-8')
        elif vs is not None:
            removed = u''
            added = vs.group(1).decode('UTF-8')
        else:
            printdbg("Version unknown case. Error ?")

        ch = Change(u'version', removed, added, by, td)

        return ch

    def analyze_resolution(self, arg2):
        printdbg("We're analyzing resolution")

        # Get the time-date of the event
        tempdate = re.search("See timeline at\s(.*)\">", str(arg2))
        td = datetime.strptime(tempdate.group(1), "%b %d, %Y %I:%M:%S %p")

        # Get the author of the event
        bytemp = re.search("Changed\s.*\sby\s(.*)", str(arg2)).group(1).decode('UTF-8')
        by = People(bytemp)

        rr = re.search('\s+<em>(.*)</em>\s(?=deleted)', str(arg2))
        rs = re.search('(?<=\sset\sto\s)<em>(.*)</em>', str(arg2))

        # If a resolution is deleted, added = ''
        # If a resolution is added, removed = ''
        if rr is not None:
            removed = rr.group(1).decode('UTF-8')
            added = u''
        elif rs is not None:
            removed = u''
            added = rs.group(1).decode('UTF-8')
        else:
            printdbg("Resolution unknown case. Error ?")

        ch = Change(u'resolution', removed, added, by, td)
        return ch

    def analyze_component(self, arg2):
        printdbg("We're analyzing component")

        # Get the time-date of the event
        tempdate = re.search("See timeline at\s(.*)\">", str(arg2))
        td = datetime.strptime(tempdate.group(1), "%b %d, %Y %I:%M:%S %p")

        # Get the author of the event
        bytemp = re.search("Changed\s.*\sby\s(.*)", str(arg2)).group(1).decode('UTF-8')
        by = People(bytemp)

        cc = re.search('(?<=\schanged\sfrom\s)<em>(.*)</em>\sto\s<em>(.*)</em>\s', str(arg2))

        if cc is not None:
            removed = cc.group(1).decode('UTF-8')
            added = cc.group(2).decode('UTF-8')
        else:
            printdbg("component unknown case. Error ?")

        printdbg("Remove: {}, add: {}".format(removed, added))
        ch = Change(u'component', removed, added, by, td)
        return ch

    def analyze_priority(self, arg2):
        printdbg("We're analyzing priority")

        # Get the time-date of the event
        tempdate = re.search("See timeline at\s(.*)\">", str(arg2))
        td = datetime.strptime(tempdate.group(1), "%b %d, %Y %I:%M:%S %p")

        # Get the author of the event
        bytemp = re.search("Changed\s.*\sby\s(.*)", str(arg2)).group(1).decode('UTF-8')
        by = People(bytemp)

        cc = re.search('(?<=\schanged\sfrom\s)<em>(.*)</em>\sto\s<em>(.*)</em>\s', str(arg2))

        if cc is not None:
            removed = cc.group(1).decode('UTF-8')
            added = cc.group(2).decode('UTF-8')
        else:
            printdbg("priority unknown case. Error ?")

        ch = Change(u'priority', removed, added, by, td)
        return ch

    def analyze_cc(self, arg2):

        printdbg("We're analyzing cc")
        # Get the time-date of the event
        tempdate = re.search("See timeline at\s(.*)\">", str(arg2))
        td = datetime.strptime(tempdate.group(1), "%b %d, %Y %I:%M:%S %p")

        # Get the author of the event
        bytemp = re.search("Changed\s.*\sby\s(.*)", str(arg2)).group(1).decode('UTF-8')
        by = People(bytemp)

        # We check which form of keywords modification we have
        # possible cases are
        # 1) tag1 tag2 tag3 added
        # 2) tag1 tag2 tag3 removed
        # 3) tag4 tag5 tag6 added; tag1 tag2 tag3 removed

        cc_a = re.search('(<em>.*)\sadded', str(arg2))
        cc_r = re.search('(<em>.*)\sremoved', str(arg2))

        if cc_r is not None:
            removed = cc_r.group(1).replace('<em>', '').replace('</em>', '').decode('UTF-8')
            added = u''

        elif cc_a is not None:
            removed = u''
            added = cc_a.group(1).replace('<em>', '').replace('</em>', '').decode('UTF-8')

        else:
            printdbg("CC unknown case. Error ?")

        ch = Change(u'cc', removed, added, by, td)

        return ch

    def analyze_type(self, arg2):
        printdbg("We're analyzing type")

        # Get the time-date of the event
        tempdate = re.search("See timeline at\s(.*)\">", str(arg2))
        td = datetime.strptime(tempdate.group(1), "%b %d, %Y %I:%M:%S %p")

        # Get the author of the event
        bytemp = re.search("Changed\s.*\sby\s(.*)", str(arg2)).group(1).decode('UTF-8')
        by = People(bytemp)

        tc = re.search('(?<=\schanged\sfrom\s)<em>(.*)</em>\sto\s<em>(.*)</em>\s', str(arg2))

        if tc is not None:
            removed = tc.group(1).decode('UTF-8')
            added = tc.group(2).decode('UTF-8')
        else:
            printdbg("type unknown case. Error ?")

        ch = Change(u'type', removed, added, by, td)
        return ch

    def analyze_summary(self, arg2):
        printdbg("We're analyzing summary")

        # Get the time-date of the event
        tempdate = re.search("See timeline at\s(.*)\">", str(arg2))
        td = datetime.strptime(tempdate.group(1), "%b %d, %Y %I:%M:%S %p")

        # Get the author of the event
        bytemp = re.search("Changed\s.*\sby\s(.*)", arg2).group(1).decode('UTF-8')
        by = People(bytemp)

        sc = re.search('(?<=\schanged\sfrom\s)<em>(.*)</em>\sto\s<em>(.*)</em>\s', str(arg2))

        if sc is not None:
            removed = sc.group(1).decode('UTF-8')
            added = sc.group(2).decode('UTF-8')
        else:
            printdbg("summary unknown case. Error ?")

        printdbg("removed: {}, add: {}".format(removed, added))
        ch = Change(u'summary', removed, added, by, td)
        return ch

    def analyze_attachment(self, arg2):
        printdbg("We're analyzing attachment")

        # Get the time-date of the event
        tempdate = re.search("See timeline at\s(.*)\">", str(arg2))
        td = datetime.strptime(tempdate.group(1), "%b %d, %Y %I:%M:%S %p")

        # Get the author of the event
        bytemp = re.search("Changed\s.*\sby\s(.*)", arg2).group(1).decode('UTF-8')
        by = People(bytemp)

        # The comment of the file inbetween <p> tags
        ac = re.search('(?<=\s<div class="comment searchable">)\s+<p>\s+(\w.*)\s</p>\s+</div>', str(arg2))

        # Attachment's name and url (anu)
        anu = re.search('<a href=".*<em>(.*)</em></a><a.*href="(.*)"\stitle=.*</a>', str(arg2))

        if ac is not None:
            comment = ac.group(1).decode('UTF-8')
        else:
            comment = u''
            printdbg("Comment not found, error?")

        if anu is not None:
            name = anu.group(1).decode('UTF-8')
            url = anu.group(2).decode('UTF-8')
        else:
            printdbg("Name or url not found, error?")
            name = u''
            url = u''

        printdbg("comment : {}, name : {}, url : {}".format(comment, name, url))

        # TODO: Check whether variables are assigned
        attach = Attachment(url, by, td)
        attach.set_name(name)
        attach.set_description(comment)

        return attach

    def analyze_comment(self, arg2):
        printdbg("We're analyzing comment")

        # Get the time-date of the event
        tempdate = re.search("See timeline at\s(.*)\">", str(arg2))
        td = datetime.strptime(tempdate.group(1), "%b %d, %Y %I:%M:%S %p")

        # Get the author of the event
        bytemp = re.search("Changed\s.*\sby\s(.*)", arg2).group(1).decode('UTF-8')
        by = People(bytemp)

        # The comment of the file inbetween <div class="comment searchable" tags
        cf = re.search('<div class="comment searchable">(.*)</div>\s+</div>', arg2, re.S)

        if cf is not None:
            #print cf.group(1)
            comm=cf.group(1).decode('UTF-8')
        else:
            printdbg("Comment not found, error?")

        # TODO: Check whether variables are assigned
        comment = Comment(comm, by, td)

        return comment

    def getIDs(self,url):
        # TODO: parse the url to check that it is a correct one

        report6 = url + "report/6"
        issue_index=[]

        result = urllib2.urlopen(report6).read()
        bs = BeautifulSoup(result)

        numresults = bs.find('span',{'class': 'numrows'}).getText().strip('()')[:-8]
        # numresults=int(numresults)
        numpages = int(numresults) / 100 + 1

        for page in range(numpages):
            url_aux = url + "report/6?asc=1&max=100&USER+anonymous&page=" + str(page)
            get_indexes = urllib2.urlopen(url_aux).read()

            bs = BeautifulSoup(get_indexes)
            for tmp in bs.findAll('td', {'class': 'ticket'}):
                issue_index.append(tmp.getText().strip('# '))

        if not issue_index:
            raise ValueError('Bug list is empty. Did you provide a correct url?')

        return issue_index

    def getIssue(self, url, id):
        issue = url + "ticket/" + id
        result = urllib2.urlopen(issue).read()
        return result

    def analyzeBug(self, raw_data):

        myTmpDates = []

        bs = BeautifulSoup(raw_data)

        props = bs.find('table', {'class': 'properties'})
        myStatus = bs.find('span', {'class': 'trac-status'}).getText().strip()
        myId = bs.find('a', {'class': 'trac-id'}).getText().strip()
        myType = bs.find('span', {'class': 'trac-type'}).getText().strip()
        mySummary = bs.find('span', {'class': 'summary'}).getText().strip()

        # TODO: Ameliorer cette condition. <div> searchable se trouve dans un <div> description
        myTmpDesc = bs.find('div', {'class': 'searchable'})
        if myTmpDesc is not None:
            myDescription = myTmpDesc.getText().strip()
        else:
            myDescription = 'None'

        myTmpDatetime = bs.findAll('a', {'class': 'timeline'})#.get('title')[16:]
        # myTmpDatetime = bs.find('div', {'class': 'date'}).getTitle().strip()
        for each in myTmpDatetime:
            myTmpDates.append(each.get('title')[16:])

        # TODO: Treat the case of a closed bug (3 dates)
        dates = bs.find('div', {'class': 'date'})
        if dates is not None:
            opened_t = re.search('<p>Opened.*title="See timeline at\s(.*)">.*</p>', str(dates))
            closed_t = re.search('<p>Closed.*title="See timeline at\s(.*)">.*</p>', str(dates))
            modified_t = re.search('<p>Last modified.*title="See timeline at\s(.*)">.*</p>', str(dates))

        if opened_t is not None:
            opened_at = datetime.strptime(opened_t.group(1), "%b %d, %Y %I:%M:%S %p")
        else:
            # This shoud never happen
            # TODO: raise error if we enter this case
            opened_at = None

        if closed_t is not None:
            closed_at = datetime.strptime(closed_t.group(1), "%b %d, %Y %I:%M:%S %p")
        else:
            # Ticket is not yet closed
            closed_at = None

        if modified_t is not None:
            modified_at = datetime.strptime(modified_t.group(1), "%b %d, %Y %I:%M:%S %p")
        else:
            # Ticket is not yet modified
            modified_at = None

        properties = [s.getText().strip() for s in props.findAll('td')]

        # Paul: est-ce que c'est une bonne methode de passer par une variable intermediaire ?
        mySubmitter = People(properties[0])
        # printdbg(mySubmitter.user_id)
        myAssignedTo = People(properties[1])
        myPriority = properties[2]
        myMilestone = properties[3]
        myComponent = properties[4]
        myVersion = properties[5]
        myKeywords = properties[6]
        myCC = properties[7]

        issue = TracIssue(myId, myType, mySummary, myDescription, mySubmitter, opened_at)

        issue.setCc(myCC)
        issue.setKeywords(myKeywords)
        issue.setVersion(myVersion)
        issue.setComponent(myComponent)
        issue.setMilestone(myMilestone)
        issue.setPriority(myPriority)
        issue.setStatus(myStatus)
        issue.setModified_at(modified_at)
        issue.set_closed_at(closed_at)

        # We are using the built-in set_assigned() method
        issue.set_assigned(myAssignedTo)

        # Analyze changes
        for change in bs.findAll('div', {'class': 'change'}):

            change = str(change)
            c_type = re.search('ul class="changes"', change)

        # If we have this field (ul class="changes", then we are analyzing
        # an argument change or attachment, else it is a comment

            if c_type is not None:

                # Changes might be 2 types: new attachment or argument change
                m_type = re.search('li class="trac-field-attachment"', change)

                if m_type is not None:

                    # This is a file attachment
                    h3 = re.search('<h3 class="change">.*</h3>', change, re.S)
                    cf = re.search('(<li class="trac-field-)(\w+)(">\s+<strong.*</strong>\s.*\s+?\w?.*?\s+</li>)(?:(\s+</ul>\s+<div.*\s+<p>\s+.*\s+</p>\s+</div>)?)', change)
                    if h3 is not None and cf is not None:
                        att = self.choose_what_to_analyze(str(cf.group(2)), str(h3.group(0))+str(cf.group(0)))
                        issue.add_attachment(att)

                    else:
                        printdbg ("h3 : {}, cf : {} change :{}".format(h3,cf,change))
                        exit(0)

                else:

                    # Some arguments are added/modified. We need to determine which ones and take old/new values
                    h3 = re.search('<h3 class="change">.*</h3>', change, re.S)
                    cf = re.findall('(<li\sclass="trac-field-)(\w+)(">\s+<strong.*</strong>\s.*)(\s</li>)', change)

                    for arg in cf:
                        # For each argument change we call a function that analyzes it and returns an instance
                        # of an object of an appropriate type.
                        chg = self.choose_what_to_analyze(arg[1], str(h3.group(0))+''.join(arg))
                        issue.add_change(chg)

            else:
                printdbg("This is a comment")
                # h3 = re.search('<h3 class="change">.*</h3>', change, re.S)
                cmt = self.choose_what_to_analyze('comment', change)
                issue.add_comment(cmt)

                # issue add changes, comments and attachments depending on val.__class__

        return issue

    def insertIssue(anal_data):
        """
        """
        # Put issue data to the database

    def run(self):

        cfg = Config()
        cfg.load_from_file("/home/user/Grimoire/Bicho/bicho/bicho.conf")

        # url = "http://10.137.2.15:8000/test/"
        url = 'http://software.rtcm-ntrip.org/'
        #project = "http://trac.nginx.org/nginx/"
        # issues = TracIssue
        tibi = TracBackend()
        issues = tibi.getIDs(url)
        bugsdb = get_database(DBTracBackend())
        bugsdb.insert_supported_traker("trac", "1.0.6post2")

        trk = Tracker(url, "trac", "1.0.6post2")
        dbtrk = bugsdb.insert_tracker(trk)

        print type(issues)
        for entry in issues:

            if start_from is not None:
                if issues.index(entry)

            printdbg("We are trying issue: {}".format(entry))
            try:
                printdbg("Getting the entry")
                raw_data = tibi.getIssue(url, entry)
                printdbg("Parsing the entry")
                issue = tibi.analyzeBug(raw_data)
                printdbg("Inserting the issue into the DB")
                # Put an issue into the database.
                bugsdb.insert_issue(issue, dbtrk.id)

            except UnicodeEncodeError:
                printerr(
                    "UnicodeEncodeError: the issue %s couldn't be stored"
                    % (issue_data.issue))

            except Exception, e:
                printerr("Error :")
                # print e
                import traceback
                traceback.print_exc()
                sys.exit(0)

            time.sleep(self.delay)





#Backend.register_backend("trac", TracBackend)

if __name__ == '__main__':
    be = Backend
    tb = TracBackend()
    tb.run()