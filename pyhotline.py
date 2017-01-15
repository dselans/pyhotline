#!/usr/bin/env python
#
# Copyright (c) 2013, Daniel Selans (daniel.selans@gmail.com)
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
#    * Neither the name of the owner nor the names of its contributors may be
#      used to endorse or promote products derived from this software without
#      specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL DANIEL SELANS BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
A python module for creating, managing and automating Asterisk hotlines.

Pyhotline is a python module that enables you to create automated receptionist
style hotlines, that in turn, can be used by clients/employees to dispatch a
trouble issue to scheduled on call contacts.

Project home: http://code.google.com/p/pyhotline/
"""

__version__ = '0.3.0'

import os, sys, time, random, string, smtplib, logging, datetime

from operator import itemgetter
from asterisk import manager
from asterisk import agi
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email.MIMEText import MIMEText
from email.Utils import COMMASPACE, formatdate
from email import Encoders

try:
    import sqlite3
except ImportError:
    from pysqlite2 import dbapi2 as sqlite3

try:
    import json
except ImportError:
    import simplejson as json

class _Base:
    """ 
    Initializes all required objects; contains all the asterisk/agi/manager
    wrapper functions.
    """

    def __init__(self, config_file, group, use_agi=False, use_mgr=False): 
        self.config_file = config_file
        self.group = group
        
        # Validate and parse the config
        config = _Config(self.config_file, self.group)
        (status, self.conf) = config.parse()
        
        if not status:
            print "[ConfigError] %s" % self.conf
            sys.exit(1)

        self.sql = _SQL(self.conf['sqlite_database'])
        self.log = self._setupLogging(self.conf['log_file'], self.conf['log_level'])
        
        if use_agi: self.agi = agi.AGI()
        if use_mgr: self.mgr = manager.Manager()

    def playMessage(self, id):
        return self.agi.stream_file(self.conf['message_dir'] + '/' + id, '#')

    def recordMessage(self, id):
        self.agi.record_file(self.conf['message_dir'] + '/' + id, 'gsm', '#', 30000)

    def say(self, msg):
        try:
            self.agi.appexec('Swift', msg)
        except Exception, e:
            self.log.critical("Unable to say(); Exception: %s" % (e))
            return False

        return True

    def managerLogin(self):
        try:
            self.mgr.connect(self.conf['manager_host'], self.conf['manager_port'])
            self.mgr.login(self.conf['manager_username'], self.conf['manager_password'])
            return True
        except Exception, e:
            self.log.critical("ERROR: Unable to start manager connection. Exception: %s)" % e)
            return False

    def call(self, number, channel_vars={}):
        """
        We utilize async=True, as we need to catch the OriginateResponse event,
        which contains the Uniqueid used for identifying the associated hangup
        event. Maybe there is a cleaner way to acquire Uniqueid? 
        """
        prepend = ''
        if self.conf['outbound_prepend']:
            prepend = str(self.conf['outbound_prepend'])

        out_channel = 'Local/' + prepend + number + '@' + self.conf['outbound_context']

        response = self.mgr.originate(channel   = out_channel,
                                      exten     = 's', 
                                      context   = self.group,
                                      priority  = '1', 
                                      timeout   = self.conf['origin_timeout'] * 1000, 
                                      caller_id = self.conf['caller_id'], 
                                      async     = True,
                                      variables = channel_vars)
        return response

    def _setupLogging(self, log_file, log_level):
        levels = {'info'     : logging.INFO,
                  'warning'  : logging.WARNING,
                  'error'    : logging.ERROR,
                  'critical' : logging.CRITICAL,
                  'debug'    : logging.DEBUG}

        logging.basicConfig(level    = levels[log_level],
                            format   = '[%(asctime)s] %(levelname)s %(message)s',
                            datefmt  = '%D %H:%M:%S',
                            filename = log_file,
                            filemode = 'a')

        logger = logging.getLogger('Base')
        return logger

class Inbound(_Base):
    """
    This class facilitates the handling of the inbound call.
    The script utilizing this class should be configured in Asterisk to be
    executed via AGI and tied to an extension (or DID number).
    
    Example Asterisk configuration:

    1234 => {
        Answer();
        AGI(myhotline-inbound.py);
    }

    Basic usage:

    inbound_obj = Inbound('/etc/pyhotline.conf', 'myhotline')
    inbound_obj.run()
    """
    def __init__(self, config_file, group):
        _Base.__init__(self, config_file, group, use_agi=True)

    def run(self):
        if self.sql.fetchClientCount() == 0:
            self.log.warning("SQLite 'clients' table is empty. Hotline will not be active until this is corrected")
            self.say("Welcome to the %s hotline. It appears this hotline is not fully configured. Please call back later." % self.conf['team_name'])
            self.agi.hangup()
            return 

        self.say("Welcome to the %s hotline. Please enter your customer pin number. |8000|4" % self.conf['team_name'])
        pin = self.agi.get_variable('SWIFT_DTMF')

        client = self.sql.fetchClientByPin(pin)
        if not client:
            self.say("Invalid pin number. Good bye! You entered: %s" % pin)
            self.agi.hangup()
            return

        msg_id = _Misc.genRandom()

        record_complete = False
        while record_complete == False:
            self.say("Please provide a brief description of the issue you are experiencing followed by the pound key.")
            self.recordMessage(msg_id)

            while True:
                self.say("If you are satisfied with your message please press 1. " + \
                         "If you would like to record a new message please press 2. " + \
                         "If you would like to play back the current message please press 3.|5000|1")

                record_pin = self.agi.get_variable('SWIFT_DTMF')

                if record_pin == '3':
                    self.playMessage(msg_id)
                    continue
                elif record_pin == '2':
                    # Back into main loop to rerecord the message
                    break
                elif record_pin == '1':
                    record_complete = True
                    break

        record_id = self.sql.insertMessage(client['client_id'], msg_id, self.agi.env['agi_callerid'])

        self.say("Thank you. Your message will be relayed to a member of the %s team immediatelly. " % self.conf['team_name'] + \
                 "In addition please send an email to %s detailing the problems you are experiencing. " % self.conf['email_phonetic'] + \
                 "Have a nice day!")

        self.agi.hangup()

        # We are all done here - let the queue runner handle the rest
        return

class Outbound(_Base):
    """
    This class facilitates the handling of the outbound call that is triggered
    via a queue script. The outbound script should be setup in Asterisk to be
    executed via AGI and placed in a context named after the hotline group name.

    Example Asterisk configuration:

    context myhotline {
        s => {
            Answer();
            AGI(myhotline-outbound.py);
        }
    }

    Note: The extension should be set to 's'
    
    Basic usage:

    from pyhotline import Outbound
    outbound_obj = Outbound('/etc/pyhotline.conf', 'myhotline')
    outbound_obj.run()
    """
    def __init__(self, config_file, group):
        _Base.__init__(self, config_file, group, use_agi=True)

    def run(self):
        self.say("Hello. This is the %s hotline calling. " 
                 "A new trouble issue has been created by %s" % (self.conf['team_name'], self.agi.get_variable('name')))
        
        while True:
            self.say("Please press 1 to listen to the message, press 2 to accept the issue or press 3 to reject the issue.|5000|1")
            data = self.agi.get_variable('SWIFT_DTMF')
            
            if not data:
                self.say("Timeout reached. The issue has been automatically rejected. Good bye.")
                self.agi.hangup()
                return

            if data == '1':
                self.playMessage(self.agi.get_variable('msg_id'))
                continue
            
            if data == '2':
                self.sql.updateStatus(int(self.agi.get_variable('id')), 1)
                self.say("Thank you. The issue has been marked as accepted.")
                break
                
            if data == '3':
                self.say("Thank you. The issue has been rejected. Good bye.")
                self.agi.hangup()
                return
       
        while True:
            self.say("Please press 1 to listen to the message again or hang up at any time.|5000|1")
            listen_again = self.agi.get_variable('SWIFT_DTMF')
            
            if listen_again == '1':
                self.playMessage(self.agi.get_variable('msg_id'))
                continue
            else:
                self.say("Timeout reached. Have a good day.")
                self.agi.hangup()
                return

class Queue(_Base):
    """
    This class facilitates calling scheduled/emergency contacts if a new trouble
    issue has been submitted. The script utilizing this class should be executed
    via cron.

    Basic usage:

    from pyhotline import Queue
    queue_obj = Queue('/etc/pyhotline.conf', 'myhotline')
    queue_obj.run()
    """
    def __init__(self, config_file, group):
        _Base.__init__(self, config_file, group, use_mgr=True)
        # Event vars
        self.action_id  = None
        self.unique_id  = None
        self.hangup_event = False
        self.orig_event   = False

    def _originateEvent(self, event, manager):
        if event.headers['ActionID'] == self.action_id:
            #print event.headers['Response']
            if event.headers['Response'] == 'Success':
                self.unique_id = event.headers['Uniqueid']
                self.log.debug("Event >> Originate event succeeded: %s" % event.headers['Uniqueid'])
            else:
                self.log.debug("Event >> Originate event failed")

            self.orig_event = True

    def _hangupEvent(self, event, manager):
        #print event.headers
        if event.headers['Uniqueid'] == self.unique_id:
            self.log.debug("Event >> Hangup event: %s" % self.unique_id)
            self.hangup_event = True

    def run(self):
        # Check for new 'unhandled' messages
        unhandled = self.sql.fetchUnhandled()
        total_messages = len(unhandled)
        handled_messages = 0

        if total_messages < 1:
            #self.log.debug("No new unhandled issues.")
            return

        self.log.info("Found %s unhandled issues." % total_messages)

        if not self.managerLogin():
            return

        self.mgr.register_event('Hangup', self._hangupEvent)
        self.mgr.register_event('OriginateResponse', self._originateEvent)


        # Get call lists
        scheduled_contacts = self._getScheduled()
        skip_list = [contact['name'] for contact in scheduled_contacts]
        emergency_contacts = self._getEmergency(skip_list)

        attempts = 0 

        while True:
            # If max_attempts = 0 -> infinite loop; otherwise iterate max_attempts
            if attempts == self.conf['max_attempts'] and self.conf['max_attempts'] != 0:
                break

            # Break out of loop if all messages accepted
            if handled_messages == total_messages:
                break
            
            attempts += 1
            self.log.info("Queue run attempt %s/%s..." % (attempts, self.conf['max_attempts']))

            for msg in unhandled:
                # Skip accepted issues
                if msg['employee'] is not None:
                    self.log.debug("Issue #%s already accepted by '%s'. Skipping..." % (msg['id'], msg['employee']))
                    continue

                (handled_type, contact) = self.handleIssue(msg, scheduled_contacts, emergency_contacts)

                if handled_type:
                    handled_messages += 1
                    msg['employee'] = contact['name']
                    msg['handled_type'] = handled_type 
                    self.sql.updateStatus(msg['id'], 2, contact['name'])

        # Update the leftover unhandled issues with failed status 
        unhandled_ids = [x['id'] for x in unhandled if 'handled' not in x]

        for id in unhandled_ids:
            self.log.debug("Setting issue #%s as unhandled" % (id))
            self.sql.updateStatus(id, 2)

        if self.conf['email_notify']:
            self.log.info("Sending email notification to '%s'..." % (self.conf['email_to']))
            if not self._notifyEmail(attempts, unhandled, scheduled_contacts, emergency_contacts):
                self.log.critical("Unable to send notification email through '%s:%s' - check your mail logs!" % (self.conf['smtp_host'], self.conf['smtp_port'])) 

        self.log.info("Queue run finished. Stats: %s/%s attempts total, %s/%s issues resolved" % (attempts, self.conf['max_attempts'], handled_messages, total_messages)) 

    def handleIssue(self, msg, scheduled, emergency):
        """
        Issue handling logic - attempt scheduled contacts first, followed by emergency.
        Returns tuple (string||None handled_type, string||None contact).
        """
        # Attempt scheduled contacts
        self.log.info("Attempting scheduled contacts for issue #%s..." % msg['id'])

        for contact in scheduled:
            self.log.info("Attempting to call scheduled contact '%s' for issue #%s" % (contact['name'], msg['id']))
            if self.attemptCall(contact['number'], msg):
                self.log.info("Primary contact (%s) succeeded for issue #%s." % (contact['name'], msg['id']))
                return ("scheduled", contact)
            else:
                self.log.warning("Primary contact (%s) failed for issue #%s." % (contact['name'], msg['id']))
        
        # Attempt emergency contacts
        self.log.warning("All scheduled contacts failed for issue #%s" % msg['id'])

        if len(emergency) == 0:
            self.log.warning("No emergency contacts available for issue #%s" % msg['id'])
            return (None, None)

        for contact in emergency:
            self.log.info("Attempting to call emergency contact '%s' for issue #%s" % (contact['name'], msg['id']))
            if self.attemptCall(contact['number'], msg):
                self.log.info("Emergency contact (%s) succeeded for issue #%s." % (contact['name'], msg['id']))
                return ("emergency", contact)
            else:
                self.log.warning("Emergency contact (%s) failed for issue #%s." % (contact['name'], msg['id']))

        return (None, None)

    def attemptCall(self, number, msg): 
        """
        Attempts to make a call to a specified number; if originate & hangup
        events are completed - checks the database to see whether call was 
        accepted/rejected or dismissed - returns True/False.
        """
        # Reset these, in case this is not our first attemptCall()
        self.unique_id  = None
        self.hangup_event = False
        self.orig_event   = False

        hangup_timeout = 180
        spent_time = 1

        response = self.call(number, channel_vars = msg)
        self.action_id = response.headers['ActionID']

        # Wait for originate event
        self.log.debug("Waiting for originate event for %s seconds" % self.conf['origin_timeout'])
        while int(spent_time) != self.conf['origin_timeout']:
            if self.orig_event:
                if self.unique_id:
                    # Call completed
                    self.log.debug("UniqueID '%s' acquired. Moving to next loop. Spent '%s' seconds in wait state" % (self.unique_id, int(spent_time)))
                    break
                else:
                    # Call failed
                    self.log.debug("Originate failed. Spent '%s' seconds in wait state" % (int(spent_time)))
                    return False
            time.sleep(.1)
            spent_time += .1

        if int(spent_time) == self.conf['origin_timeout']:
            # Exceeded timeout for originate
            self.log.debug("Exceeded timeout for originate... Spent '%s' seconds in wait state" % (int(spent_time)))
            return False

        spent_time = 1
        # Wait for hangup event
        self.log.debug("Waiting for hangup event for %s seconds" % hangup_timeout)
        while int(spent_time) != hangup_timeout:
            if self.hangup_event:
                self.log.debug("Hangup completed. Moving on! Spent '%s' seconds in wait state" % (int(spent_time)))
                break
            time.sleep(.1)
            spent_time += .1

        if int(spent_time) == hangup_timeout:
            # Exceeded wait for hangup
            self.log.debug("Exceeded timeout for hangup. Spent '%s' " % (int(spent_time)))
            return False

        # Hang up ocurred, let's check DB
        msg_status = self.sql.fetchStatus(msg['id'])
        if msg_status == 1:
            return True

        # Person was not reachable or did not accept issue
        return False

    def _notifyEmail(self, attempts, issues, scheduled, emergency):
        email_body = "Number of issues: %s\n" % len(issues)
        email_body += "Number of attempts: %s/%s\n" % (attempts, self.conf['max_attempts'])

        if len(scheduled) == 0:
            sched_str = "None"
        else:
            sched_str = ', '.join([contact['name'] for contact in scheduled])

        if len(emergency) == 0:
            emerg_str = "None"
        else:
            emerg_str = ', '.join([contact['name'] for contact in emergency])

        email_body += "Scheduled contacts: %s\n" % sched_str
        email_body += "Emergency contacts: %s\n" % emerg_str
        email_body += "\n"

        files = []

        for issue in issues:
            email_body += "Issue id: %s\n" % issue['id']
            email_body += "Client Name: %s\n" % issue['name'] 
            email_body += "Client CallerID: %s\n" % issue['caller_id']
            email_body += "Client Message ID: %s\n" % issue['msg_id']

            msg_filename = self.conf['message_dir'] + '/' + issue['msg_id'] + '.gsm'
            files.append(msg_filename)

            if issue['employee'] is not None: 
                email_body += "Status: Handled by %s\n\n" % issue['employee']
            else:
                email_body += "Status: Unhandled\n\n"
        
        email = { 
            'to' : self.conf['email_to'], 
            'from' : self.conf['email_from'], 
            'subject' : "[%s hotline] Issue summary" % self.group,
            'message' : email_body
        }

        return _Misc.sendEmail(email, files, host=self.conf['smtp_host'], port=self.conf['smtp_port'])

    def _getScheduled(self):
        weekday = (datetime.datetime.now()).weekday()
        call_list = []

        for employee in self.conf['contacts']:
            if weekday in employee['schedule']:
                call_list.append(employee)

        # Sort by priority level
        return sorted(call_list, key = itemgetter('priority'), reverse=True)

    def _getEmergency(self, skip_list=[]):
        call_list = []

        for employee in self.conf['contacts']:
            if employee['name'] in skip_list:
                continue

            if employee['emergency']:
                call_list.append(employee)

        # Again, sort by priority level
        return sorted(call_list, key = itemgetter('priority'), reverse=True)

class _Misc:
    """
    Miscelaneous class functions used by other classes in the module.
    """
    @classmethod
    def getTime(cls):
        return (datetime.datetime.now()).strftime('%Y-%m-%d %H:%M:%S')

    @classmethod
    def genRandom(cls, length=8):
        return ''.join([random.choice(string.hexdigits) for n in xrange(8)])

    @classmethod
    def sendEmail(cls, email, files=[], host='localhost', port=25):
        """ Expects an email dictionary """
        req_params = ['to', 'from', 'subject', 'message']
        if type(email) is not dict:
            return False

        for req in req_params:
            if req not in email:
                return False

        if type(files) is not list or len(files) == 0:
            return False

        for f in files:
            if not os.path.exists(f):
                return False

        # Borrowed from somewhere on stackoverflow
        msg = MIMEMultipart()
        msg['From'] = email['from']
        msg['To'] = email['to']
        msg['Date'] = formatdate(localtime=True)
        msg['Subject'] = email['subject']

        msg.attach( MIMEText(email['message']))

        for f in files:
            part = MIMEBase('application', "octet-stream")
            part.set_payload(open(f,"rb").read())
            Encoders.encode_base64(part)
            part.add_header('Content-Disposition', 'attachment; filename="%s"' % os.path.basename(f))
            msg.attach(part)

        try:
            s = smtplib.SMTP(host, port)
            s.sendmail(email['from'], [email['to']], msg.as_string())
            s.quit()
        except Exception, e:
            return False

        return True

class _SQL:
    """
    sqlite messages.status:
        0 - new/unhandled issue
        1 - success 
        2 - failure
    """
    def __init__(self, db_file):
        self.con = sqlite3.connect(db_file)
        self.con.row_factory = self._dictFactory
        self.cur = self.con.cursor()

    def updateStatus(self, id, status, name=None):
        self.cur.execute("UPDATE messages SET status=?, employee=? WHERE id=?", (status, name,id))
        id = self.cur.lastrowid
        self.con.commit()
        return id

    def fetchStatus(self, id):
        self.cur.execute("SELECT status FROM messages WHERE id=?", (id,))
        row = self.cur.fetchone()
        if row != None:
            return row['status']
        return row

    def insertMessage(self, id, msg_id, caller_id):
        cur_date = _Misc.getTime() 
        self.cur.execute("INSERT INTO messages (client_id, msg_id, caller_id, date) VALUES (?, ?, ?, ?)", (id, msg_id, caller_id, cur_date))
        id = self.cur.lastrowid
        self.con.commit() 
        return id

    def fetchClientByPin(self, pin):
        self.cur.execute("SELECT * FROM clients WHERE pin=?", (pin,))
        return self.cur.fetchone()

    def fetchClientCount(self):
        self.cur.execute("SELECT COUNT(*) FROM clients")
        # return first element from values
        return (self.cur.fetchone()).values()[0]

    def fetchUnhandled(self):
        self.cur.execute("SELECT messages.*, clients.name FROM messages, clients WHERE messages.status = 0 AND clients.client_id = messages.client_id")
        return self.cur.fetchall()

    def fetchTables(self):
        self.cur.execute("SELECT name FROM SQLite_Master")
        return self.cur.fetchall()

    # custom row factory for sqlite3; returns dicts instead of tuples
    def _dictFactory(self, cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    @classmethod
    def setupDatabase(cls, file):
        try:
            sql = _SQL(file)
            sql.cur.execute("""CREATE TABLE
                               clients(client_id INTEGER PRIMARY KEY AUTOINCREMENT,
                               name INT, 
                               pin INT)""")
            sql.cur.execute("""CREATE TABLE 
                               messages(id INTEGER PRIMARY KEY AUTOINCREMENT,
                               client_id INT,
                               msg_id TEXT,
                               caller_id INT,
                               date INT, 
                               status INT DEFAULT 0, 
                               employee TEXT)""")
            # Insert dummy account
            sql.cur.execute("INSERT INTO clients (name, pin) VALUES ('Test Client', '1111')")
            sql.con.commit()
            sql.cur.close()
        except Exception, e:
            return (False, e)

        return (True, '')

class _Config:
    """
    Config validation class
    """
    def __init__(self, config_file, group):
        self.config_file = config_file
        self.group = group
        self.json_data = None
        self.config = None
       
        # Required sections, options
        self.required_main = {'manager_host'     : None,
                              'manager_port'     : self._checkPort,
                              'manager_username' : None,
                              'manager_password' : None,
                              'origin_timeout'   : self._checkOriginTimeout,
                              'outbound_context' : None,
                              'outbound_prepend' : self._checkPrepend,
                              'smtp_host'        : None,
                              'smtp_port'        : self._checkPort}

        self.required_group = {'sqlite_database' : self._checkDatabase,
                               'message_dir'     : self._checkDir,
                               'log_file'        : self._checkFile,
                               'log_level'       : self._checkLogLevel,
                               'max_attempts'    : self._checkMaxAttempts,
                               'team_name'       : None,
                               'caller_id'       : None,
                               'email_phonetic'  : None,
                               'email_notify'    : self._checkBool,
                               'email_to'        : self._checkEmailValue, 
                               'email_from'      : self._checkEmailValue, 
                               'contacts'        : self._checkContacts}

        self.required_contacts = {'name'      : None,
                                  'number'    : None,
                                  'schedule'  : self._checkSchedule,
                                  'emergency' : self._checkBool,
                                  'priority'  : self._checkPriority}

        self.required_sections = {'main'   : self.required_main, 
                                  'groups' : self.required_group}

    def parse(self):
        (status, json_data) = self._loadConfig()
        if not status:
            return (False, json_data)

        self.json_data = json_data

        # Check if sections exist
        for section in self.required_sections:
            if section not in self.json_data:
                return (False, "Missing section %s" % section)

        # Check if the specific hotline group is defined
        if self.group not in self.json_data['groups']:
            return (False, "'%s' is not defined" % self.group)

        # Perform in-depth checks
        for section, settings in self.required_sections.iteritems():
            for req_opt, validateFunc in settings.iteritems():
                # Define where to look for the required options
                target = None
                if section == 'groups':
                    target = self.json_data['groups'][self.group]
                else:
                    target = self.json_data[section]

                # Check if the req option is defined
                if req_opt not in target:
                    return (False, "Missing required option '%s' in section '%s'" % (req_opt, section))

                # Check if the value is blank
                if target[req_opt] == '':
                    return (False, "Option '%s' in section '%s' cannot be blank" % (req_opt, section))

                # Skip if there is no associated validation function
                if validateFunc == None:
                    continue

                # Perform the validation function
                (status, message) = validateFunc(target[req_opt])
                if not status:
                    if section == 'groups':
                        return (False, "(groups->%s->%s) %s" % (self.group, req_opt, message))
                    return (False, "(%s->%s) %s" % (section, req_opt, message)) 

        # Return a 'clean' version of the config (include the specific group)
        self.config = dict(self.json_data['groups'][self.group].items() + self.json_data['main'].items())
        return (True, self.config)

    def _loadConfig(self):
        if not os.path.exists(self.config_file):
            return(False, "No such file '%s'" % self.config_file)

        try:
            conf_fh = open(self.config_file)
            json_data = json.load(conf_fh)
            conf_fh.close()
        except IOError, e:
            return (False, "Unable to open config file '%s'. Exception: %s" % (self.config_file, e))
        except Exception, e:
            return(False, "Unable to load config file '%s'. Exception: %s" % (self.config_file, e))

        return (True, json_data)

    def _checkPort(self, value):
        if type(value) != int:
            return (False, "Value is not of integer type")

        if value > 0 and value < 65535:
            return (True, '')
        return (False, "Invalid port value '%s'" % value)
       
    def _checkOriginTimeout(self, value):
        max = 600 # "10 minutes ought to be enough for anybody"
        if type(value) != int:
            return (False, "Value is not of integer type")

        if value > 1 and value < max: 
            return (True, '')
        return (False, "Invalid value '%s' (max: %s)" % (value, max))

    def _checkDir(self, value):
        if not os.path.isdir(value):
            return (False, "'%s' is not a valid directory" % value)
        return (True, '')

    def _checkMaxAttempts(self, value):
        try:
            int(value)
        except ValueError, e:
            return (False, "'%s' is not of int type" % value)

        if value < 0 or value > 10:
            return (False, "Invalid max_attempts '%s' value (allowed 0..10)" % (value))

        return (True, '')

    def _checkDatabase(self, value):
        if not os.path.exists(value):
            return (False, "SQLite db does not exist. Consult documentation for creating the initial db.")

        sql = _SQL(value)
        tables = sql.fetchTables()

        if len(tables) > 1:
            return (True, '')
        return (False, "SQLite db missing required tables. Consult documentation for creating the initial db.")

    def _checkFile(self, value):
        if os.path.exists(value):
            if not os.access(value, os.W_OK):
                return (False, "Unable to write to file '%s'" % value)
        else:
            try:
                open(value, 'a')
                os.remove(value)
            except IOError, e:
                return (False, "Unable to write to file '%s'" % value)

        return (True, '')

    def _checkLogLevel(self, value):
        log_levels = ['debug', 'info', 'critical', 'warning', 'error']
        if value not in log_levels:
            return (False, "Invalid log level '%s'" % value)
        return (True, '')

    def _checkBool(self, value):
        if type(value) == bool:
            return (True, '')
        return (False, "Value should be of bool type")

    def _checkSchedule(self, value):
        if type(value) != list:
            return (False, "Schedule is not of array type")

        allowed = range(0,7)
        for day in value:
            if day not in allowed:
                return (False, "Invalid schedule value '%s'" % day)
        return (True, '')

    def _checkPriority(self, value):
        if type(value) != int:
            return (False, "Value should be of integer type")
        return (True, '')

    def _checkPrepend(self, value):
        if value == False or type(value) == int:
            return (True, '')
        return (False, "Invalid value - has to be of int type or bool 'false'")

    def _checkEmailValue(self, value):
        if value == False:
            # Only allow value to be set to false if email_notify is disabled
            if self.json_data['groups'][self.group]['email_notify'] != False:
                return (False, "Value cannot be 'false' while email_notify is enabled")
        elif value == True:
            return (False, "Value can only be set to 'false' or string")

        return (True, '')

    def _checkContacts(self, value):
        # Same as before, check req_opts, then exec associated validation func
        for req_opt, validateFunc in self.required_contacts.iteritems():
            # Contacts are held in a list
            for contact in value:
                if req_opt not in contact:
                    return (False, "Missing required option %s" % (req_opt))

                if contact[req_opt] == '':
                    return (False, "Required option '%s' cannot be blank" % (req_opt))

                if validateFunc == None:
                    continue

                (status, msg) = validateFunc(contact[req_opt])
                if not status:
                    return (False, msg)

        return (True, '')
