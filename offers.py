"""
Бот-офферы на NFT-подарки.

Использование в любом чате:  @yourbot nurik 1200 plushpepe-1

Флоу:
1. Покупатель (ты) вызывает инлайн-команду -> в чат падает карточка оффера.
2. Продавец (username из команды) жмёт «Принять» -> видит инструкцию
   передать подарок в профиль покупателя, звёзды будут начислены после передачи.
3. Покупатель жмёт «Получил подарок» -> бот шлёт ему инвойс в звёздах.
4. После оплаты бот уведомляет админа: выплатить продавцу вручную.

Настройка:
  pip install aiogram
  BotFather: /setinline (включить инлайн-режим)
  BOT_TOKEN=... ADMIN_ID=... python offer_bot.py
"""
import asyncio
import os
import time
import uuid

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

BOT_TOKEN = "8829058755:AAEoBYHUT9MJ5TqH7HHWAmr1w5G9N58UhQY"
ADMIN_ID = 7623548272
OFFER_TTL = 6 * 3600  # оффер действует 6 часов

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# id -> dict. Для продакшена замени на sqlite/redis.
offers: dict[str, dict] = {}


def kb(*rows):
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=d) for t, d in row] for row in rows]
    )


def left(o) -> str:
    h = max(0, int((o["created"] + OFFER_TTL - time.time()) // 3600))
    return f"{h}ч."


def card_text(o) -> str:
    return (
        f"💼 @{o['buyer_name']} предлагает @{o['seller']} "
        f"<b>{o['stars']} ⭐</b> за <b>{o['gift']}</b>.\n\n"
        f"Предложение действует ещё {left(o)}"
    )


@dp.message(CommandStart())
async def start(m: Message):
    await m.answer("Используй инлайн: @имя_бота username сумма подарок\nНапример: nurik 1200 plushpepe-1")


@dp.inline_query()
async def inline(q: InlineQuery):
    parts = q.query.strip().split()
    if len(parts) != 3 or not parts[1].isdigit():
        await q.answer([], cache_time=1, switch_pm_text="Формат: nurik 1200 plushpepe-1", switch_pm_parameter="help")
        return
    seller, stars, gift = parts[0].lstrip("@"), int(parts[1]), parts[2]
    oid = uuid.uuid4().hex[:10]
    offers[oid] = dict(
        seller=seller.lower(), stars=stars, gift=gift,
        buyer_id=q.from_user.id, buyer_name=q.from_user.username or q.from_user.full_name,
        created=time.time(), status="new", seller_id=None,
    )
    o = offers[oid]
    o["seller"] = seller  # для отображения
    res = InlineQueryResultArticle(
        id=oid,
        title=f"Оффер: {stars} ⭐ за {gift}",
        description=f"Для @{seller}",
        input_message_content=InputTextMessageContent(message_text=card_text(o), parse_mode="HTML"),
        reply_markup=kb([("Отклонить", f"rej:{oid}"), ("Принять", f"acc:{oid}")]),
    )
    await q.answer([res], cache_time=1, is_personal=True)


def get_offer(c: CallbackQuery, oid: str):
    o = offers.get(oid)
    if not o:
        return None, "Оффер не найден"
    if time.time() > o["created"] + OFFER_TTL and o["status"] == "new":
        o["status"] = "expired"
        return None, "Оффер истёк"
    return o, None


async def edit(c: CallbackQuery, text: str, markup=None):
    await bot.edit_message_text(
        text, inline_message_id=c.inline_message_id, parse_mode="HTML", reply_markup=markup
    )


@dp.callback_query(F.data.startswith("acc:"))
async def accept(c: CallbackQuery):
    o, err = get_offer(c, c.data.split(":")[1])
    if err:
        return await c.answer(err, show_alert=True)
    if (c.from_user.username or "").lower() != o["seller"].lower():
        return await c.answer("Этот оффер не для вас", show_alert=True)
    if o["status"] != "new":
        return await c.answer("Оффер уже обработан", show_alert=True)
    o["status"] = "accepted"
    o["seller_id"] = c.from_user.id
    oid = c.data.split(":")[1]
    await edit(
        c,
        f"✅ @{o['seller']} принял оффер.\n\n"
        f"📦 Передайте подарок <b>{o['gift']}</b> в профиль @{o['buyer_name']}.\n"
        f"💫 <b>{o['stars']} ⭐</b> будут начислены после передачи.",
        kb([("Получил подарок ✅", f"got:{oid}"), ("Отмена", f"cancel:{oid}")]),
    )
    await c.answer("Передайте подарок в профиль отправителя")


@dp.callback_query(F.data.startswith("rej:"))
async def reject(c: CallbackQuery):
    o, err = get_offer(c, c.data.split(":")[1])
    if err:
        return await c.answer(err, show_alert=True)
    if (c.from_user.username or "").lower() != o["seller"].lower():
        return await c.answer("Этот оффер не для вас", show_alert=True)
    o["status"] = "rejected"
    await edit(c, f"❌ @{o['seller']} отклонил оффер на {o['gift']}.")
    await c.answer()


@dp.callback_query(F.data.startswith("cancel:"))
async def cancel(c: CallbackQuery):
    o, err = get_offer(c, c.data.split(":")[1])
    if err:
        return await c.answer(err, show_alert=True)
    if c.from_user.id not in (o["buyer_id"], o["seller_id"]):
        return await c.answer("Нет доступа", show_alert=True)
    if o["status"] != "accepted":
        return await c.answer("Уже нельзя отменить", show_alert=True)
    o["status"] = "cancelled"
    await edit(c, "🚫 Сделка отменена.")
    await c.answer()


@dp.callback_query(F.data.startswith("got:"))
async def got(c: CallbackQuery):
    oid = c.data.split(":")[1]
    o, err = get_offer(c, oid)
    if err:
        return await c.answer(err, show_alert=True)
    if c.from_user.id != o["buyer_id"]:
        return await c.answer("Подтвердить может только покупатель", show_alert=True)
    if o["status"] != "accepted":
        return await c.answer("Неверный статус", show_alert=True)
    o["status"] = "awaiting_payment"
    o["inline_id"] = c.inline_message_id
    try:
        await bot.send_invoice(
            chat_id=c.from_user.id,
            title=f"Оплата: {o['gift']}",
            description=f"Расчёт с @{o['seller']} за подарок {o['gift']}",
            payload=oid,
            currency="XTR",
            prices=[LabeledPrice(label=o["gift"], amount=o["stars"])],
            provider_token="",
        )
    except Exception:
        o["status"] = "accepted"
        return await c.answer("Сначала нажми Start у бота в личке", show_alert=True)
    await c.answer("Инвойс отправлен в личку бота")


@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    o = offers.get(q.invoice_payload)
    await q.answer(ok=bool(o and o["status"] == "awaiting_payment"), error_message="Оффер недоступен")


@dp.message(F.successful_payment)
async def paid(m: Message):
    oid = m.successful_payment.invoice_payload
    o = offers[oid]
    o["status"] = "paid"
    o["charge_id"] = m.successful_payment.telegram_payment_charge_id
    if o.get("inline_id"):
        await bot.edit_message_text(
            f"🎉 Сделка завершена: @{o['seller']} получает <b>{o['stars']} ⭐</b> за {o['gift']}.",
            inline_message_id=o["inline_id"], parse_mode="HTML",
        )
    if ADMIN_ID:
        await bot.send_message(
            ADMIN_ID,
            f"💰 Выплатить @{o['seller']} {o['stars']} ⭐ (оффер {oid}, {o['gift']})\n"
            f"charge_id: {o['charge_id']}",
        )
    await m.answer("Оплачено, продавец получит звёзды.")


async def health(request):
    return web.Response(text="ok")


async def main():
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 10000))).start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
