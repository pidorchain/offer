"""
Inline-бот для офферов на покупку Telegram NFT за Stars.

Установка:  pip install aiogram
Запуск:     BOT_TOKEN=xxx python nft_offer_bot.py
В @BotFather: /setinline

Использование в любом чате:
    @your_bot https://t.me/nft/PlushPepe-1234 500
(последнее число - цена в Stars)
"""
import asyncio
import hashlib
import html
import os
import re

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Message,
)

bot = Bot(os.environ["8829058755:AAEoBYHUT9MJ5TqH7HHWAmr1w5G9N58UhQY"])
dp = Dispatcher()

NFT_RE = re.compile(r"(?:https?://)?t\.me/nft/([A-Za-z0-9_]+-\d+)")
OFFERS: dict[str, dict] = {}  # offer_id -> данные (для продакшена - БД)


def parse(text: str):
    m = NFT_RE.search(text)
    if not m:
        return None
    rest = text.replace(m.group(0), "").strip()
    if not rest.isdigit() or int(rest) <= 0:
        return None
    return m.group(1), int(rest)


def user_name(u) -> str:
    return f"@{u.username}" if u.username else u.full_name


def card(o: dict) -> str:
    return (
        "💎 <b>Оффер на покупку NFT</b>\n\n"
        f"🖼 NFT: <a href=\"https://t.me/nft/{o['nft']}\">{html.escape(o['nft'])}</a>\n"
        f"⭐ Цена: <b>{o['price']} Stars</b>\n"
        f"👤 Покупатель: {html.escape(o['buyer'])}"
    )


@dp.message(CommandStart())
async def start(m: Message):
    me = await bot.get_me()
    await m.answer(
        "Напиши в любом чате:\n"
        f"<code>@{me.username} https://t.me/nft/PlushPepe-1234 500</code>\n"
        "где 500 - цена в Stars.",
        parse_mode="HTML",
    )


@dp.inline_query()
async def inline(q: InlineQuery):
    p = parse(q.query)
    if not p:
        await q.answer([InlineQueryResultArticle(
            id="help",
            title="Как сделать оффер",
            description="Ссылка на NFT и цена в Stars",
            input_message_content=InputTextMessageContent(
                message_text="Формат: @бот https://t.me/nft/PlushPepe-1234 500"),
        )], cache_time=1, is_personal=True)
        return

    nft, price = p
    oid = hashlib.md5(f"{q.from_user.id}:{nft}:{price}".encode()).hexdigest()[:16]
    o = {"nft": nft, "price": price, "buyer": user_name(q.from_user),
         "buyer_id": q.from_user.id, "buyer_username": q.from_user.username}
    OFFERS[oid] = o

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Принять", callback_data=f"acc:{oid}")]])
    await q.answer([InlineQueryResultArticle(
        id=oid,
        title=f"Оффер: {nft}",
        description=f"{price} Stars - нажми, чтобы отправить",
        input_message_content=InputTextMessageContent(
            message_text=card(o), parse_mode="HTML"),
        reply_markup=kb,
    )], cache_time=1, is_personal=True)


@dp.callback_query(F.data.startswith("acc:"))
async def accept(c: CallbackQuery):
    o = OFFERS.get(c.data.split(":", 1)[1])
    if not o:
        await c.answer("Оффер устарел", show_alert=True)
        return
    if c.from_user.id == o["buyer_id"]:
        await c.answer("Нельзя принять свой оффер", show_alert=True)
        return

    # Открываем профиль покупателя (?profile - показать профиль, а не чат)
    if o["buyer_username"]:
        url = f"https://t.me/{o['buyer_username']}?profile"
    else:
        url = f"tg://user?id={o['buyer_id']}"
    rows = [[InlineKeyboardButton(text="🎁 Передать NFT", url=url)]]

    await bot.edit_message_text(
        text=card(o) + f"\n\n✅ Принял: {html.escape(user_name(c.from_user))}",
        inline_message_id=c.inline_message_id,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await c.answer("Оффер принят")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
