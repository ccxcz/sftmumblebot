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
    'ircservername',
    'ircport',
    'ircnick',
    'ircchannel',
    'ircpassword',
    'ircauthtype',
    'ircencoding',
    'ircloglevel',
))
MumbleConfig = namedtuple("MumbleConfig", (
    'servername',
    'port',
    'nick',
    'channel',
    'password',
    'loglevel',
))

irc = None
mumble = None
console = None


def mumbleTextMessageCallback(sender, message):
    line = "mumble: " + sender + ": " + message
    console.sendTextMessage(line)
    irc.sendTextMessage(line)
    if(message == 'gtfo'):
        mumble.sendTextMessage("KAY CU")
        mumble.stop()


def ircTextMessageCallback(sender, message):
    line = "irc: " + sender + ": " + message
    console.sendTextMessage(line)
    mumble.sendTextMessage(line)
    if (message == 'gtfo'):
        irc.sendTextMessage("KAY CU")
        irc.stop()


def consoleTextMessageCallback(sender, message):
    line = "console: " + message
    irc.sendTextMessage(line)
    mumble.sendTextMessage(line)


def mumbleConnected():
    irc.setAway()


def mumbleDisconnected():
    line = "connection to mumble lost. reconnect in 5 seconds."
    console.sendTextMessage(line)
    irc.setAway(line)
    time.sleep(5)
    mumble.start()


def mumbleConnectionFailed():
    line = "connection to mumble failed. retrying in 15 seconds."
    console.sendTextMessage(line)
    irc.setAway(line)
    time.sleep(15)
    mumble.start()


def ircConnected():
    mumble.setComment()


def ircDisconnected():
    line = "connection to irc lost. reconnect in 15 seconds."
    console.sendTextMessage(line)
    mumble.setComment(line)
    time.sleep(15)
    irc.start()


def ircConnectionFailed():
    line = "connection to irc failed. retrying in 15 seconds."
    console.sendTextMessage(line)
    mumble.setComment(line)
    time.sleep(15)
    irc.start()


def main():
    print("sft mumble bot " + sftbot.VERSION)

    global mumble
    global irc
    global console

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

    # create server connections
    # hostname, port, nickname, channel, password, name, loglevel
    mumble = MumbleConnection.MumbleConnection(
        mblcfg.servername,
        mblcfg.port,
        mblcfg.nick,
        mblcfg.channel,
        mblcfg.password,
        "mumble",
        mblcfg.loglevel,
    )

    irc = IRCConnection.IRCConnection(
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

    console = ConsoleConnection.ConsoleConnection(
        "utf-8",
        "console",
        loglevel)

    # register text callback functions
    mumble.registerTextCallback(mumbleTextMessageCallback)
    irc.registerTextCallback(ircTextMessageCallback)
    console.registerTextCallback(consoleTextMessageCallback)

    # register connection-established callback functions
    mumble.registerConnectionEstablishedCallback(mumbleConnected)
    irc.registerConnectionEstablishedCallback(ircConnected)

    # register connection-lost callback functions
    irc.registerConnectionLostCallback(ircDisconnected)
    mumble.registerConnectionLostCallback(mumbleDisconnected)

    # register connection-failed callback functions
    irc.registerConnectionFailedCallback(ircConnectionFailed)
    mumble.registerConnectionFailedCallback(mumbleConnectionFailed)

    # start the connections.
    # they will be self-sustaining due to the callback functions.
    mumble.start()
    irc.start()

    # start the console connection, outside a thread (as main loop)
    console.run()


if __name__ == "__main__":
    main()
