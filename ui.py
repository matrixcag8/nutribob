"""NutriBob — testi (HTML) e tastiere Telegram. Nessun I/O qui dentro."""

from datetime import date, datetime, timedelta
from html import escape
from typing import Optional

from telegram import InlineKeyboardButton as Btn
from telegram import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from nutrition import MEAL_LABELS, MEALS, display_name, meal_for_time

# ── OBIETTIVI (il metodo della v1: kcal = peso × moltiplicatore) ─────────────

GOAL_MULTIPLIER = {"cut": 28, "main": 33, "bulk": 38}
GOAL_LABELS = {"cut": "✂️ Cut (dimagrire)", "main": "⚖️ Mantenimento", "bulk": "💪 Bulk (massa)"}
GOAL_DESC = {
    "cut": "deficit calorico — brucia più di quello che mangi",
    "main": "mangiare quanto consumi — peso stabile",
    "bulk": "surplus calorico — costruisci massa muscolare",
}
# Macro: proteine e grassi in g per kg di peso, i carboidrati coprono il resto
PROTEIN_G_PER_KG = {"cut": 2.0, "main": 1.8, "bulk": 1.8}
FAT_G_PER_KG = {"cut": 0.8, "main": 0.9, "bulk": 1.0}


def targets(weight_kg: Optional[float], goal: str = "main") -> dict:
    if not weight_kg:
        return {"kcal": 2000, "p": 100, "c": 250, "f": 65}
    kcal = round(weight_kg * GOAL_MULTIPLIER.get(goal, 33))
    p = round(weight_kg * PROTEIN_G_PER_KG.get(goal, 1.8))
    f = round(weight_kg * FAT_G_PER_KG.get(goal, 0.9))
    c = max(0, round((kcal - p * 4 - f * 9) / 4))
    return {"kcal": kcal, "p": p, "c": c, "f": f}


# ── PICCOLI COMPONENTI ───────────────────────────────────────────────────────

_FOOD_EMOJI = {
    "pasta": "🍝", "spaghetti": "🍝", "pizza": "🍕", "riso": "🍚", "risotto": "🍚",
    "insalata": "🥗", "pollo": "🍗", "tacchino": "🍗", "manzo": "🥩", "carne": "🥩",
    "bistecca": "🥩", "pesce": "🐟", "salmone": "🐟", "tonno": "🐟", "gamberi": "🦐",
    "uov": "🥚", "latte": "🥛", "yogurt": "🥛", "formaggio": "🧀", "mozzarella": "🧀",
    "parmigiano": "🧀", "mela": "🍎", "banana": "🍌", "arancia": "🍊", "fragol": "🍓",
    "uva": "🍇", "pera": "🍐", "kiwi": "🥝", "avocado": "🥑", "pomodor": "🍅",
    "patat": "🥔", "carot": "🥕", "broccol": "🥦", "gelato": "🍨", "cioccolat": "🍫",
    "torta": "🍰", "biscott": "🍪", "cornetto": "🥐", "croissant": "🥐", "pane": "🍞",
    "panino": "🥪", "piadina": "🌯", "caff": "☕", "cappuccino": "☕", "te ": "🍵",
    "birra": "🍺", "vino": "🍷", "spritz": "🍹", "acqua": "💧", "hamburger": "🍔",
    "sushi": "🍣", "kebab": "🌯", "proteine": "💪", "proteina": "💪", "olio": "🫒",
    "noci": "🥜", "mandorle": "🥜", "avena": "🌾", "frullat": "🥤", "succo": "🧃",
}


def food_emoji(name: str) -> str:
    n = name.lower() + " "
    for k, e in _FOOD_EMOJI.items():
        if k in n:
            return e
    return "🍽"


def bar(value: float, target: float, width: int = 10) -> str:
    pct = value / target if target else 0
    filled = round(min(pct, 1.0) * width)
    color = "🟥" if pct > 1.1 else "🟨" if pct >= 0.9 else "🟩"
    return color * filled + "⬜" * (width - filled)


def thin_bar(value: float, target: float, width: int = 12) -> str:
    pct = value / target if target else 0
    filled = round(min(pct, 1.0) * width)
    return "▰" * filled + "▱" * (width - filled)


def sparkline(values: list[float]) -> str:
    chars = "▁▂▃▄▅▆▇█"
    if not values:
        return ""
    lo, hi = min(values), max(values)
    if hi == lo:
        return chars[3] * len(values)
    return "".join(chars[round((v - lo) / (hi - lo) * 7)] for v in values)


def _n(x: Optional[float]) -> str:
    return "–" if x is None else str(round(x))


def macro_line(p, c, f) -> str:
    return f"P {_n(p)}g · C {_n(c)}g · G {_n(f)}g"


def day_label(offset: int) -> str:
    d = date.today() - timedelta(days=offset)
    if offset == 0:
        return f"oggi {d:%d/%m}"
    if offset == 1:
        return f"ieri {d:%d/%m}"
    return f"{_DAY_NAMES[d.weekday()]} {d:%d/%m}"


_DAY_NAMES = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]


# ── TASTIERA FISSA (in basso) ────────────────────────────────────────────────

MENU_DIARY = "📖 Diario"
MENU_WEEK = "📊 Settimana"
MENU_WEIGHT = "⚖️ Peso"
MENU_PROFILE = "👤 Profilo"
MENU_SGARRO = "🍕 Sgarro"
MENU_HELP = "❓ Aiuto"


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(MENU_DIARY), KeyboardButton(MENU_WEEK)],
            [KeyboardButton(MENU_WEIGHT), KeyboardButton(MENU_PROFILE)],
            [KeyboardButton(MENU_SGARRO), KeyboardButton(MENU_HELP)],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Es: 200g pasta, 2 uova e una mela",
    )


# ── SCHEDA BOZZA (prima di salvare) ──────────────────────────────────────────
#
# draft = {
#   "id": int, "items": [item...], "unknown": [{text, qty, unit, unit_word, suggestions}],
#   "meal": str, "offset": 0|1 (giorni fa), "view": "card"|"edit"|"alt"|"fix", "sel": int,
# }
# callback_data: "d:<draft_id>:<azione>[:<arg>...]"  (max 64 byte)


def new_draft(draft_id: int, parsed: dict) -> dict:
    return {
        "id": draft_id,
        "items": parsed["items"],
        "unknown": parsed["unknown"],
        "meal": parsed["meal"] or meal_for_time(datetime.now()),
        "offset": 0,
        "view": "card",
        "sel": 0,
    }


def draft_totals(draft: dict) -> dict:
    items = draft["items"]
    return {
        "kcal": sum(i["kcal"] for i in items),
        "p": sum(i["p"] or 0 for i in items),
        "c": sum(i["c"] or 0 for i in items),
        "f": sum(i["f"] or 0 for i in items),
    }


def render_draft(draft: dict, day_tot: dict, tgt: dict) -> tuple[str, InlineKeyboardMarkup]:
    """day_tot = totali già salvati per il giorno della bozza."""
    d = draft
    cb = lambda *a: "d:" + ":".join(str(x) for x in (d["id"], *a))  # noqa: E731
    sel = d["sel"] if d["view"] in ("edit", "alt") else None

    lines = [f"<b>{MEAL_LABELS[d['meal']]}</b> · {day_label(d['offset'])}", ""]
    for i, it in enumerate(d["items"]):
        name = escape(display_name(it["key"]))
        pointer = "👉 " if i == sel else ""
        fuzzy = " <i>(?)</i>" if it.get("fuzzy") else ""
        lines.append(f"{pointer}{food_emoji(it['key'])} <b>{name}</b>{fuzzy} — {escape(it['desc'])}")
        lines.append(f"      <code>{it['kcal']:>4} kcal</code>  {macro_line(it['p'], it['c'], it['f'])}")
    for u in d["unknown"]:
        lines.append(f"❓ <i>{escape(u['text'])}</i> — non trovato")

    tot = draft_totals(d)
    if d["items"]:
        after = day_tot["kcal"] + tot["kcal"]
        lines += [
            "",
            f"🔥 <b>{tot['kcal']} kcal</b> · {macro_line(tot['p'], tot['c'], tot['f'])}",
            f"{bar(after, tgt['kcal'])}",
            f"<i>Dopo il salvataggio: {after}/{tgt['kcal']} kcal ({round(after / tgt['kcal'] * 100)}%)</i>",
        ]
    else:
        lines += ["", "<i>Nessun alimento da salvare.</i>"]

    rows: list[list[Btn]] = []

    if d["view"] == "edit":
        it = d["items"][sel]
        lines += ["", "✏️ <i>Usa i tasti o scrivi la quantità (es. <code>150</code>, <code>150g</code>, <code>2</code>)</i>"]
        if it["unit"] == "g":
            rows.append([Btn(t, callback_data=cb("q", sel, t)) for t in ("-50", "-10", "+10", "+50")])
        else:
            rows.append([Btn(t, callback_data=cb("q", sel, t)) for t in ("-1", "-½", "+½", "+1")])
            rows.append([Btn("⚖️ Passa a grammi", callback_data=cb("tog", sel))])
        rows.append([
            Btn("🔁 Era un'altra cosa", callback_data=cb("alt", sel)),
            Btn("🗑 Rimuovi", callback_data=cb("rm", sel)),
        ])
        rows.append([Btn("✅ Fatto", callback_data=cb("back"))])

    elif d["view"] == "alt":
        it = d["items"][sel]
        lines += ["", f"🔁 <i>Cosa intendevi al posto di «{escape(display_name(it['key']))}»?</i>"]
        for k, key in enumerate(d.get("alts", [])):
            rows.append([Btn(f"{food_emoji(key)} {display_name(key)}", callback_data=cb("set", sel, k))])
        rows.append([Btn("⬅️ Indietro", callback_data=cb("e", sel))])

    elif d["view"] == "fix":
        u = d["unknown"][d["sel"]]
        lines += ["", f"❓ <i>«{escape(u['text'])}» non è nel database. Intendevi…</i>"]
        for k, key in enumerate(u["suggestions"]):
            rows.append([Btn(f"{food_emoji(key)} {display_name(key)}", callback_data=cb("fs", d["sel"], k))])
        rows.append([
            Btn("🗑 Ignora", callback_data=cb("fd", d["sel"])),
            Btn("⬅️ Indietro", callback_data=cb("back")),
        ])

    else:  # card
        for i, it in enumerate(d["items"]):
            label = f"✏️ {display_name(it['key'])} · {it['kcal']} kcal"
            rows.append([Btn(label[:60], callback_data=cb("e", i))])
        for j, u in enumerate(d["unknown"]):
            rows.append([Btn(f"❓ {u['text']} → scegli"[:60], callback_data=cb("fx", j))])
        rows.append([
            Btn(f"🕐 {MEAL_LABELS[d['meal']]}", callback_data=cb("meal")),
            Btn("📅 " + ("Ieri" if d["offset"] else "Oggi"), callback_data=cb("day")),
        ])
        save = [Btn("❌ Annulla", callback_data=cb("no"))]
        if d["items"]:
            save.insert(0, Btn(f"✅ Salva ({len(d['items'])})", callback_data=cb("ok")))
        rows.append(save)

    return "\n".join(lines), InlineKeyboardMarkup(rows)


# ── DIARIO DEL GIORNO ────────────────────────────────────────────────────────


def _entry_meal(e: dict) -> str:
    if e.get("meal") in MEALS:
        return e["meal"]
    return meal_for_time(datetime.fromisoformat(e["created_at"]))


def render_diary(rows: list[dict], offset: int, tgt: dict, delete_mode: bool = False
                 ) -> tuple[str, InlineKeyboardMarkup]:
    lines = [f"📖 <b>Diario — {day_label(offset)}</b>"]
    kb: list[list[Btn]] = []

    if not rows:
        lines += ["", "📭 Nessuna voce. Scrivimi cosa hai mangiato!"]
    else:
        by_meal: dict[str, list[dict]] = {m: [] for m in MEALS}
        for e in rows:
            by_meal[_entry_meal(e)].append(e)
        for meal in MEALS:
            entries = by_meal[meal]
            if not entries:
                continue
            kcal = sum(e["calories"] for e in entries)
            lines += ["", f"<b>{MEAL_LABELS[meal]}</b> · {kcal} kcal"]
            for e in entries:
                lines.append(
                    f"  {food_emoji(e['food'])} {escape(e['food'])} — {e['calories']} kcal"
                    f"  <i>{escape(e['quantity_desc'] or '')}</i>"
                )
                if delete_mode:
                    kb.append([Btn(f"🗑 {e['food']} ({e['calories']} kcal)"[:60],
                                   callback_data=f"dx:{offset}:{e['id']}")])

        tot = {
            "kcal": sum(e["calories"] for e in rows),
            "p": sum(e["p"] for e in rows),
            "c": sum(e["c"] for e in rows),
            "f": sum(e["f"] for e in rows),
        }
        pct = round(tot["kcal"] / tgt["kcal"] * 100)
        lines += [
            "",
            f"🔥 <b>{tot['kcal']}/{tgt['kcal']} kcal</b> ({pct}%)",
            bar(tot["kcal"], tgt["kcal"]),
            "",
            f"<code>💪 P {thin_bar(tot['p'], tgt['p'])} {round(tot['p']):>3}/{tgt['p']}g</code>",
            f"<code>🍞 C {thin_bar(tot['c'], tgt['c'])} {round(tot['c']):>3}/{tgt['c']}g</code>",
            f"<code>🥑 G {thin_bar(tot['f'], tgt['f'])} {round(tot['f']):>3}/{tgt['f']}g</code>",
        ]
        left = tgt["kcal"] - tot["kcal"]
        if offset == 0:
            if left > 0:
                p_left = tgt["p"] - tot["p"]
                hint = f" — di cui ancora ~{round(p_left)}g di proteine" if p_left > 15 else ""
                lines.append(f"\n💡 <i>Ti restano {left} kcal{hint}.</i>")
            elif tot["kcal"] > tgt["kcal"] * 1.1:
                lines.append(f"\n⚠️ <i>Sei {-left} kcal sopra l'obiettivo.</i>")

    nav = [Btn("◀️", callback_data=f"dy:{offset + 1}")]
    if offset > 0:
        nav.append(Btn("Oggi", callback_data="dy:0"))
        nav.append(Btn("▶️", callback_data=f"dy:{offset - 1}"))
    if rows:
        nav.append(Btn("✅ Fine" if delete_mode else "🗑 Modifica",
                       callback_data=f"dy:{offset}" if delete_mode else f"dd:{offset}"))
    kb.append(nav)
    return "\n".join(lines), InlineKeyboardMarkup(kb)


# ── SETTIMANA ────────────────────────────────────────────────────────────────


def render_week(rows: list[dict], tgt: dict) -> str:
    if not rows:
        return "📭 Nessun dato negli ultimi 7 giorni."
    by_day = {r["day"]: r for r in rows}
    lines = ["📊 <b>Ultimi 7 giorni</b>", ""]
    values = []
    for back in range(6, -1, -1):
        d = date.today() - timedelta(days=back)
        r = by_day.get(d.isoformat())
        kcal = r["kcal"] if r else 0
        values.append(kcal)
        name = _DAY_NAMES[d.weekday()][:3].capitalize()
        if r:
            lines.append(f"<code>{name} {d:%d/%m} {thin_bar(kcal, tgt['kcal'], 8)} {kcal:>4}</code>")
        else:
            lines.append(f"<code>{name} {d:%d/%m} {'·' * 8}    –</code>")
    n = len(rows)
    avg = round(sum(r["kcal"] for r in rows) / n)
    lines += [
        "",
        f"📈 Media: <b>{avg} kcal</b> su {tgt['kcal']} ({n} {'giorno' if n == 1 else 'giorni'} registrati)",
        f"⌀ {macro_line(sum(r['p'] for r in rows) / n, sum(r['c'] for r in rows) / n, sum(r['f'] for r in rows) / n)}",
        f"<code>{sparkline(values)}</code>",
    ]
    return "\n".join(lines)


# ── PESO ─────────────────────────────────────────────────────────────────────


def _kg(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def render_weight(rows: list[tuple[str, float]]) -> str:
    if not rows:
        return "📭 Nessuna misurazione. Scrivi ad esempio <code>/peso 75.4</code>"
    ordered = list(reversed(rows))
    w = [float(x) for _, x in ordered]
    delta = w[-1] - w[0]
    trend = "↘️" if delta < 0 else "↗️" if delta > 0 else "➡️"
    lines = [
        f"⚖️ <b>Peso attuale: {_kg(w[-1])} kg</b>",
        f"{trend} {delta:+.1f} kg in {len(w)} misurazioni".replace(".", ","),
        f"📉 min {_kg(min(w))} · max {_kg(max(w))} kg",
        "",
        f"<code>{sparkline(w)}</code>",
        "",
    ]
    for ts, x in ordered[-7:]:
        lines.append(f"<code>{datetime.fromisoformat(ts):%d/%m}  {_kg(float(x))} kg</code>")
    return "\n".join(lines)


def goal_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [Btn("✂️ Cut — perdere peso", callback_data="goal:cut")],
        [Btn("⚖️ Mantenimento", callback_data="goal:main")],
        [Btn("💪 Bulk — aumentare massa", callback_data="goal:bulk")],
    ])


def welcome_text(weight: Optional[float], goal: str) -> str:
    t = targets(weight, goal)
    profile = (
        f"⚖️ <b>{_kg(weight)} kg</b> · {GOAL_LABELS.get(goal, goal)}\n"
        f"🎯 <b>{t['kcal']} kcal</b> · P {t['p']}g · C {t['c']}g · G {t['f']}g\n\n"
        if weight else ""
    )
    return (
        "👋 Sono <b>NutriBob</b>, il tuo diario alimentare.\n\n"
        + profile
        + "<b>Scrivimi cosa hai mangiato, anche più cose insieme:</b>\n"
        "• <code>200g pasta al pomodoro, 2 uova e un'insalata</code>\n"
        "• <code>a colazione yogurt greco 170g + 30g avena + banana</code>\n"
        "• <code>pollo 150, riso 80g e olio 10g</code>\n"
        "• <code>pane 2 fette e un etto di prosciutto cotto</code>\n\n"
        "La quantità può stare prima o dopo il cibo. Prima di salvare puoi "
        "correggere ogni voce dalla scheda.\n\n"
        "<b>Comandi</b>\n"
        "/oggi — diario di oggi · /ieri — diario di ieri\n"
        "/settimana — ultimi 7 giorni\n"
        "/peso 75.4 — registra il peso · /profilo — obiettivo\n"
        "/sgarro 450 pizza — kcal libere\n"
        "/cancella — elimina l'ultima voce · /reset — svuota oggi\n"
        "/tabella — unità di misura · /consigli — alimenti consigliati"
    )


# ── AZIONI SULLA BOZZA (pure: modificano il dict, ritornano un esito) ────────

_STEP_PCS = {"-1": -1, "-½": -0.5, "+½": 0.5, "+1": 1}


def set_quantity(item: dict, qty: float, unit: Optional[str] = None) -> None:
    from nutrition import recompute
    if unit:
        item["unit"] = unit
        if unit == "g":
            item["unit_word"] = None
    item["qty"] = max(qty, 1 if item["unit"] == "g" else 0.5)
    recompute(item)


def draft_action(draft: dict, act: str, args: list[str]) -> Optional[str]:
    """Applica un tasto alla bozza. Ritorna 'save', 'cancel' oppure None (ridisegna)."""
    from nutrition import build_item, suggest

    items, unknown = draft["items"], draft["unknown"]
    idx = int(args[0]) if args and args[0].isdigit() else 0

    if act == "ok":
        return "save"
    if act == "no":
        return "cancel"
    if act == "back":
        draft["view"] = "card"
    elif act == "meal":
        draft["meal"] = MEALS[(MEALS.index(draft["meal"]) + 1) % len(MEALS)]
    elif act == "day":
        draft["offset"] = 0 if draft["offset"] else 1
    elif act == "e" and idx < len(items):
        draft["view"], draft["sel"] = "edit", idx
    elif act == "q" and idx < len(items):
        it, step = items[idx], args[1]
        if it["unit"] == "g":
            set_quantity(it, it["qty"] + int(step))
        else:
            set_quantity(it, it["qty"] + _STEP_PCS.get(step, 0))
    elif act == "tog" and idx < len(items):
        it = items[idx]
        set_quantity(it, round(it["grams"]), unit="g")
    elif act == "rm" and idx < len(items):
        items.pop(idx)
        draft["view"] = "card"
    elif act == "alt" and idx < len(items):
        it = items[idx]
        draft["alts"] = suggest(it.get("raw") or it["key"], n=6, exclude=it["key"])
        draft["view"], draft["sel"] = "alt", idx
    elif act == "set" and idx < len(items):
        alts = draft.get("alts", [])
        k = int(args[1])
        if k < len(alts):
            old = items[idx]
            items[idx] = build_item(alts[k], old["qty"], old["unit"], old.get("unit_word"),
                                    raw=old.get("raw", ""))
        draft["view"] = "edit"
    elif act == "fx" and idx < len(unknown):
        draft["view"], draft["sel"] = "fix", idx
    elif act == "fs" and idx < len(unknown):
        u, k = unknown[idx], int(args[1])
        if k < len(u["suggestions"]):
            items.append(build_item(u["suggestions"][k], u["qty"], u["unit"], u.get("unit_word"),
                                    raw=u["text"]))
            unknown.pop(idx)
        draft["view"] = "card"
    elif act == "fd" and idx < len(unknown):
        unknown.pop(idx)
        draft["view"] = "card"
    return None
