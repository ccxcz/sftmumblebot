#!/usr/bin/env python2
import sys
import os.path
import time
from collections import namedtuple
from functools import partial

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
    'tokens',
    'loglevel',
))
ConsoleConfig = namedtuple("ConsoleConfig", (
    'loglevel',
))


def fmt_message(origin, sender, message):
    return '<%s@%s> %s' % (sender, origin, message)


class Main(object):
    def __init__(self, mblcfg, irccfg, concfg):
        """Bridge between irc, mumble and console."""
        self.mblcfg = mblcfg
        self.irccfg = irccfg
        self.concfg = concfg

        # create server connections
        # hostname, port, nickname, channel, password, name, loglevel
        self.mumble = MumbleConnection.MumbleConnection(
            hostname=mblcfg.servername,
            port=mblcfg.port,
            nickname=mblcfg.nick,
            channel=mblcfg.channel,
            password=mblcfg.password,
            tokens=mblcfg.tokens,
            name="mumble",
            loglevel=mblcfg.loglevel,
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
        line = fmt_message("mumble", sender, message)
        self.console.sendTextMessage(line)
        self.irc.sendTextMessage(line)
        # if(message == 'gtfo'):
        #     self.mumble.sendTextMessage("KAY CU")
        #     self.mumble.stop()

    def _ircTextMessageCallback(self, sender, message):
        if sender == self.irccfg.nick:
            return
        line = fmt_message("irc", sender, message)
        self.console.sendTextMessage(line)
        self.mumble.sendTextMessage(line)
        # if (message == 'gtfo'):
        #     self.irc.sendTextMessage("KAY CU")
        #     self.irc.stop()

    def _consoleTextMessageCallback(self, sender, message):
        line = fmt_message("cmd", sender, message)
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

    def get(section, key, convert=None, **kwargs):
        if 'default' in kwargs:
            if not cparser.has_option(section, key):
                return kwargs['default']
            elif convert is None:
                convert = type(kwargs['default'])
        value = cparser.get(section, key)
        return value if convert is None else convert(value)

    # configuration for the mumble connection
    mblget = partial(get, 'mumble')
    mblcfg = MumbleConfig(
        servername=mblget('server'),
        port=mblget('port', default=64738),
        nick=mblget('nickname'),
        channel=mblget('channel'),
        password=mblget('password', default=''),
        tokens=mblget('tokens', default='').split(','),
        loglevel=mblget('loglevel', default=1),
    )

    # configuration for the IRC connection
    ircget = partial(get, 'irc')
    irccfg = IRCConfig(
        servername=ircget('server'),
        port=ircget('port', default=6667),
        nick=ircget('nickname'),
        channel=ircget('channel'),
        password=ircget('password', default=''),
        authtype=ircget('authtype', default='none'),
        encoding=ircget('encoding', default='utf-8'),
        loglevel=ircget('loglevel', default=1),
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
