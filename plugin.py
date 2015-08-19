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

import traceback
import threading
import time
import re

from telegram import TelegramBot, TelegramError

class TelegramBridge(callbacks.Plugin):
    """Add the help for "@plugin help TelegramBridge" here
    This should describe *how* to use this plugin."""

    _pipe = None

    def __init__(self, irc):
        super(TelegramBridge, self).__init__(irc)
        self.log.debug("initualizing")
        self._tgPipe = None
        self._tgPipeLock = threading.Lock()
        self._tgChatId = self.registryValue("tgChatId")
        self._tgToken = self.registryValue("tgToken")
        try:
            self._tgId = int(self._tgToken.split(":", 1)[0])
        except ValueError:
            self.log.error("failed to parse tgToken, please check it is in "
                           "the <ID>:<COOKIE> format")
        self._tgTimeout = self.registryValue("tgTimeout")
        self._tgTargetChannel = None
        self._tgIrc = None
        self._tg = TelegramBot(self._tgToken)

    def _feedToSupybot(self, author, text):
        newMsg = ircmsgs.privmsg(self._tgTargetChannel,
                                 text.encode("utf8", "replace"))
        newMsg.prefix = self._tgIrc.prefix.encode("utf8", "replace")
        newMsg.tag("from_telegram")
        newMsg.nick = author.encode("ascii", "replace")
        self.log.debug("feeding back to supybot: %s", newMsg)
        self._tgIrc.feedMsg(newMsg)

    def _validTgChat(self, message):
        chat = message.get("chat")
        if chat and chat.get("id") == self._tgChatId:
            return True
        return False

    def _tgUserRepr(self, user):
        id = user.get("id", "??")
        last_name = user.get("last_name", "")
        name = user.get("first_name", str(id)) + last_name
        chosen = user.get("username", name)
        return id, chosen

    def _tgHandleText(self, message):
        text = message.get("text", "")
        if not text:
            for type in ("photo", "video", "audio", "sticker", "contact",
                         "location"):
                if message.get(type):
                    text = "<%s>" % (type)
        user = message.get("from")
        id, author = self._tgUserRepr(user)
        if id != self._tgId:
            for line in text.splitlines():
                repr = "%s> %s" % (author, line)
                self._sendIrcMessage(repr)
                self._feedToSupybot(author, line)

    def _telegramDiscardPreviousUpdates(self):
        update_id = None
        for update_id, update in self._tg.updates():
            pass
        all(self._tg.updates(state=update_id))

    def _telegramLoop(self):
        self._telegramDiscardPreviousUpdates()
        while True:
            try:
                for message in self._tg.updatesLoop(self._tgTimeout):
                    if self._validTgChat(message):
                        self._tgHandleText(message)
            except Exception, e:
                self.log.critical("%s", traceback.format_exc())
                self.log.critical("%s", str(e))
            time.sleep(1)

    def _startTelegramLoop(self):
        t = threading.Thread(target=self._telegramLoop)
        t.setDaemon(True)
        t.start()

    def _sendTelegram(self, line):
        data = line.encode("utf8", "replace")
        self.log.debug("to tg: %r" % (data))
        self._tgPipe.stdin.write(data + "\r\n")

    def _sendToChat(self, text):
        text = text.decode("utf8", "replace")
        text = text.encode("utf8")
        self._tg.sendMessage(self._tgChatId, text)

    def _sendIrcMessage(self, text):
        data = text.encode("utf8", "replace")
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
            self._startTelegramLoop()

    def doPrivmsg(self, irc, msg):
        irc = callbacks.SimpleProxy(irc, msg)
        channel = msg.args[0]
        if (not msg.isError and channel in irc.state.channels
                and not msg.from_telegram):
            text = msg.args[1]
            if ircmsgs.isAction(msg):
                text = ircmsgs.unAction(msg).decode("utf8", "replace")
                line = "* %s %s" % (msg.nick, text)
            else:
                line = "%s> %s" % (msg.nick, text.decode("utf8", "replace"))
            line = line.encode("utf8", "replace")
            self._sendToChat(line)

    def doTopic(self, irc, msg):
        if len(msg.args) == 1:
            return
        channel = msg.args[0]
        topic = msg.args[1]
        line = u"%s: %s" % (channel, topic.decode("utf8", "replace"))
        self._sendToChat(line.encode("utf8"))

    def outFilter(self, irc, msg):
        if msg.command == "PRIVMSG" and not msg.from_telegram:
            self.doPrivmsg(irc, msg)
        return msg

Class = TelegramBridge


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
