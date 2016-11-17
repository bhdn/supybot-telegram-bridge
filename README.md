supybot-telegram-bridge
=======================

A Supybot plugin that implements an IRC-Telegram gateway. 

It relies on the [Telegram Bot API](https://core.telegram.org/bots/api).

# Setting it up

1. Create your Telegram bot using [@BotFather](https://core.telegram.org/bots#botfather)
2. Set up your supybot bot using `supybot-wizard`.
3. Clone this repository into the `plugins/` directory and rename the
   checkout to `TelegramBridge`
4. Invite the bot to the target Telegram Chat
5. Start supybot
5. Send a message to the Telegram Chat, and watch the supybot logs for the message
   `Got message from unknown Telegram group:`; the Telegram chat ID will follow.
6. Either update the supybot's bot configuration manually or say `config channel
   <channel_name> plugins.TelegramBridge.tgChatId <chat_id>` to your bot to set
   the Telegram chat ID.
7. Enjoy

# Configuration options

* `supybot.plugins.TelegramBridge.tgToken`: The bot's token as provided by
@BotFather
* `supybot.plugins.TelegramBridge.tgChatId`: The chatroom ID
  **NB:** this is a per-channel configuration option
