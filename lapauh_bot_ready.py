from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Final

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не найден. Добавь его в переменные окружения.")

FOOD_KCAL_PER_100G: Final[float] = 365.0

INSTAGRAM_URL: Final[str] = "https://www.instagram.com/lapaux_nature"
TELEGRAM_CHANNEL_URL: Final[str] = "https://t.me/lapaux"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

(
    MENU,
    WEIGHT,
    AGE_GROUP,
    STERILIZED,
    ACTIVITY,
) = range(5)


@dataclass
class CatProfile:
    weight_kg: float
    age_group: str
    sterilized: bool
    activity: str


def get_start_keyboard():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Рассчитать норму корма", callback_data="start_calc")]]
    )


def get_age_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("До 1 года", callback_data="age_kitten")],
            [InlineKeyboardButton("1–7 лет", callback_data="age_adult")],
            [InlineKeyboardButton("7+ лет", callback_data="age_senior")],
        ]
    )


def get_yes_no_keyboard(prefix):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Да", callback_data=f"{prefix}_yes")],
            [InlineKeyboardButton("Нет", callback_data=f"{prefix}_no")],
        ]
    )


def get_activity_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Низкая", callback_data="activity_low")],
            [InlineKeyboardButton("Средняя", callback_data="activity_medium")],
            [InlineKeyboardButton("Высокая", callback_data="activity_high")],
        ]
    )


def calc_daily_grams(profile: CatProfile):
    rer = 70 * (profile.weight_kg ** 0.75)

    if profile.age_group == "kitten":
        factor = 2.0
    elif profile.age_group == "senior":
        factor = 1.1 if profile.sterilized else 1.2
    else:
        factor = 1.2 if profile.sterilized else 1.4

    if profile.activity == "low":
        factor *= 0.9
    elif profile.activity == "high":
        factor *= 1.1

    daily_kcal = rer * factor
    grams = daily_kcal / FOOD_KCAL_PER_100G * 100

    min_g = max(1, round(grams * 0.9))
    max_g = max(min_g, round(grams * 1.1))
    return min_g, max_g


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Привет! Я помогу рассчитать суточную норму корма для кота 🐱\n\n"
        "Нажмите кнопку ниже, чтобы начать."
    )

    await update.message.reply_text(text, reply_markup=get_start_keyboard())
    return MENU


async def begin_calculation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Введите вес кота в кг (например 4.2)")
    return WEIGHT


async def weight_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    weight = float(update.message.text.replace(",", "."))
    context.user_data["weight_kg"] = weight

    await update.message.reply_text("Выберите возраст:", reply_markup=get_age_keyboard())
    return AGE_GROUP


async def age_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data["age_group"] = query.data.replace("age_", "")

    await query.message.reply_text(
        "Кот стерилизован?", reply_markup=get_yes_no_keyboard("ster")
    )
    return STERILIZED


async def sterilized_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data["sterilized"] = query.data.endswith("yes")

    await query.message.reply_text(
        "Уровень активности:", reply_markup=get_activity_keyboard()
    )
    return ACTIVITY


async def activity_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    activity = query.data.replace("activity_", "")
    context.user_data["activity"] = activity

    profile = CatProfile(
        weight_kg=context.user_data["weight_kg"],
        age_group=context.user_data["age_group"],
        sterilized=context.user_data["sterilized"],
        activity=activity,
    )

    min_g, max_g = calc_daily_grams(profile)

    text = f"Суточная норма корма: {min_g}-{max_g} г"

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Instagram", url=INSTAGRAM_URL)],
            [InlineKeyboardButton("Telegram", url=TELEGRAM_CHANNEL_URL)],
        ]
    )

    await query.message.reply_text(text, reply_markup=keyboard)

    return MENU


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено")
    return ConversationHandler.END


def main():
    application = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(begin_calculation, pattern="start_calc"),
        ],
        states={
            MENU: [CallbackQueryHandler(begin_calculation, pattern="start_calc")],
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, weight_step)],
            AGE_GROUP: [CallbackQueryHandler(age_step, pattern="age_")],
            STERILIZED: [CallbackQueryHandler(sterilized_step, pattern="ster_")],
            ACTIVITY: [CallbackQueryHandler(activity_step, pattern="activity_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv)

    print("Bot started")
    application.run_polling()


if __name__ == "__main__":
    main()