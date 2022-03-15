import datetime
from json import load

import telegram
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from telegram import Update
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackContext,
    InlineQueryHandler,
    PicklePersistence,
)

from apscheduler.schedulers.background import BackgroundScheduler
import pytz

from random import choice

import sys

import logging

logging.basicConfig()
logging.getLogger("apscheduler").setLevel(logging.DEBUG)

with open("config.json") as f:
    config = load(f)

telegram_token = config["token"]
if not telegram_token:
    sys.exit("No Telegram Token Provided")

moscow_time = pytz.timezone("Europe/Moscow")

updater = Updater(
    telegram_token, persistence=PicklePersistence("py-telegram-bot.pickle")
)
jobstores = {"default": SQLAlchemyJobStore(url="sqlite:///jobs.sqlite")}
scheduler = BackgroundScheduler(jobstores=jobstores, timezone=moscow_time)


def send_message(status: str, token: str, silent=True):
    bot = telegram.Bot(token)
    print(silent, "status: ", status)

    text_to_send = "lol_wut"
    if silent:
        match status:
            case "detained":
                text_to_send = choice(config["detained_texts"])
            case "free":
                text_to_send = choice(config["free_texts"])
            case "arrested":
                text_to_send = choice(config["arrested_texts"]).format(d="вечность.")

    else:
        match status:
            case "detained":
                text_to_send = choice(config["detain_texts"])
            case "free":
                text_to_send = choice(config["release_texts"])
            case "arrest":
                text_to_send = choice(config["arrest_texts"]).format(d="вечность.")

    cur_time = datetime.datetime.now(tz=moscow_time).strftime("%H:%M")

    bot.send_message(
        config["chat_id"], f"{cur_time}\n{text_to_send}", disable_notification=silent
    )


def is_allowed(user_id: int, bot: telegram.Bot):
    admins = list(
        map(lambda x: int(x.user.id), bot.get_chat_administrators(config["chat_id"]))
    )
    print(user_id, list(admins))

    return user_id in admins


def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Хеллоу.")
    if not is_allowed(update.message.from_user.id, context.bot):
        update.message.reply_text("Вы не админ. За вами уже выехали.")
        return
    update.message.reply_text("У вас есть доступ к командам бота!")


def change_status(new_status: str, ctx: CallbackContext) -> None:
    ctx.bot_data["status"] = new_status
    token = config["token"]
    send_message(new_status, token, silent=False)
    scheduler.remove_all_jobs()

    for t in config["update_time"]:
        scheduler.add_job(
            send_message,
            "cron",
            args=[new_status, token],
            hour=t[0],
            minute=t[1],
            second=0,
            misfire_grace_time=30,
        )
    scheduler.print_jobs()


def detain(update: Update, context: CallbackContext) -> None:
    if is_allowed(update.message.from_user.id, context.bot):
        update.message.reply_text(f"Вы задержали {config['name']}. Так держать!")
        change_status("detained", context)


def release(update: Update, context: CallbackContext) -> None:
    if is_allowed(update.message.from_user.id, context.bot):
        update.message.reply_text(
            f"Вы отпустили {config['name']}. Начальство точно будет недовольно..."
        )
        change_status("free", context)


def arrest(update: Update, context: CallbackContext) -> None:
    if is_allowed(update.message.from_user.id, context.bot):
        msg_c = update.message.text.split(" ")
        if len(msg_c) != 2:
            update.message.reply_text(
                f"Чуваки, а когда отпускать надо то?..."
                f"Напишите команду ещё раз, только /arrest <дата (формат - ГГГГ-ММ-ДД)>."
            )
        update.message.reply_text(f"Вы арестовали {config['name']}. Вау!")

        context.bot_data["arrested_until"] = datetime.datetime.fromisoformat(msg_c[1])
        change_status("arrested", context)


updater.dispatcher.add_handler(CommandHandler("start", start))
updater.dispatcher.add_handler(CommandHandler("detain", detain))
updater.dispatcher.add_handler(CommandHandler("release", release))
updater.dispatcher.add_handler(CommandHandler("arrest", release))

telegram_thread = updater.start_polling()
scheduler.start()
updater.idle()
