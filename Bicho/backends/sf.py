# Copyright (C) 2007  GSyC/LibreSoft
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# Authors: Daniel Izquierdo Cortazar <dizquierdo@gsyc.escet.urjc.es>
#

from Bicho.backends import Backend, register_backend
from Bicho.utils import *
from HTMLUtils import *
from HTMLParser import HTMLParser
from ParserSFBugs import *
import re
import time
import Bicho.Bug as Bug
from Bicho.SqlBug import *
import os
import time
import datetime



class SFBackend (Backend):

    def __init__ (self):
        Backend.__init__ (self)
        options = OptionsStore()
        self.url = options.url


   
    def get_links (self, url):
        p = ParserSFLinksBugs ()
        p.add_filter (['a'])

        try:
            p.feed (urllib.urlopen (url).read ())
            p.close ()
        except:
            pass # TODO

        return p.get_tags ()

   
   
    def getLinksBugs (self, url):
        links = []
        bugs = []
        next_bugs = ""
        
        links = self.get_links(url)
      
        for link in links:
            url_str = str(link.get('href'))
            # Bugs URLs
            if re.search("tracker", url_str) and re.search("aid", url_str):
                bugs.append(url_join("http://sourceforge.net" + url_str))
                
            # Next page with bugs
            if re.search("offset", url_str):
                next_bugs = url_join("http://sourceforge.net/", url_str)
        
       
        return bugs, next_bugs

    def storeData(self, data, idBug):
        opt = OptionsStore()
        if not os.path.exists(opt.path):
             os.makedirs(opt.path)
        if not os.path.exists(os.path.join(opt.path, opt.db_database_out)):
             os.makedirs(os.path.join(opt.path, opt.db_database_out))

        #creating file to store data
        file = open(os.path.join(os.path.join(opt.path, opt.db_database_out), str(idBug)), 'w')
        file.write(data)
        file.close

    
    def analyzeBug(self, bugUrl):

        parser = ParserSFBugs(bugUrl)
        print "Analysing: " + bugUrl

        dataWeb = urllib.urlopen(bugUrl).read()
        parser.feed(dataWeb)
        parser.close()
        
        dataBug = parser.getDataBug()

        #storing data
        self.storeData(dataWeb, dataBug.Id)

        return dataBug
    
    
    def insert_general_info(self, url):
        firstTime = True
        project = ""
        tracker = ""
        cont = 0

        links = self.get_links (url)

        for link in links:
            url_str = str(link.get('href'))
            if re.search("softwaremap", url_str): 
                cont = cont + 1

            elif cont == 2:
                project = link.get_data()
                cont = cont + 1
            elif cont == 3:
                cont = cont + 1
            elif cont == 4:
                tracker = link.get_data()
                break
                            
        db = getDatabase()
        dbGeneralInfo = DBGeneralInfo(project, url, tracker, datetime.date.today())
        db.insert_general_info(dbGeneralInfo)

    
    def run (self):
        
        debug ("Running Bicho")
        
        #There are several pages of bugs for each project and 50 bugs per page
        #25th August 2007

        #Creating database
        #SqlBug file
        db = getDatabase()
        url = self.url        
        urls = []

        self.insert_general_info(url)

        while url != "" and not url in urls:
            urls.append(url)
            print "Obtaining bug links, from url: " + str(url)
            bugs, url = self.getLinksBugs(url)
            
            for bug in bugs:
                
                time.sleep(5)
                dataBug = self.analyzeBug(bug)

                dbBug = DBBug(dataBug)
                db.insert_bug(dbBug)

                print "Adding comments"
                for comment in dataBug.Comments:
                    dbComment = DBComment(comment)
                    db.insert_comment(dbComment)

                print "Adding attachments"
                for attach in dataBug.Attachments:
                    dbAttachment = DBAttachment(attach)
                    db.insert_attachment(dbAttachment)

                print "Adding changes"
                for change in dataBug.Changes:
                    dbChange = DBChange(change)
                    db.insert_change(dbChange)


register_backend ("sf", SFBackend)
    