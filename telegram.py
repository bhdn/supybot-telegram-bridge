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

import sys
import json
import pprint

if sys.version_info[0] >= 3:
    from urllib.parse import urlencode
    from urllib.request import urlopen
else:
    from urllib import urlencode
    from urllib2 import urlopen

BASEURL = "https://api.telegram.org/bot%(id)s/%(method)s?%(args)s"

class TelegramError(Exception):
    pass

class TelegramBot:

    def __init__(self, id, timeout=600):
        self.id = id
        self.timeout = timeout

    def call(self, method, **args):
        encoded_args = urlencode(args)
        info = dict(id=self.id, method=method, args=encoded_args)
        query_url = BASEURL % (info)
        try:
            data = urlopen(query_url, timeout=self.timeout)
        except EnvironmentError as e:
            raise TelegramError("failed to send request to %s: %s" % (query_url, e))
        if sys.version_info[0] >= 3:
            data = data.read().decode()
        return json.loads(data)

    def updates(self, state=None, timeout=None):
        args = {}
        if state is not None:
            args["offset"] = str(state + 1)
        if timeout is not None:
            args["timeout"] = str(timeout)
        data = self.call("getUpdates", **args)
        if not data.get("ok"):
            raise TelegramError("Request failed: %s" %
                                (data.get("description")))
        for update in data.get("result"):
            update_id = update.get("update_id")
            message = update.get("message")
            if message is not None:
                yield update_id, message

    def updatesLoop(self, timeout):
        update_id = None
        while True:
            for update_id, message in self.updates(state=update_id,
                                              timeout=timeout):
                yield message

    def sendMessage(self, to, message):
        return self.call("sendMessage", chat_id=to, text=message)

    def getMe(self):
        data = self.call("getMe")
        return data
