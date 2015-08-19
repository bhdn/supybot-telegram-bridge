supybot-telegram-bridge
=======================

A Supybot plugin that implements an IRC-Telegram gateway. 

It relies on the [Telegram Bot API](https://core.telegram.org/bots/api).

# Setting it up

1. Create your Telegram bot using [@BotFather](https://core.telegram.org/bots#botfather)
2. Set up your supybot bot using `supybot-wizard`.
3. Clone this repositoy into the `plugins/` directory and rename the
   checkout to `TelegramBridge`
4. Invite the bot to the target Telegram Chat (only one supported now.)
5. Run `./bot-info <TOKEN>` using the token provided by @BotFather; it will
   print the value for `tgChatId` as needed by the supybot bot configuration.
6. Either update the supybot's bot configuration manually or run
   `supybot-wizard` again and fill `tgChatId` and `tgid` from the output of
   the script from the previous step.
7. Ensure `TelegramBridge` is in the list of plugins to load automatically
8. Run `supybot <YOURBOT.conf>`.
9. Enjoy

# Configuration options

* `supybot.plugins.TelegramBridge.tgToken`: The bot's token as provided by
@BotFather
* `supybot.plugins.TelegramBridge.tgChatId`: The chatroom ID (from `bot-info`)
