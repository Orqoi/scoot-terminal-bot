from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    filters,
)
from config.settings import BOT_TOKEN, logger
from controllers.new_auction import handle_newauction
from controllers.schedule_auction import handle_scheduleauction
from controllers.bid import handle_bid
from controllers.summary import handle_summary
from controllers.help import handle_help
from controllers.bind import handle_bind
from controllers.view_schedule import handle_view_schedule
from controllers.cancel import handle_cancel
from setups.scheduler import on_startup

def main():
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(on_startup)
        .build()
    )

    app.add_handler(CommandHandler(
        "help",
        handle_help,
        filters=filters.ChatType.PRIVATE,
    ))
    app.add_handler(CommandHandler(
        "summary",
        handle_summary,
        filters=filters.ChatType.PRIVATE,
    ))
    app.add_handler(CommandHandler(
        "bind",
        handle_bind,
        filters=filters.ChatType.PRIVATE,
    ))
    app.add_handler(CommandHandler(
        "viewschedule",
        handle_view_schedule,
        filters=filters.ChatType.PRIVATE,
    ))
    app.add_handler(CommandHandler(
        "cancel",
        handle_cancel,
        filters=filters.ChatType.PRIVATE,
    ))
    app.add_handler(MessageHandler(
        filters.PHOTO & filters.ChatType.PRIVATE & filters.CaptionRegex(r'^/schedulesa(\s|$)'),
        handle_scheduleauction
    ))
    app.add_handler(MessageHandler(
        filters.PHOTO & filters.ChatType.PRIVATE & filters.CaptionRegex(r'^/sa(\s|$)'),
        handle_newauction
    ))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS & filters.REPLY, handle_bid))

    logger.info("🤖 Auction bot running")
    app.run_polling()

if __name__ == "__main__":
    main()