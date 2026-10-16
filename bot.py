#!/usr/bin/env python3
"""NutriBob v2 — diario alimentare Telegram bot.

Struttura:
    foods.py      database alimenti (kcal, porzioni, macro)
    nutrition.py  parsing del testo libero + calcoli
    db.py         SQLite
    ui.py         testi HTML, tastiere, logica della scheda bozza
    texts.py      testi statici (/tabella, /consigli)
"""

import logging
import os
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path

from dotenv import load_dotenv
from telegram import BotCommand, InlineKeyboardMarkup, Update
from telegram import InlineKeyboardButton as Btn
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PicklePersistence,
    filters,
)

import db
import texts
import ui
from nutrition import MEAL_TIMES, display_name, meal_for_time, parse_item, parse_message

load_dotenv(Path(__file__).parent / ".env")

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

HTML = ParseMode.HTML


# ── HELPER ───────────────────────────────────────────────────────────────────


def _targets(user_id: int) -> dict:
    profile = db.get_profile(user_id)
    return ui.targets(*profile) if profile else ui.targets(None)


def _parse_weight_kg(text: str):
    cleaned = text.strip().lower().replace("kg", "").strip()
    try:
        weight = float(cleaned.replace(",", "."))
    except ValueError:
        return None
    return weight if 20 <= weight <= 300 else None


def _parse_sgarro(text: str):
    """'450 pizza e gelato' → (450, 'pizza e gelato') oppure None."""
    parts = text.split(None, 1)
    try:
        kcal = int(float(parts[0].replace(",", ".")))
    except (ValueError, IndexError):
        return None
    if kcal <= 0:
        return None
    return kcal, (parts[1].strip() if len(parts) > 1 else "sgarro")


def _timestamp(offset: int, meal: str) -> str:
    if offset == 0:
        return db.now_str()
    d = date.today() - timedelta(days=offset)
    return f"{d.isoformat()} {MEAL_TIMES[meal]}:00"


async def _safe_edit(query, text: str, reply_markup=None) -> None:
    try:
        await query.edit_message_text(text, parse_mode=HTML, reply_markup=reply_markup)
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            raise


# ── BOZZA (scheda modificabile prima del salvataggio) ────────────────────────


def _draft_view(user_id: int, draft: dict):
    day = date.today() - timedelta(days=draft["offset"])
    return ui.render_draft(draft, db.day_totals(user_id, day), _targets(user_id))


async def _show_new_draft(update: Update, context: ContextTypes.DEFAULT_TYPE, parsed: dict) -> None:
    ud = context.user_data
    ud["draft_seq"] = ud.get("draft_seq", 0) + 1
    draft = ui.new_draft(ud["draft_seq"], parsed)
    ud["draft"] = draft
    text, kb = _draft_view(update.effective_user.id, draft)
    await update.message.reply_text(text, parse_mode=HTML, reply_markup=kb)


def _save_draft(user_id: int, draft: dict) -> list[int]:
    ts = _timestamp(draft["offset"], draft["meal"])
    ids = []
    for it in draft["items"]:
        ids.append(db.add_entry(
            user_id, display_name(it["key"]), it["kcal"], it["desc"], ts,
            meal=draft["meal"], protein_g=it["p"], carbs_g=it["c"], fat_g=it["f"],
            grams=it["grams"], food_key=it["key"],
        ))
    return ids


async def on_draft_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, parts: list[str]) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    draft = context.user_data.get("draft")
    draft_id, act, args = int(parts[1]), parts[2], parts[3:]

    if not draft or draft["id"] != draft_id:
        await query.answer("Questa scheda è scaduta — mandami di nuovo il messaggio.", show_alert=True)
        return
    await query.answer()

    outcome = ui.draft_action(draft, act, args)

    if outcome == "cancel":
        context.user_data.pop("draft", None)
        await _safe_edit(query, "❌ Non salvato.")
        return

    if outcome == "save":
        ids = _save_draft(user_id, draft)
        context.user_data.pop("draft", None)
        context.user_data["last_saved"] = ids
        offset = draft["offset"]
        day = date.today() - timedelta(days=offset)
        tot, tgt = db.day_totals(user_id, day), _targets(user_id)
        added = ui.draft_totals(draft)
        names = ", ".join(display_name(i["key"]) for i in draft["items"])
        text = (
            f"✅ <b>Salvato</b> in {ui.MEAL_LABELS[draft['meal']]} · {ui.day_label(offset)}\n"
            f"<i>{escape(names)}</i>\n"
            f"+{added['kcal']} kcal · {ui.macro_line(added['p'], added['c'], added['f'])}\n\n"
            f"{ui.bar(tot['kcal'], tgt['kcal'])}\n"
            f"<b>{tot['kcal']}/{tgt['kcal']} kcal</b> · {ui.macro_line(tot['p'], tot['c'], tot['f'])}"
        )
        kb = InlineKeyboardMarkup([[
            Btn("↩️ Annulla", callback_data="undo"),
            Btn("📖 Diario", callback_data=f"dy:{offset}"),
        ]])
        await _safe_edit(query, text, kb)
        return

    text, kb = _draft_view(user_id, draft)
    await _safe_edit(query, text, kb)


async def _maybe_set_quantity_from_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    """Se c'è una voce in modifica e il messaggio è solo una quantità ('150', '150g', '2'), la applica."""
    draft = context.user_data.get("draft")
    if not draft or draft.get("view") != "edit":
        return False
    p = parse_item(text)
    if p.food:
        return False
    item = draft["items"][draft["sel"]]
    if p.unit == "pcs" and p.unit_word:
        item["unit_word"] = p.unit_word
    ui.set_quantity(item, p.qty, unit=p.unit)
    draft["view"] = "card"
    # ridisegna come nuovo messaggio (la scheda vecchia scade cambiando id)
    context.user_data["draft_seq"] = context.user_data.get("draft_seq", 0) + 1
    draft["id"] = context.user_data["draft_seq"]
    text_, kb = _draft_view(update.effective_user.id, draft)
    await update.message.reply_text(text_, parse_mode=HTML, reply_markup=kb)
    return True


# ── COMANDI ──────────────────────────────────────────────────────────────────


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    profile = db.get_profile(user_id)
    if profile is None:
        context.user_data["awaiting"] = "weight_goal"
        await update.message.reply_text(
            "👋 Ciao! Sono <b>NutriBob</b>, il tuo diario alimentare.\n\n"
            "Per calcolare il tuo obiettivo dimmi il tuo <b>peso in kg</b> (es. <code>75</code>):",
            parse_mode=HTML, reply_markup=ui.main_menu(),
        )
        return
    await update.message.reply_text(ui.welcome_text(*profile), parse_mode=HTML, reply_markup=ui.main_menu())


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = db.get_profile(update.effective_user.id) or (None, "main")
    await update.message.reply_text(ui.welcome_text(*profile), parse_mode=HTML, reply_markup=ui.main_menu())


async def _send_diary(update: Update, offset: int) -> None:
    uid = update.effective_user.id
    day = date.today() - timedelta(days=offset)
    text, kb = ui.render_diary(db.get_day(uid, day), offset, _targets(uid))
    await update.message.reply_text(text, parse_mode=HTML, reply_markup=kb)


async def cmd_oggi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_diary(update, 0)


async def cmd_ieri(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_diary(update, 1)


async def cmd_settimana(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    await update.message.reply_text(ui.render_week(db.weekly(uid), _targets(uid)), parse_mode=HTML)


async def cmd_profilo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    profile = db.get_profile(uid)
    if profile is None:
        context.user_data["awaiting"] = "weight_goal"
        await update.message.reply_text("⚖️ Non ho ancora il tuo peso. Mandamelo in kg (es. <code>75</code>):",
                                        parse_mode=HTML)
        return
    weight, goal = profile
    t = ui.targets(weight, goal)
    await update.message.reply_text(
        f"👤 <b>Profilo</b>\n"
        f"Peso: <b>{weight} kg</b>\n"
        f"Obiettivo: {ui.GOAL_LABELS.get(goal, goal)} — <i>{ui.GOAL_DESC.get(goal, '')}</i>\n\n"
        f"🎯 <b>{t['kcal']} kcal/giorno</b>\n"
        f"💪 Proteine {t['p']}g · 🍞 Carboidrati {t['c']}g · 🥑 Grassi {t['f']}g\n\n"
        "Cambia obiettivo:",
        parse_mode=HTML, reply_markup=ui.goal_keyboard(),
    )


async def cmd_peso(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    raw = " ".join(context.args).strip() if context.args else ""
    if not raw:
        context.user_data["awaiting"] = "weight"
        rows = db.get_weight_history(uid)
        await update.message.reply_text(
            ui.render_weight(rows) + "\n\n✏️ Scrivimi il peso di oggi (es. <code>74.8</code>) "
            "oppure /annulla", parse_mode=HTML)
        return
    await _save_weight(update, context, raw, ask_goal=False)


async def _save_weight(update: Update, context: ContextTypes.DEFAULT_TYPE, raw: str, ask_goal: bool) -> None:
    uid = update.effective_user.id
    weight = _parse_weight_kg(raw)
    if weight is None:
        await update.message.reply_text("⚠️ Peso non valido, scrivi un numero in kg (es. <code>74.8</code>):",
                                        parse_mode=HTML)
        return
    context.user_data.pop("awaiting", None)
    db.set_weight(uid, weight)
    if ask_goal:
        await update.message.reply_text(f"✅ Peso salvato: <b>{weight} kg</b>\n\n🎯 Qual è il tuo obiettivo?",
                                        parse_mode=HTML, reply_markup=ui.goal_keyboard())
        return
    await update.message.reply_text("✅ Peso salvato!\n\n" + ui.render_weight(db.get_weight_history(uid)),
                                    parse_mode=HTML)


async def cmd_sgarro(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    raw = " ".join(context.args).strip() if context.args else ""
    if not raw:
        context.user_data["awaiting"] = "sgarro"
        await update.message.reply_text(
            "🍕 <b>Sgarro!</b> Mandami le kcal e una nota (opzionale):\n"
            "<code>450 pizza e gelato</code>  ·  /annulla", parse_mode=HTML)
        return
    await _save_sgarro(update, context, raw)


async def _save_sgarro(update: Update, context: ContextTypes.DEFAULT_TYPE, raw: str) -> None:
    uid = update.effective_user.id
    parsed = _parse_sgarro(raw)
    if parsed is None:
        await update.message.reply_text("⚠️ Scrivi prima le kcal, poi la nota. Es: <code>450 pizza e gelato</code>",
                                        parse_mode=HTML)
        return
    context.user_data.pop("awaiting", None)
    kcal, note = parsed
    db.add_entry(uid, note, kcal, f"{kcal} kcal", db.now_str(), meal=meal_for_time(datetime.now()))
    tot, tgt = db.day_totals(uid, date.today()), _targets(uid)
    await update.message.reply_text(
        f"🍕 <b>Sgarro registrato</b>: <i>{escape(note)}</i> — {kcal} kcal\n\n"
        f"{ui.bar(tot['kcal'], tgt['kcal'])}\n<b>{tot['kcal']}/{tgt['kcal']} kcal</b>",
        parse_mode=HTML)


async def cmd_annulla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("awaiting", None)
    context.user_data.pop("draft", None)
    await update.message.reply_text("OK, annullato.", reply_markup=ui.main_menu())


async def cmd_cancella(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    row = db.delete_last(update.effective_user.id)
    if row:
        await update.message.reply_text(f"🗑 Rimossa: <b>{escape(row[0])}</b> ({row[1]} kcal)", parse_mode=HTML)
    else:
        await update.message.reply_text("📭 Nessuna voce da eliminare.")


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    kb = InlineKeyboardMarkup([[Btn("✅ Sì, svuota oggi", callback_data="reset:yes"),
                                Btn("❌ No", callback_data="reset:no")]])
    await update.message.reply_text("⚠️ Eliminare <b>tutte</b> le voci di oggi?", parse_mode=HTML, reply_markup=kb)


async def cmd_tabella(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(texts.TABELLA, parse_mode=ParseMode.MARKDOWN)


async def cmd_consigli(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(texts.CONSIGLI, parse_mode=ParseMode.MARKDOWN)


# ── MESSAGGI DI TESTO ────────────────────────────────────────────────────────

_MENU_ACTIONS = {
    ui.MENU_DIARY: cmd_oggi,
    ui.MENU_WEEK: cmd_settimana,
    ui.MENU_WEIGHT: cmd_peso,
    ui.MENU_PROFILE: cmd_profilo,
    ui.MENU_SGARRO: cmd_sgarro,
    ui.MENU_HELP: cmd_help,
}


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()

    if text in _MENU_ACTIONS:
        context.args = []
        await _MENU_ACTIONS[text](update, context)
        return

    awaiting = context.user_data.get("awaiting")
    if awaiting in ("weight", "weight_goal"):
        await _save_weight(update, context, text, ask_goal=awaiting == "weight_goal")
        return
    if awaiting == "sgarro":
        await _save_sgarro(update, context, text)
        return

    if await _maybe_set_quantity_from_text(update, context, text):
        return

    parsed = parse_message(text)
    if not parsed["items"] and not parsed["unknown"]:
        await update.message.reply_text("🤔 Non ho capito. Prova ad esempio: <code>200g pasta e 2 uova</code>",
                                        parse_mode=HTML)
        return
    if not parsed["items"] and not any(u["suggestions"] for u in parsed["unknown"]):
        names = ", ".join(u["text"] for u in parsed["unknown"])
        await update.message.reply_text(
            f"🤔 Non trovo <b>{escape(names)}</b> nel database.\n"
            "Prova con un nome più semplice, oppure registralo con /sgarro e le kcal.",
            parse_mode=HTML)
        return
    await _show_new_draft(update, context, parsed)


# ── CALLBACK ─────────────────────────────────────────────────────────────────


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    uid = query.from_user.id
    parts = query.data.split(":")
    kind = parts[0]

    if kind == "d":
        await on_draft_callback(update, context, parts)
        return

    await query.answer()

    if kind == "dy":        # naviga nel diario
        offset = max(0, int(parts[1]))
        day = date.today() - timedelta(days=offset)
        text, kb = ui.render_diary(db.get_day(uid, day), offset, _targets(uid))
        await _safe_edit(query, text, kb)

    elif kind == "dd":      # modalità elimina
        offset = int(parts[1])
        day = date.today() - timedelta(days=offset)
        text, kb = ui.render_diary(db.get_day(uid, day), offset, _targets(uid), delete_mode=True)
        await _safe_edit(query, text, kb)

    elif kind == "dx":      # elimina una voce
        offset, entry_id = int(parts[1]), int(parts[2])
        db.delete_entries(uid, [entry_id])
        day = date.today() - timedelta(days=offset)
        rows = db.get_day(uid, day)
        text, kb = ui.render_diary(rows, offset, _targets(uid), delete_mode=bool(rows))
        await _safe_edit(query, text, kb)

    elif kind == "undo":
        ids = context.user_data.pop("last_saved", [])
        n = db.delete_entries(uid, ids)
        await _safe_edit(query, f"↩️ Annullato ({n} voci rimosse)." if n else "Niente da annullare.")

    elif kind == "reset":
        if parts[1] == "yes":
            n = db.delete_day(uid, date.today())
            await _safe_edit(query, f"🗑 Diario di oggi svuotato ({n} voci).")
        else:
            await _safe_edit(query, "OK, nessuna modifica.")

    elif kind == "goal":
        goal = parts[1]
        if goal not in ui.GOAL_MULTIPLIER:
            return
        db.set_goal(uid, goal)
        weight, _ = db.get_profile(uid) or (None, goal)
        t = ui.targets(weight, goal)
        await _safe_edit(
            query,
            f"{ui.GOAL_LABELS[goal]} — <i>{ui.GOAL_DESC[goal]}</i>\n\n"
            f"🎯 <b>{t['kcal']} kcal/giorno</b> · P {t['p']}g · C {t['c']}g · G {t['f']}g\n\n"
            "Ora scrivimi cosa hai mangiato! Es: <code>200g pasta, 2 uova e una mela</code>",
        )


# ── MAIN ─────────────────────────────────────────────────────────────────────

COMMANDS = [
    BotCommand("oggi", "Diario di oggi"),
    BotCommand("ieri", "Diario di ieri"),
    BotCommand("settimana", "Ultimi 7 giorni"),
    BotCommand("peso", "Registra il peso"),
    BotCommand("profilo", "Peso e obiettivo"),
    BotCommand("sgarro", "Registra kcal libere"),
    BotCommand("cancella", "Elimina l'ultima voce"),
    BotCommand("reset", "Svuota il diario di oggi"),
    BotCommand("tabella", "Unità di misura"),
    BotCommand("consigli", "Alimenti consigliati"),
    BotCommand("help", "Come si usa"),
]


async def _post_init(app: Application) -> None:
    await app.bot.set_my_commands(COMMANDS)


def build_app(token: str) -> Application:
    db.init_db()
    persistence = PicklePersistence(filepath=db.DATA_DIR / "bot_state.pickle")
    app = Application.builder().token(token).persistence(persistence).post_init(_post_init).build()

    for name, fn in [
        ("start", cmd_start), ("help", cmd_help), ("oggi", cmd_oggi), ("ieri", cmd_ieri),
        ("settimana", cmd_settimana), ("profilo", cmd_profilo), ("peso", cmd_peso),
        ("sgarro", cmd_sgarro), ("annulla", cmd_annulla), ("cancella", cmd_cancella),
        ("reset", cmd_reset), ("tabella", cmd_tabella), ("consigli", cmd_consigli),
    ]:
        app.add_handler(CommandHandler(name, fn))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app


def main() -> None:
    token = os.environ["BOT_TOKEN"]  # da variabile d'ambiente o .env, mai nel codice
    app = build_app(token)
    logger.info("NutriBob v2 avviato — in ascolto...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    import asyncio
    asyncio.set_event_loop(asyncio.new_event_loop())
    main()
