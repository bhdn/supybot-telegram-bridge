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

from .telegram import TelegramBot, TelegramError
import supybot.utils as utils
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks
import supybot.ircmsgs as ircmsgs

import traceback
import threading
import time
import sys
import re

import importlib
from . import telegram
importlib.reload(telegram)


class TelegramBridge(callbacks.Plugin):
    """Add the help for "@plugin help TelegramBridge" here
    This should describe *how* to use this plugin."""

    _pipe = None

    def __init__(self, irc):
        super(TelegramBridge, self).__init__(irc)
        self.log.debug("initualizing")
        self._tgToken = self.registryValue("tgToken")
        try:
            self._tgId = int(self._tgToken.split(":", 1)[0])
        except ValueError:
            self.log.error("failed to parse tgToken, please check it is in "
                           "the <ID>:<COOKIE> format")
        self._tgTimeout = self.registryValue("tgTimeout")
        self._tgIrc = irc
        self._tg = TelegramBot(self._tgToken)
        self._start_telegram_loop()

    def _feed_to_supybot(self, channel, author, text):
        new_msg = ircmsgs.privmsg(channel, text)
        new_msg.prefix = self._tgIrc.prefix
        new_msg.tag("from_telegram")
        new_msg.nick = author
        self.log.debug("feeding back to supybot: %s", new_msg)
        self._tgIrc.feedMsg(new_msg)

    def _tg_user_repr(self, user):
        user_id = user.get("id", "??")
        last_name = user.get("last_name", "")
        name = user.get("first_name", str(user_id)) + last_name
        chosen = user.get("username", name)
        return user_id, chosen

    def _tg_handle_text(self, message):
        chat_ids = {self.registryValue('tgChatId', ch): ch for ch in self._tgIrc.state.channels}
        msg_chat_id = message.get("chat")
        if not msg_chat_id:
            self.log.warning("Malformed Telegram message")
            return
        msg_chat_id = msg_chat_id.get("id")
        channel = chat_ids.get(msg_chat_id, None)
        if channel is None:
            self.log.info("Got message from unknown Telegram group: %s", msg_chat_id)
            return
        else:
            self.log.debug("Got message from Telegram chat %s, relaying to channel %s", msg_chat_id, channel)

        text = message.get("text", "")
        if not text:
            for msg_type in ("photo", "video", "audio", "sticker", "contact", "location"):
                if message.get(msg_type):
                    text = "<%s>" % msg_type
        user = message.get("from")
        user_id, author = self._tg_user_repr(user)
        if user_id != self._tgId:
            for line in text.splitlines():
                user_repr = "%s> %s" % (author, line)
                self._send_irc_message(channel, user_repr)
                self._feed_to_supybot(channel, author, line)

    def _telegram_discard_previous_updates(self):
        update_id = None
        for update_id, update in self._tg.updates():
            pass
        all(self._tg.updates(state=update_id))

    def _telegram_loop(self):
        self._telegram_discard_previous_updates()
        while True:
            try:
                for message in self._tg.updates_loop(self._tgTimeout):
                    self._tg_handle_text(message)
            except Exception as e:
                self.log.critical("%s", traceback.format_exc())
                self.log.critical("%s", str(e))
            time.sleep(1)

    def _start_telegram_loop(self):
        t = threading.Thread(target=self._telegram_loop)
        t.setDaemon(True)
        t.start()

    def _send_to_chat(self, text, chatId):
        if sys.version_info[0] < 3:
            text = text.decode("utf8", "replace")
            text = text.encode("utf8")
        self._tg.send_message(chatId, text)

    def _send_irc_message(self, channel, text):
        if sys.version_info[0] < 3:
            text = text.encode("utf8", "replace")
        new_msg = ircmsgs.privmsg(channel, text)
        new_msg.tag("from_telegram")
        self._tgIrc.queueMsg(new_msg)

    def doPrivmsg(self, irc, msg):
        irc = callbacks.SimpleProxy(irc, msg)
        channel = msg.args[0]
        if (not msg.isError and channel in irc.state.channels
                and not msg.from_telegram):
            chat_id = self.registryValue("tgChatId", channel)
            if not chat_id or chat_id == 0:
                self.log.debug("TelegramBridge not configured for channel %s", channel)
                return

            text = msg.args[1]
            if ircmsgs.isAction(msg):
                text = ircmsgs.unAction(msg)
                if sys.version_info[0] < 3:
                    text = text.decode("utf8", "replace")
                line = "* %s %s" % (msg.nick, text)
            else:
                if sys.version_info[0] < 3:
                    text = text.decode("utf8", "replace")
                line = "%s> %s" % (msg.nick, text)
            if sys.version_info[0] < 3:
                line = line.encode("utf8", "replace")
            self._send_to_chat(line, chat_id)

    def doTopic(self, irc, msg):
        if len(msg.args) == 1:
            return
        channel = msg.args[0]
        topic = msg.args[1]
        if sys.version_info[0] < 3:
            topic = topic.decode("utf8", "replace")
        line = u"%s: %s" % (channel, topic)
        if sys.version_info[0] < 3:
            line = line.encode("utf8")
        self._send_to_chat(line)

    def outFilter(self, irc, msg):
        if msg.command == "PRIVMSG" and not msg.from_telegram:
            self.doPrivmsg(irc, msg)
        return msg

Class = TelegramBridge


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
