__author__ = 'bdavenport'

import sys
import em7

from twisted.internet import protocol, reactor, task
from twisted.python import log
from twisted.words.protocols import irc

class FrameBot(irc.IRCClient):
    # Try to keep track of the channels were in
    channels = []
    nickname = "frameBot"
    realname = "FrameBot 0.0.1"
    versionName = "FrameBot"
    versionNum = "0.0.1"
    sourceURL = "http://wiki.hostedsolutions.com/EM7:em7bot"
    heartbeatInterval = 30
    #password = "em7bot/WHS:em7bot"

    # Get our nickname
    def _get_nickname(self):
        #TODO: Move this to a more clean location
        #HACK: This hijacks this to set the function further down the stack
        self.em7api.irc_msg = self.msg
        self.em7api.irc_join = self.join
        self.em7api.irc_part = self.part
        self.em7api.irc_topic = self.topic
        return self.factory.nickname
    nickname = property(_get_nickname)

    # Get our trigger character (also username: <cmd> works too)
    def _get_cmdTrigger(self):
        return self.factory.cmdTrigger
    cmdTrigger = property(_get_cmdTrigger)

    # Get our em7api class from higher up
    def _get_em7api(self):
        return self.factory.em7api
    em7api = property(_get_em7api)

    def signedOn(self):
        self.join(self.factory.channel)
        print "Signed on as %s." % (self.nickname,)

    def joined(self, channel):
        self.channels.append(channel)
        self.em7api.irc_channels = self.channels

    def privmsg(self, user, channel, msg):
        if channel == self.nickname:
            direct = True
        else:
            direct = False

        if len(msg.split(self.cmdTrigger)) > 1:
            isCmd = True
            trigger = "!"
        elif msg.startswith(self.nickname + ":"):
            isCmd = True
            trigger = self.nickname + ": "
        else:
            isCmd = False
            trigger = None

        self.em7api.ircCommand(user, channel, msg, direct, isCmd, theTrigger=trigger)


class FrameBotFactory(protocol.ClientFactory):
    protocol = FrameBot

    def __init__(self, channel, nickname='frameBot', cmdTrigger="!", api=None):
        self.channel = channel
        self.nickname = nickname
        self.realname = "FrameBot 0.0.1"
        self.cmdTrigger = cmdTrigger
        self.em7api = api

    def clientConnectionLost(self, connector, reason):
        print "Lost connection (%s), reconnecting." % (reason,)
        connector.connect()

    def clientConnectionFailed(self, connector, reason):
        print "Could not connect: %s" % (reason,)
        connector.connect()



if __name__ == "__main__":
    log.startLogging(sys.stdout)
    print "Initalizing EM7 API"
    em7api = em7.em7()
    print "Initalized"

    print "Prepping deferred tasks"
    task_1 = task.LoopingCall(em7api.task30)
    task_1.start(interval=int(30), now=False)

    task_2 = task.LoopingCall(em7api.task3600)
    task_2.start(interval=int(3600), now=False)

    task_3 = task.LoopingCall(em7api.task1)
    task_3.start(interval=int(1), now=False)
    print "Prepped"

    print "Starting Bot"
    #reactor.connectTCP('192.168.1.220', 1025, FrameBotFactory('#em7bot', api=em7api))
    reactor.connectTCP('irc.hostedsolutions.com', 6667, FrameBotFactory('#em7bot', api=em7api))
    reactor.run()
