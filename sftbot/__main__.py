#!/usr/bin/env python2
import sys
import os.path
import time
from collections import namedtuple

import MumbleConnection
import IRCConnection
import ConsoleConnection
import ConfigParser
import sftbot


IRCConfig = namedtuple("IRCConfig", (
    'servername',
    'port',
    'nick',
    'channel',
    'password',
    'authtype',
    'encoding',
    'loglevel',
))
MumbleConfig = namedtuple("MumbleConfig", (
    'servername',
    'port',
    'nick',
    'channel',
    'password',
    'loglevel',
))
ConsoleConfig = namedtuple("ConsoleConfig", (
    'loglevel',
))


class Main(object):
    def __init__(self, mblcfg, irccfg, concfg):
        """Bridge between irc, mumble and console."""
        self.mblcfg = mblcfg
        self.irccfg = irccfg
        self.concfg = concfg

        # create server connections
        # hostname, port, nickname, channel, password, name, loglevel
        self.mumble = MumbleConnection.MumbleConnection(
            mblcfg.servername,
            mblcfg.port,
            mblcfg.nick,
            mblcfg.channel,
            mblcfg.password,
            "mumble",
            mblcfg.loglevel,
        )

        self.irc = IRCConnection.IRCConnection(
            irccfg.servername,
            irccfg.port,
            irccfg.nick,
            irccfg.channel,
            irccfg.password,
            irccfg.authtype,
            irccfg.encoding,
            "irc",
            irccfg.loglevel,
        )

        self.console = ConsoleConnection.ConsoleConnection(
            "utf-8",
            "console",
            concfg.loglevel,
        )

        # register text callback functions
        self.mumble.registerTextCallback(self._mumbleTextMessageCallback)
        self.irc.registerTextCallback(self._ircTextMessageCallback)
        self.console.registerTextCallback(self._consoleTextMessageCallback)

        # register connection-established callback functions
        self.mumble.registerConnectionEstablishedCallback(
            self._mumbleConnected
        )
        self.irc.registerConnectionEstablishedCallback(self._ircConnected)

        # register connection-lost callback functions
        self.irc.registerConnectionLostCallback(self._ircDisconnected)
        self.mumble.registerConnectionLostCallback(self._mumbleDisconnected)

        # register connection-failed callback functions
        self.irc.registerConnectionFailedCallback(self._ircConnectionFailed)
        self.mumble.registerConnectionFailedCallback(
            self._mumbleConnectionFailed
        )

    def start(self):
        # start the connections.
        # they will be self-sustaining due to the callback functions.
        self.mumble.start()
        self.irc.start()

        # start the console connection, outside a thread (as main loop)
        self.console.run()

    def _mumbleTextMessageCallback(self, sender, message):
        if sender == self.mblcfg.nick:
            return
        line = "mumble: " + sender + ": " + message
        self.console.sendTextMessage(line)
        self.irc.sendTextMessage(line)
        if(message == 'gtfo'):
            self.mumble.sendTextMessage("KAY CU")
            self.mumble.stop()

    def _ircTextMessageCallback(self, sender, message):
        if sender == self.irccfg.nick:
            return
        line = "irc: " + sender + ": " + message
        self.console.sendTextMessage(line)
        self.mumble.sendTextMessage(line)
        if (message == 'gtfo'):
            self.irc.sendTextMessage("KAY CU")
            self.irc.stop()

    def _consoleTextMessageCallback(self, sender, message):
        line = "console: " + message
        self.irc.sendTextMessage(line)
        self.mumble.sendTextMessage(line)

    def _mumbleConnected(self):
        self.irc.setAway()

    def _mumbleDisconnected(self):
        line = "connection to mumble lost. reconnect in 5 seconds."
        self.console.sendTextMessage(line)
        self.irc.setAway(line)
        time.sleep(5)
        self.mumble.start()

    def _mumbleConnectionFailed(self):
        line = "connection to mumble failed. retrying in 15 seconds."
        self.console.sendTextMessage(line)
        self.irc.setAway(line)
        time.sleep(15)
        self.mumble.start()

    def _ircConnected(self):
        self.mumble.setComment()

    def _ircDisconnected(self):
        line = "connection to irc lost. reconnect in 15 seconds."
        self.console.sendTextMessage(line)
        self.mumble.setComment(line)
        time.sleep(15)
        self.irc.start()

    def _ircConnectionFailed(self):
        line = "connection to irc failed. retrying in 15 seconds."
        self.console.sendTextMessage(line)
        self.mumble.setComment(line)
        time.sleep(15)
        self.irc.start()


def main():
    print("sft mumble bot " + sftbot.VERSION)

    loglevel = 3

    if len(sys.argv) > 1:
        # load the user-specified conffile
        conffiles = [sys.argv[1]]
    else:
        # try finding a confile at one of the default paths
        conffiles = ["sftbot.conf", "/etc/sftbot.conf"]

    # try all of the possible conffile paths
    for conffile in conffiles:
        if os.path.isfile(conffile):
            break
    else:
        if len(conffiles) == 1:
            raise Exception("conffile not found (" + conffiles[0] + ")")
        else:
            raise Exception("conffile not found at any of these paths: " +
                            ", ".join(conffiles))

    # read the conffile from the identified path
    print("loading conf file " + conffile)
    cparser = ConfigParser.ConfigParser()
    cparser.read(conffile)

    # configuration for the mumble connection
    mblcfg = MumbleConfig(
        servername=cparser.get('mumble', 'server'),
        port=int(cparser.get('mumble', 'port')),
        nick=cparser.get('mumble', 'nickname'),
        channel=cparser.get('mumble', 'channel'),
        password=cparser.get('mumble', 'password'),
        loglevel=int(cparser.get('mumble', 'loglevel')),
    )

    # configuration for the IRC connection
    irccfg = IRCConfig(
        servername=cparser.get('irc', 'server'),
        port=int(cparser.get('irc', 'port')),
        nick=cparser.get('irc', 'nickname'),
        channel=cparser.get('irc', 'channel'),
        password=cparser.get('irc', 'password', ''),
        authtype=cparser.get('irc', 'authtype'),
        encoding=cparser.get('irc', 'encoding'),
        loglevel=int(cparser.get('irc', 'loglevel')),
    )

    concfg = ConsoleConfig(loglevel=loglevel)

    bridge = Main(
        mblcfg=mblcfg,
        irccfg=irccfg,
        concfg=concfg,
    )

    bridge.start()


if __name__ == "__main__":
    main()
