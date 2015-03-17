__author__ = 'bdavenport'

import base64
import copy
import json
import time
import urllib3
import yaml

from random import randint

ircControlChar = ""
'''
Color format:
	colorcode = 6	#forground only
	colorcode = 6,8 #forground and background

Color codes:

 1- Black
 2- Navy Blue
 3- Green
 4- Red
 5- Brown
 6- Purple
 7- Olive
 8- Yellow
 9- Lime Green
10- Teal
11- Aqua Light
12- Roal Blue
13- Hot Pink
14- Dark Grey
15- Light Grey
16- White
'''

class em7:
    def __init__(self):
        self.randint = randint(0,999999)
        self.settings = {}
        self.tickets = {}
        self.irc_msg = None
        self.irc_join = None
        self.irc_part = None
        self.irc_topic = None
        self.sevhs = []

        # Load data from YAML for preservation
        print "Loading Settings"
        f = open('em7bot.settings.yml')
        dataMap = yaml.load(f)
        f.close
        self.settings = dataMap['settings']
        del dataMap
        print "Loaded"
        print "Loading Tickets"
        f = open('em7bot.tickets.yml')
        dataMap = yaml.load(f)
        f.close
        self.tickets = dataMap['tickets']
        del dataMap
        print "Loaded"

        self.api_url_base = self.settings['api_url_base']
        self.queryheaders = self.settings['queryheaders']
        self.channels = self.settings['channels']

        # This is so we can rate limit the output
        self.messages = []
        ''' self.messages = [
                [tstamp_added, privmsg, '#channel', 'message'], - message
                [tstamp_added, topic,   '#channel', 'message'], - topic
                [tstamp_added, notice,  '#channel', 'message'], - notice
        ]'''

    # Makes the call to the API server using url path we need to request
    def call_api(self, passed_url):
        httppool = urllib3.PoolManager(cert_reqs='CERT_NONE', assert_hostname=False)
        request = httppool.request('GET', url=passed_url, headers=self.queryheaders)
        x = request.data
        request.close()
        resultstring = json.loads(x.decode('utf-8'),strict=False)

        return resultstring

    # Requests the tickets, by default 3000 tickets that are in a Open/Pending/Working state
    def api_get_tickets(self, limit=3000, filters=["status.in=0,1,2"], silentRun=False):
        # Make our URL and add the filters
        built_url = self.api_url_base + "/ticket?limit=%s&extended_fetch=1" % limit
        for x in filters:
            built_url = built_url + "&filter.%s" % x

        result = self.call_api(built_url)['result_set']

        for k, c in result.items():
            self.check_ticket(int(k.split('/')[-1]), c, oneOff=silentRun)

    # Takes the output of the ticket and puts it into our arrays for tracking
    def check_ticket(self, tid, data, oneOff=False):
        #print tid
        #print data

        # A little logic, to help figure out if the ticket state
        if tid not in self.tickets:
            self.tickets[tid] = {
                'state': "new"
            }
        else:
            self.tickets[tid]['state'] = "existing"
            if time.gmtime(int(data['date_update'])) > self.tickets[tid]['em7_date_updated']:
                self.tickets[tid]['state'] = "updated"

        self.tickets[tid] = {
            'state': self.tickets[tid]['state'],
            'bot_date_update': time.gmtime(),
            'em7_ticket_queue': int(data['ticket_queue'].split('/')[-1]),
            'em7_date_created': time.gmtime(int(data['date_create'])),
            'em7_date_updated': time.gmtime(int(data['date_update'])),
            'em7_updated_by': int(data['updated_by'].split('/')[-1]),
            'em7_assigned_to': int(data['assigned_to'].split('/')[-1]),
            'em7_category': int(data['category'].split('/')[-1]),
            'em7_severity': int(data['severity']),
            'em7_status': int(data['status']),
            'em7_description': data['description'].replace('\n|\r', '').encode('utf-8'),
            'em7_aligned_resource': data['aligned_resource'].encode('utf-8'),
            'em7_aligned_resource_name': data['aligned_resource_name'].encode('utf-8')
        }

        if int(data['severity']) == 4 and tid not in self.sevhs and self.tickets[tid]['state'] == "new":
            self.sevhs.append(tid)

        # If the ticket is updated, and if this is not a oneOff check...
        if oneOff is False and self.tickets[tid]['state'] == "updated":
            # Now check the queues in the channel settings...
            for x in self.channels:
                if self.tickets[tid]['em7_ticket_queue'] in self.channels[x]['queues']:
                    if self.tickets[tid]['em7_updated_by'] not in self.channels[x]['ignore_updated_by']:
                        message = self.build_message(tid)
                        self.messages.append([time.gmtime(), 'privmsg', '%s' % x, message])
                    else:
                        pass
                else:
                    pass


    #TODO: Pull this information from EM7
    # This our cheat, does not apply to all em7 instances,
    def sevLookup(self, sevlvl):
        if sevlvl == 0:
            return ['Sev 4 / Informational',  'Sev 4',  '1,3']
        if sevlvl == 1:
            return ['Sev 3 / Change Request', 'Sev 3',  '1,2']
        if sevlvl == 2:
            return ['Sev 2 / Degraded',       'Sev 2',  '1,8']
        if sevlvl == 3:
            return ['Sev 1 / Critical',       'Sev 1',  '1,7']
        if sevlvl == 4:
            return ['Sev HS / Internal',      'Sev HS', '1,4']
        return ['Sev ? / BROKEN', 'Sev ?', '1,0']

    def ircCommand(self, user, channel, msg, direct=False, isCmd=False, theTrigger=None):
        if isCmd:
            print "[%s,%s]%s: %s" % (direct, isCmd, channel, msg)
            self.irc_msg("#em7bot", "EM7API - [%s,%s]%s: %s" % (direct, isCmd, channel, msg))

            cmdArgs = msg.split(theTrigger)[1].split(" ")
            print cmdArgs
            if cmdArgs[0] == "save":
                self.SaveToYAML()
            elif cmdArgs[0] == "join":
                self.irc_join(channel=cmdArgs[1])
            elif cmdArgs[0] in ['part', 'leave']:
                if len(cmdArgs) == 1:
                    self.irc_part(channel=channel)
                else:
                    self.irc_part(channel=cmdArgs[1])
            elif cmdArgs[0] == "add_channel":
                if len(cmdArgs) == 1:
                    tmp_x = channel
                else:
                    tmp_x = cmdArgs[1]

                self.channels[tmp_x[1:]] = copy.deepcopy(self.channels['default'])
                self.irc_join(tmp_x)
                self.SaveToYAML()

                del tmp_x
            elif cmdArgs[0] == "set_channel":
                if cmdArgs[1] == "queues":
                    cmdArgs.pop(1)
                    cmdArgs.pop(0)




            elif cmdArgs[0] == "tid":
                self.api_get_tickets(limit=1, filters=["status.in=0,1,2,3", "tid=%s" % int(cmdArgs[1])], silentRun=True)
                message = self.build_message(tid=int(cmdArgs[1]))
                self.irc_msg(channel, message)
            elif cmdArgs[0] in ["quite", "silence"]:
                if len(cmdArgs) == 1:
                    tmp_x = channel
                else:
                    tmp_x = cmdArgs[1]

                if tmp_x[1:] in self.channels:
                    print self.channels[channel[1:]]
                    if self.channels[channel[1:]]['quite']:
                        self.channels[channel[1:]]['quite'] = False
                    else:
                        self.channels[channel[1:]]['quite'] = True
                    print self.channels[channel[1:]]

                del tmp_x
            elif cmdArgs[0] == "chaninfo":
                if len(cmdArgs) == 1:
                    tmp_x = channel
                else:
                    tmp_x = cmdArgs[1]

                print tmp_x

                if tmp_x[1:] in self.channels:
                    '''
                    Channel Information for: #em7
                    Announceing Ticket QIDs: 234, Silent: True, Ignoring Updates by UIDs: 123,123,123,
                    '''
                    message = "Channel Information for: %s\n" % tmp_x
                    message = "%sTicket QIDs: %s, Ignore UIDs: %s, Silent: %s" % (message, self.channels[tmp_x[1:]]['queues'], self.channels[tmp_x[1:]]['ignore_updated_by'], self.channels[tmp_x[1:]]['quite'])
                    self.irc_msg(channel, message)
                    del message
                else:
                    self.irc_msg(channel, "Sorry that channel is not in my settings, use add_channel to add it.")

                del tmp_x

    # Build ticket irc msg notice
    def build_message(self, tid):
        message = ""

        # Unassigned: if ticket is unassigned
        #    Updated: if ticket is assigned
        #        New: iassigned

        if self.tickets[tid]['em7_assigned_to'] == 0:
            message = " Unassigned: "
        else:
            if self.tickets[tid]['state'] == "updated":
                message = "    Updated: "
            else:
                message = "     Ticket: "

        message = "%s %s | " % (message, tid)

        x = self.sevLookup(self.tickets[tid]['em7_severity'])
        y = "%s%s" % (x[2], x[1])

        message = "%s %s | " % (message, y)

        message = "%s %s\n" % (message, self.tickets[tid]['em7_description'])

        message = "%s        ||| https://dashboard.hostedsolutions.com/em7/index.em7?exec=ticket_editor&tid=%s" % (message, tid)

        return message

    def ircPushMsgs(self):
        if len(self.messages) > 0:
            # DEBUG
            self.irc_msg('#em7bot', 'Message Array Len: %s' % len(self.messages))
            for msg in self.messages:
                print msg
                if msg[1] == 'privmsg':
                    if msg[2] in self.channels:
                        if not self.channels[msg[2]]['quite']:
                            self.irc_msg("#%s" % msg[2], msg[3])
                else:
                    #TODO: Topic and Notice, not implamented yet
                    pass
            self.messages = []

    # This is called every 30 seconds from the bot framework level
    def task30(self):
        # This will fetch all open tickets
        self.api_get_tickets()
        print "Finished ticket poll"
        print self.messages
        self.ircPushMsgs()

    # This is called every hour from the bot framework level
    def task3600(self):
        # Save to the YMLs for faster crash recovery
        self.SaveToYAML()

    # This is called every second from the botframework level
    def task1(self):
        # There was a need for this, might be used later so leaving fragment behind
        pass

    # This is called to join the channels after the recactor starts
    def joinSetChannels(self):
        for chan in self.channels:
            if chan != "default":
                x = "#%s" % chan
                self.irc_join(x)
                del x

    def SaveToYAML(self):
        tmp = {}
        tmp['settings'] = self.settings
        tmp['settings']['channels'] = self.channels
        with open('em7bot.settings.yml', 'w') as outfile:
            outfile.write( yaml.dump(tmp) )

        '''
        tmp = {}
        tmp['tickets'] = self.tickets
        with open('em7bot.tickets.yml', 'w') as outfile:
            outfile.write( yaml.dump(tmp) )
        '''

        del tmp