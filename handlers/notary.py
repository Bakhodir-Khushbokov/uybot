"""
Notariat xizmati moduli.

Foydalanuvchi oqimi:
  1. "📜 Uy hujjatlarini tekshirish" tugmasi yoki /notary buyrug'i
  2. Hujjat turi tanlanadi
  3. Hujjat rasmi/scan yuklanadi
  4. To'lov cheki (screenshot) yuklanadi
  5. Zayavka adminga yuboriladi, foydalanuvchiga ID beriladi

Admin oqimi (admin.py orqali):
  adm_not:{action}:{order_id}  → approve / reject / assign:{admin_id}
"""
import asyncio
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command

import json
from config import ADMIN_IDS, OWNER_IDS, MEDIA_CHANNEL_ID
import database as db
from keyboards.reply import cancel_kb, main_menu_kb

# user_id → asyncio.Task (debounce)
_doc_timers: dict[int, asyncio.Task] = {}

router = Router()

NOTARY_FEE = "50 000 so'm"          # namoyish uchun; real ma'lumot .env da bo'lishi mumkin
NOTARY_CARD = "8600 1234 5678 9012"  # to'lov kartasi (config dan ham olish mumkin)

DOC_TYPES = {
    "savdo": "📄 Uy oldi-sottisi shartnomasi",
}

STATUS_LABELS = {
    "new":           "🆕 Yangi",
    "payment_check": "💳 To'lov tekshirilmoqda",
    "processing":    "⚙️ Jarayonda",
    "done":          "✅ Bajarildi",
    "rejected":      "❌ Rad etildi",
}


class NotaryStates(StatesGroup):
    doc_type    = State()
    upload_doc  = State()
    upload_pay  = State()
    confirm     = State()


class NotaryWorkerStates(StatesGroup):
    upload_result = State()   # notarius natija rasmlarini yuklaydi


# notarius_id → order_id (qaysi zayavka uchun rasm kutilmoqda)
_worker_result_timers: dict[int, asyncio.Task] = {}
_worker_order_map:    dict[int, int] = {}   # notarius_id → order_id


# ── Inline klaviaturalar ─────────────────────────────────────
def doc_type_kb() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=label, callback_data=f"nt_dt:{key}")]
            for key, label in DOC_TYPES.items()]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def notary_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Yuborish",       callback_data="nt:send")],
        [InlineKeyboardButton(text="🔄 Qaytadan boshlash", callback_data="nt:restart")],
        [InlineKeyboardButton(text="❌ Bekor qilish",   callback_data="nt:cancel")],
    ])


def admin_notary_kb(order_id: int, assigned: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="✅ Qabul qilish",   callback_data=f"adm_not:approve:{order_id}"),
         InlineKeyboardButton(text="❌ Rad etish",      callback_data=f"adm_not:reject:{order_id}")],
        [InlineKeyboardButton(text="⚙️ Jarayonga olish", callback_data=f"adm_not:process:{order_id}")],
        [InlineKeyboardButton(text="✔️ Bajarildi",      callback_data=f"adm_not:done:{order_id}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Boshlash ─────────────────────────────────────────────────
@router.message(F.text == "📜 Uy hujjatlarini tekshirish")
@router.message(Command("notary"))
async def notary_start(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer(
        "📜 <b>Ko'chmas mulk hujjatlarini notariusga tayyorligini online tekshirish</b>\n\n"
        "Uy hujjatlari notariusga tayyormi, qarzlari bormi yoki taqiqda turibdimi — "
        "hammasini bir zumda online tekshirib olasiz:\n\n"
        "1. 🏛 Soliq qarzdorligi\n"
        "2. 📐 Kadastr — taqiq, arest va cheklovlar mavjud emasligi; egalik huquqi hujjatga mosligi\n"
        "3. ⚡️ Elektr energiyasi\n"
        "4. 🔥 Gaz xizmati\n"
        "5. 💧 Sovuq suv va oqava suv\n"
        "6. ♨️ Issiq suv va isitish tizimi\n"
        "7. 🏠 Mening uyim (JEK)\n"
        "8. 🪪 IIV — propiska (uyda ro'yxatda turgan shaxslar, shu jumladan voyaga yetmaganlar)\n"
        "9. 🗑 Toza hudud — chiqindi\n\n"
        f"💳 <b>Xizmat narxi: {NOTARY_FEE}</b>\n\n"
        "📎 Hujjatlarning <b>sifatli rasmini</b> yuboring:\n\n"
        "1️⃣ Egalik huquqini tasdiqlovchi hujjat <i>(oldi-sotdi, meros yoki boshqa)</i>\n"
        "2️⃣ Kadastr ko'chirmasi\n"
        "3️⃣ Mulkdorning pasporti yoki ID kartasi <i>(oldi-orqa tomoni)</i>\n\n"
        "─────────────────────\n"
        "✅ Ushbu tekshiruv orqali notariusga borishdan oldin barcha xatarlarni kamaytirasiz.",
        reply_markup=cancel_kb(),
        parse_mode="HTML",
    )
    await state.update_data(doc_type="savdo", doc_label="📄 Uy oldi-sottisi shartnomasi")
    await state.set_state(NotaryStates.upload_doc)


@router.callback_query(NotaryStates.doc_type, F.data.startswith("nt_dt:"))
async def notary_doc_type(cb: CallbackQuery, state: FSMContext):
    key = cb.data.split(":")[1]
    label = DOC_TYPES.get(key, "Hujjat")
    await state.update_data(doc_type=key, doc_label=label)
    await cb.message.edit_text(
        f"✅ Tanlandi: <b>{label}</b>\n\n"
        "📎 Endi hujjatni (pasport, guvohnoma yoki shartnoma) "
        "<b>rasm yoki fayl</b> ko'rinishida yuboring:",
        parse_mode="HTML",
    )
    await cb.message.answer("Bekor qilish uchun:", reply_markup=cancel_kb())
    await state.set_state(NotaryStates.upload_doc)
    await cb.answer()


# ── Hujjat yuklanishi (debounce — oxirgi rasmdan 3 sek keyin) ─
@router.message(NotaryStates.upload_doc, F.photo | F.document)
async def notary_got_doc(msg: Message, state: FSMContext):
    if msg.photo:
        file_id = msg.photo[-1].file_id
    elif msg.document:
        file_id = msg.document.file_id
    else:
        return

    data = await state.get_data()
    doc_files = data.get("doc_files") or []
    doc_files.append(file_id)
    await state.update_data(doc_files=doc_files, doc_file_id=doc_files[0])

    user_id = msg.from_user.id

    # Oldingi taymerini bekor qil
    if user_id in _doc_timers:
        _doc_timers[user_id].cancel()

    # 3 soniya kutib, xabar yuborish
    async def _send_payment_prompt():
        await asyncio.sleep(3)
        count = len(doc_files)
        await msg.answer(
            f"✅ <b>{count} ta hujjat qabul qilindi!</b>\n\n"
            f"💳 Endi to'lovni amalga oshiring:\n\n"
            f"📲 Karta raqami:\n<code>{NOTARY_CARD}</code>\n\n"
            f"Miqdor: <b>{NOTARY_FEE}</b>\n\n"
            "To'lovdan so'ng chekni <b>(rasm yoki screenshot)</b> yuboring 👇",
            parse_mode="HTML",
        )
        await state.set_state(NotaryStates.upload_pay)
        _doc_timers.pop(user_id, None)

    task = asyncio.create_task(_send_payment_prompt())
    _doc_timers[user_id] = task


@router.message(NotaryStates.upload_doc)
async def notary_doc_wrong(msg: Message):
    if msg.text == "❌ Bekor qilish":
        return
    await msg.answer("📎 Iltimos, hujjat rasmi yoki faylini yuboring.")


# ── To'lov cheki ─────────────────────────────────────────────
@router.message(NotaryStates.upload_pay, F.photo | F.document)
async def notary_got_payment(msg: Message, state: FSMContext):
    if msg.photo:
        file_id = msg.photo[-1].file_id
    elif msg.document:
        file_id = msg.document.file_id
    else:
        await msg.answer("Iltimos, to'lov chekini rasm ko'rinishida yuboring.")
        return

    await state.update_data(payment_file_id=file_id)
    data = await state.get_data()

    await msg.answer(
        "✅ <b>To'lov cheki qabul qilindi!</b>\n\n"
        f"📋 Hujjat turi: <b>{data.get('doc_label', '')}</b>\n"
        f"💳 To'lov: <b>{NOTARY_FEE}</b>\n\n"
        "Zayavkani notariusga yuboraylikmi?",
        reply_markup=notary_confirm_kb(),
        parse_mode="HTML",
    )
    await state.set_state(NotaryStates.confirm)


@router.message(NotaryStates.upload_pay)
async def notary_pay_wrong(msg: Message):
    if msg.text == "❌ Bekor qilish":
        return
    await msg.answer("📸 Iltimos, to'lov chekining rasmini yuboring.")


# ── Tasdiqlash ───────────────────────────────────────────────
@router.callback_query(NotaryStates.confirm, F.data == "nt:send")
async def notary_send(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = await db.get_user(cb.from_user.id)

    order_id = await db.create_notary_order(
        user_id=cb.from_user.id,
        listing_id=data.get("listing_id"),
        doc_file_id=saved_doc_fids[0] if saved_doc_fids else data.get("doc_file_id"),
        doc_type=data.get("doc_type"),
        doc_files_json=json.dumps(saved_doc_fids, ensure_ascii=False),
    )
    await db.set_notary_payment(order_id, saved_payment_fid)

    sender = f"@{cb.from_user.username}" if cb.from_user.username else f"#{cb.from_user.id}"
    full_name = cb.from_user.full_name or ""

    import datetime
    now = datetime.datetime.now().strftime('%d.%m.%Y %H:%M')

    # ── Rasmlarni kanalga saqlash ──────────────────────────────
    doc_files      = data.get("doc_files") or [data.get("doc_file_id")]
    payment_fid    = data.get("payment_file_id")
    saved_doc_fids = []

    for i, fid in enumerate(doc_files, 1):
        try:
            sent = await cb.bot.send_photo(
                MEDIA_CHANNEL_ID, photo=fid,
                caption=f"📎 Hujjat {i}/{len(doc_files)} | User:{cb.from_user.id} | {now}",
            )
            saved_doc_fids.append(sent.photo[-1].file_id)
        except Exception:
            saved_doc_fids.append(fid)  # fallback: original file_id

    try:
        pay_sent = await cb.bot.send_photo(
            MEDIA_CHANNEL_ID, photo=payment_fid,
            caption=f"💳 To'lov cheki | User:{cb.from_user.id} | {now}",
        )
        saved_payment_fid = pay_sent.photo[-1].file_id
    except Exception:
        saved_payment_fid = payment_fid

    # Faqat notarius rolidagi adminlarga yuborish
    # Agar notarius yo'q bo'lsa — super-admin va config adminlarga
    notary_ids = await db.get_notary_admin_ids()
    if not notary_ids:
        notary_ids = list(set(ADMIN_IDS + await db.get_admin_ids()))

    # Notariusga to'liq zayavka xabari
    notary_text = (
        f"📜 <b>Yangi zayavka #{order_id}</b>\n\n"
        f"👤 Mijoz: {sender} | {full_name}\n"
        f"📋 Hujjat: <b>{data.get('doc_label', '')}</b>\n"
        f"💳 To'lov: <b>{NOTARY_FEE}</b> — chek yuborilgan\n"
        f"📅 Vaqt: {now}\n\n"
        "⬇️ Hujjat va to'lov cheki quyida:"
    )

    for nid in notary_ids:
        try:
            # Barcha hujjat rasmlari (kanaldan saqlangan)
            for i, fid in enumerate(saved_doc_fids, 1):
                await cb.bot.send_photo(
                    nid, photo=fid,
                    caption=f"📎 Hujjat {i}/{len(saved_doc_fids)} — Zayavka #{order_id}",
                )
            # To'lov cheki
            await cb.bot.send_photo(
                nid, photo=saved_payment_fid,
                caption=f"💳 To'lov cheki — Zayavka #{order_id}",
            )
            # Asosiy xabar + tugmalar
            await cb.bot.send_message(
                nid, notary_text,
                reply_markup=admin_notary_kb(order_id),
                parse_mode="HTML",
            )
        except Exception:
            pass

    # Super-adminga faqat xabar (hujjatsiz, tugmasiz) — hisobot uchun
    owner_text = (
        f"📊 <b>Yangi notariat zayavkasi #{order_id}</b>\n"
        f"Mijoz: {sender} | Vaqt: {now}\n"
        f"Notariuslarga yuborildi: {len(notary_ids)} ta"
    )
    from config import OWNER_IDS
    for oid in OWNER_IDS:
        try:
            await cb.bot.send_message(oid, owner_text, parse_mode="HTML")
        except Exception:
            pass

    await cb.message.edit_text(
        f"✅ <b>Zayavka #{order_id} qabul qilindi!</b>\n\n"
        "Notarius hujjatlaringizni ko'rib chiqadi va natija haqida "
        "bot orqali xabar beriladi.\n\n"
        f"📋 Zayavka raqamingiz: <b>#{order_id}</b>",
        parse_mode="HTML",
    )
    await state.clear()
    await cb.message.answer("Asosiy menyu:", reply_markup=main_menu_kb())
    await cb.answer("✅ Yuborildi!")


@router.callback_query(NotaryStates.confirm, F.data == "nt:restart")
async def notary_restart(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await notary_start(cb.message, state)
    await cb.answer()


@router.callback_query(NotaryStates.confirm, F.data == "nt:cancel")
async def notary_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("❌ Bekor qilindi.")
    await cb.message.answer("Asosiy menyu:", reply_markup=main_menu_kb())
    await cb.answer()


# ── Notarius: zayavkani ko'rib chiqish ──────────────────────
@router.callback_query(F.data.startswith("adm_not:"))
async def admin_notary_action(cb: CallbackQuery, state: FSMContext):
    parts    = cb.data.split(":")
    action   = parts[1]
    order_id = int(parts[2])

    order = await db.get_notary_order(order_id)
    if not order:
        await cb.answer("Zayavka topilmadi.", show_alert=True)
        return

    # "done" bosilganda — avval natija rasmlarini so'raymiz
    if action == "done":
        _worker_order_map[cb.from_user.id] = order_id
        await cb.message.edit_reply_markup(reply_markup=None)
        await cb.message.answer(
            f"📤 <b>Zayavka #{order_id} — natija rasmlari</b>\n\n"
            "Tekshirilgan hujjat va to'lov chekining rasmini yuboring.\n"
            "Bir nechta rasm yuborishingiz mumkin.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"not_res:cancel:{order_id}")]
            ])
        )
        await state.set_state(NotaryWorkerStates.upload_result)
        await cb.answer()
        return

    action_map = {
        "approve": ("payment_check", "✅ To'lov qabul qilindi"),
        "process": ("processing",    "⚙️ Jarayonga olindi"),
        "reject":  ("rejected",      "❌ Rad etildi"),
    }

    if action not in action_map:
        await cb.answer()
        return

    new_status, status_text = action_map[action]
    await db.update_notary_order(order_id, new_status, assigned_to=cb.from_user.id)

    user_msgs = {
        "payment_check": (
            f"✅ <b>Zayavka #{order_id}: to'lovingiz qabul qilindi!</b>\n\n"
            "Hujjatingiz notariat tomonidan ko'rib chiqilmoqda."
        ),
        "processing": (
            f"⚙️ <b>Zayavka #{order_id}: ishga tushdi!</b>\n\n"
            "Notarius hujjatingizni tayyorlashni boshladi."
        ),
        "rejected": (
            f"❌ <b>Zayavka #{order_id} rad etildi.</b>\n\n"
            "Sabab: hujjat yoki to'lov muammosi. Qayta murojaat qiling: /notary"
        ),
    }
    try:
        await cb.bot.send_message(
            order["user_id"], user_msgs.get(new_status, ""), parse_mode="HTML"
        )
    except Exception:
        pass

    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer(f"✅ Zayavka #{order_id} → <b>{status_text}</b>", parse_mode="HTML")
    await cb.answer(status_text)


# ── Notarius: natija rasmlarini yuklash (debounce) ───────────
@router.message(NotaryWorkerStates.upload_result, F.photo | F.document)
async def notary_worker_result_photo(msg: Message, state: FSMContext):
    if msg.photo:
        file_id = msg.photo[-1].file_id
    else:
        file_id = msg.document.file_id

    data = await state.get_data()
    result_files = data.get("result_files") or []
    result_files.append(file_id)
    await state.update_data(result_files=result_files)

    worker_id = msg.from_user.id
    if worker_id in _worker_result_timers:
        _worker_result_timers[worker_id].cancel()

    async def _send_results():
        await asyncio.sleep(3)
        order_id = _worker_order_map.get(worker_id)
        if not order_id:
            return

        order = await db.get_notary_order(order_id)
        if not order:
            return

        import datetime
        now = datetime.datetime.now().strftime('%d.%m.%Y %H:%M')

        # Kanalga saqlash
        saved_fids = []
        for i, fid in enumerate(result_files, 1):
            try:
                sent = await msg.bot.send_photo(
                    MEDIA_CHANNEL_ID, photo=fid,
                    caption=f"📤 Natija {i}/{len(result_files)} | Order:{order_id} | {now}",
                )
                saved_fids.append(sent.photo[-1].file_id)
            except Exception:
                saved_fids.append(fid)

        # Mijozga yuborish
        try:
            await msg.bot.send_message(
                order["user_id"],
                f"✅ <b>Zayavka #{order_id} bajarildi!</b>\n\n"
                "Notarius tekshirilgan hujjatlaringizni yubordi 👇",
                parse_mode="HTML",
            )
            for fid in saved_fids:
                await msg.bot.send_photo(order["user_id"], photo=fid)
        except Exception:
            pass

        # Status yangilash
        await db.update_notary_order(order_id, "done", assigned_to=worker_id)

        await msg.answer(
            f"✅ <b>Zayavka #{order_id} bajarildi!</b>\n"
            f"Mijozga {len(saved_fids)} ta rasm yuborildi.",
            parse_mode="HTML",
        )
        await state.clear()
        _worker_order_map.pop(worker_id, None)
        _worker_result_timers.pop(worker_id, None)

    task = asyncio.create_task(_send_results())
    _worker_result_timers[worker_id] = task

    await msg.answer(
        f"✅ {len(result_files)} ta rasm qabul qilindi.\n"
        "Yana rasm yuborishingiz yoki kutishingiz mumkin (3 soniya).",
    )


@router.callback_query(NotaryWorkerStates.upload_result, F.data.startswith("not_res:cancel:"))
async def notary_result_cancel(cb: CallbackQuery, state: FSMContext):
    worker_id = cb.from_user.id
    if worker_id in _worker_result_timers:
        _worker_result_timers[worker_id].cancel()
    _worker_order_map.pop(worker_id, None)
    await state.clear()
    await cb.message.edit_text("❌ Bekor qilindi. Zayavka hali ham ochiq.")
    await cb.answer()


@router.message(NotaryWorkerStates.upload_result)
async def notary_worker_result_wrong(msg: Message):
    if msg.text and msg.text.startswith("❌"):
        return
    await msg.answer("📸 Iltimos, rasm yuboring.")
