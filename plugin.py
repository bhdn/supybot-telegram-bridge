###
# Copyright (c) 2015, Bogdano Arendartchuk
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

###

import supybot.utils as utils
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks
import supybot.ircmsgs as ircmsgs

import subprocess
import threading
import time
import select
import re

class TelegramBridge(callbacks.Plugin):
    """Add the help for "@plugin help TelegramBridge" here
    This should describe *how* to use this plugin."""

    _pipe = None

    def __init__(self, irc):
        super(TelegramBridge, self).__init__(irc)
        self.log.debug("initualizing")
        self._tgPipe = None
        self._tgPipeLock = threading.Lock()
        self._tgChat = self.registryValue("tgChat")
        self._tgNick = self.registryValue("tgNick")
        self._tgTargetChannel = None
        self._tgIrc = None
        self._startTelegramDaemon()

    def _feedToSupybot(self, author, text):
        newMsg = ircmsgs.privmsg(self._tgTargetChannel, text.encode("utf8"))
        newMsg.prefix = self._tgIrc.prefix.encode("utf8")
        newMsg.tag("from_telegram")
        newMsg.nick = author.encode("ascii", "replace")
        self.log.debug("feeding back to supybot: %s", newMsg)
        self._tgIrc.feedMsg(newMsg)

    def _processTelegramLine(self, line):
        if self._tgIrc is not None:
            expr = r"\[\d\d:\d\d\]  %s (?P<author>.*) >>> (?P<msg>.*)" % (self._tgChat)
            found = re.search(expr, line, re.U)
            if found:
                orig_author = found.group("author")
                if orig_author != self._tgNick:
                    author = orig_author.replace(" ", "")
                    msg = found.group("msg")
                    line = "[%s] %s" % (author, msg)
                    self._sendIrcMessage(line)
                    self._feedToSupybot(author, msg)

    def _telegramLoop(self):
        while True:
            r, w, x = select.select([self._tgPipe.stdout.fileno()], [], [])
            line = self._tgPipe.stdout.readline()
            line = line.decode("utf8", "replace")
            if not line:
                self.log.critical("tg apparently died")
                if self._tgIrc is not None:
                    self._tgIrc.error("tg apparently is dead")
                break
            else:
                self.log.debug("tg: %r" % (line))
                self._processTelegramLine(line)

    def _startTelegramDaemon(self):
        binary = self.registryValue("tgCommand")
        self.log.debug("starting %s" % (binary))
        try:
            self._tgPipe = subprocess.Popen(binary, shell=True,
                                          stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE,
                                          stdin=subprocess.PIPE)
        except EnvironmentError, e:
            self.log.warn("failed to run the telegram client: %s" % (e))
        else:
            time.sleep(1)
            if self._tgPipe.poll() is not None:
                self.log.warn("failed to run the telegram client: %s" %
                              self._tgPipe.stderr.read())
            else:
                thread = threading.Thread(target=self._telegramLoop)
                thread.start()

    def _sendTelegram(self, line):
        data = line.encode("utf8")
        self.log.debug("to tg: %r" % (data))
        self._tgPipe.stdin.write(data + "\r\n")

    def _sendToChat(self, text):
        chat = self._tgChat.replace("#", "@")
        command = "msg %s %s" % (chat, text)
        self._sendTelegram(command)

    def _sendIrcMessage(self, text):
        data = text.encode("utf8")
        newMsg = ircmsgs.privmsg(self._tgTargetChannel, data)
        newMsg.tag("from_telegram")
        self._tgIrc.queueMsg(newMsg)

    def doJoin(self, irc, msg):
        self.log.debug("joined %s" % (msg))
        if self._tgTargetChannel is None:
            self._tgIrc = irc
            self._tgTargetChannel = msg.args[0]
            self._tgMsg = msg
            self.log.info("gathered the channel information (%s, %s)" %
                          (irc, msg.args[0]))

    def doPrivmsg(self, irc, msg):
        irc = callbacks.SimpleProxy(irc, msg)
        channel = msg.args[0]
        if (not msg.isError and channel in irc.state.channels
                and not msg.from_telegram):
            text = msg.args[1]
            if ircmsgs.isAction(msg):
                text = ircmsgs.unAction(msg).decode("utf8")
                line = "* %s %s" % (msg.nick, text)
            else:
                line = "%s> %s" % (msg.nick, text.decode("utf8"))
            self._sendToChat(line)

    def doTopic(self, irc, msg):
        if len(msg.args) == 1:
            return
        channel = msg.args[0]
        topic = msg.args[1]
        line = u"%s: %s" % (channel, topic.decode("utf8"))
        self._sendToChat(line)

    def outFilter(self, irc, msg):
        if msg.command == "PRIVMSG" and not msg.from_telegram:
            self.doPrivmsg(irc, msg)
        return msg

Class = TelegramBridge


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
