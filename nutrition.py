"""NutriBob — parsing del testo libero e calcolo kcal/macro.

Modulo "puro" (niente Telegram, niente DB) così è facile da testare.

Flusso:
    parse_message("a pranzo 200g pasta, pollo 150 e 2 uova")
      → split_items()  → ["200g pasta", "pollo 150", "2 uova"]
      → parse_item()   → (testo cibo, quantità, unità, parola-porzione)
      → lookup()       → chiave in FOODS
      → build_item()   → dict con grammi, kcal e macro
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from difflib import get_close_matches
from typing import Optional

from foods import FOODS, MACROS, PORTION_OVERRIDES, PORTION_WORDS, UNIT_GRAMS

# ── PASTI ─────────────────────────────────────────────────────────────────────

MEALS = ["colazione", "pranzo", "spuntino", "cena"]
MEAL_LABELS = {
    "colazione": "☕ Colazione",
    "pranzo":    "🍝 Pranzo",
    "spuntino":  "🍎 Spuntino",
    "cena":      "🌙 Cena",
}
# Orario usato quando si registra un pasto su un giorno passato
MEAL_TIMES = {"colazione": "08:00", "pranzo": "13:00", "spuntino": "16:30", "cena": "20:00"}

_MEAL_WORDS = {
    "colazione": "colazione",
    "pranzo": "pranzo",
    "spuntino": "spuntino", "merenda": "spuntino", "snack": "spuntino",
    "cena": "cena",
}


def meal_for_time(dt: datetime) -> str:
    h = dt.hour + dt.minute / 60
    if 5 <= h < 11:
        return "colazione"
    if 11 <= h < 15:
        return "pranzo"
    if 15 <= h < 18.5:
        return "spuntino"
    return "cena"


# ── NORMALIZZAZIONE ──────────────────────────────────────────────────────────


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def normalize(text: str) -> str:
    """minuscolo, apostrofi → spazio (come le chiavi di FOODS), spazi compattati."""
    text = text.lower().replace("’", "'").replace("'", " ")
    return re.sub(r"\s+", " ", text).strip()


# Indice: chiave normalizzata senza accenti → chiave originale
_INDEX: dict[str, str] = {}
for _k in FOODS:
    _INDEX.setdefault(_strip_accents(normalize(_k)), _k)
_KEYS_BY_LEN = sorted(_INDEX, key=len, reverse=True)

# Chiavi che contengono un congiuntivo ("pasta e fagioli", "pizza con prosciutto"):
# non vanno spezzate in due alimenti.
_SOFT_SEP = r"e|ed|con|piu|più|poi|anche"
_JOINED_KEYS = [k for k in _KEYS_BY_LEN if re.search(rf"\s(?:{_SOFT_SEP})\s", k)]


# ── SPLIT IN PIÙ ALIMENTI ────────────────────────────────────────────────────

_PREFIX_RE = re.compile(
    r"^(?:oggi\s+|stamattina\s+|stasera\s+|ieri\s+)?"
    r"(?:ho\s+appena\s+|mi\s+sono\s+|ho\s+)?"
    r"(?:mangiat[oaie]|bevut[oaie]|fatto|pres[oa]|sto\s+mangiando)\s+",
)
_MEAL_RE = re.compile(
    r"\b(?:a|per|al|alla|come|di|x)?\s*(colazione|pranzo|merenda|spuntino|snack|cena)\b\s*:?"
)


def extract_meal(text: str) -> tuple[str, Optional[str]]:
    """'a pranzo pasta e pollo' → ('pasta e pollo', 'pranzo')."""
    m = _MEAL_RE.search(text)
    if not m:
        return text, None
    meal = _MEAL_WORDS[m.group(1)]
    text = (text[: m.start()] + " " + text[m.end():]).strip()
    return re.sub(r"\s+", " ", text), meal


def _food_part(chunk: str) -> str:
    """Solo la parte 'cibo' di un pezzo, senza numeri/unità (per i confronti)."""
    return parse_item(chunk).food


def split_items(text: str) -> list[str]:
    """Divide una frase in alimenti singoli.

    Separatori forti: , ; + a capo
    Separatori deboli: e / ed / con / più / poi — ignorati se uniscono un
    piatto noto ("pasta e fagioli", "cappuccino con zucchero").
    """
    items: list[str] = []
    for chunk in re.split(r"[,;+\n]+", text):
        chunk = chunk.strip()
        if not chunk:
            continue
        pieces = re.split(rf"\s+(?:{_SOFT_SEP})\s+", chunk)
        seps = re.findall(rf"\s+({_SOFT_SEP})\s+", chunk)
        current = pieces[0]
        for sep, nxt in zip(seps, pieces[1:]):
            joined = f"{current} {sep} {nxt}"
            joined_food = _strip_accents(_food_part(joined))
            current_food = _strip_accents(_food_part(current))
            # unisci solo se un piatto noto "scavalca" il separatore
            if any(
                re.search(rf"\b{re.escape(k)}\b", joined_food)
                and not re.search(rf"\b{re.escape(k)}\b", current_food)
                for k in _JOINED_KEYS
            ):
                current = joined
            else:
                items.append(current)
                current = nxt
        items.append(current)
    return [i.strip() for i in items if i.strip()]


# ── QUANTITÀ (prima o dopo il cibo) ──────────────────────────────────────────

_NUM_WORDS: dict[str, float] = {
    "un": 1, "uno": 1, "una": 1,
    "due": 2, "tre": 3, "quattro": 4, "cinque": 5, "sei": 6,
    "sette": 7, "otto": 8, "nove": 9, "dieci": 10, "dodici": 12,
    "mezzo": 0.5, "mezza": 0.5, "meta": 0.5, "metà": 0.5,
}
_NUM = r"(?:\d+(?:[.,]\d+)?|\d+/\d+|" + "|".join(sorted(_NUM_WORDS, key=len, reverse=True)) + r")"

# unità con peso fisso (grammi per unità)
_WEIGHT_UNITS = {
    "kg": 1000, "chili": 1000, "chilo": 1000,
    "hg": 100, "etto": 100, "etti": 100,
    "g": 1, "gr": 1, "grammi": 1, "grammo": 1,
    "l": 1000, "litro": 1000, "litri": 1000,
    "cl": 10, "ml": 1,
}
_WEIGHT_RE = "|".join(sorted(_WEIGHT_UNITS, key=len, reverse=True))
_UNITWORD_RE = "|".join(sorted(set(UNIT_GRAMS) | PORTION_WORDS, key=len, reverse=True))

_FILLER_RE = re.compile(
    r"^(?:(?:di|del|dello|della|dei|degli|delle|da|il|lo|la|i|gli|le|l|circa|tipo)\s+)+"
)
_TRAILING_RE = re.compile(r"\s+(?:circa|tipo|in tutto)$")

# Sotto questa soglia un numero "nudo" è un conteggio (2 uova), sopra sono grammi (pollo 150)
BARE_NUMBER_GRAMS_THRESHOLD = 20


def _to_number(tok: str) -> float:
    tok = tok.strip()
    if tok in _NUM_WORDS:
        return _NUM_WORDS[tok]
    if "/" in tok:
        a, b = tok.split("/")
        return float(a) / float(b) if float(b) else 1.0
    return float(tok.replace(",", "."))


@dataclass
class ParsedItem:
    food: str               # testo del cibo, ripulito
    qty: float              # grammi se unit == 'g', altrimenti numero di porzioni
    unit: str               # 'g' | 'pcs'
    unit_word: Optional[str] = None   # 'fetta', 'piatto'... (solo per 'pcs')


def _cut(text: str, m: re.Match) -> str:
    return (text[: m.start()] + " " + text[m.end():]).strip()


def _clean_food(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = _FILLER_RE.sub("", text)
    text = _TRAILING_RE.sub("", text)
    return text.strip(" .!:-")


def parse_item(raw: str) -> ParsedItem:
    """Estrae la quantità ovunque si trovi nel testo.

    200g pasta · pasta 200g · pasta da 200 g · un etto di prosciutto
    2 uova · uova x2 · 2x uova · pollo 150 · 3 fette di pane · pane 3 fette
    una tazza di latte · mezzo panino · 1/2 pizza
    """
    text = normalize(raw)
    text = _PREFIX_RE.sub("", text)

    # 1) numero (o parola-numero) + unità di peso: "200g", "un etto", "mezzo litro"
    m = re.search(rf"(?:^|\s|da\s)({_NUM})?\s*({_WEIGHT_RE})\b(?=\s|$)", text)
    if m and (m.group(1) or m.group(2) in ("etto", "litro", "chilo")):
        n = _to_number(m.group(1)) if m.group(1) else 1.0
        grams = n * _WEIGHT_UNITS[m.group(2)]
        return ParsedItem(_clean_food(_cut(text, m)), grams, "g")

    # 2) numero + parola-unità: "3 fette", "due cucchiai", "un piatto"
    m = re.search(rf"(?:^|\s)({_NUM})\s+({_UNITWORD_RE})\b", text)
    # 2b) parola-unità senza numero a inizio frase: "tazza di latte"
    if not m:
        m = re.search(rf"^()({_UNITWORD_RE})\s+(?:di|d)\s", text)
    if m:
        n = _to_number(m.group(1)) if m.group(1) else 1.0
        word = m.group(2)
        rest = _clean_food(_cut(text, m))
        if word in UNIT_GRAMS:
            return ParsedItem(rest, n * UNIT_GRAMS[word], "g")
        return ParsedItem(rest, n, "pcs", word)

    # 3) moltiplicatore: "x2", "2x", "×2"
    m = re.search(r"(?:^|\s)(?:[x×]\s*(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s*[x×])(?=\s|$)", text)
    if m:
        n = _to_number(m.group(1) or m.group(2))
        return ParsedItem(_clean_food(_cut(text, m)), n, "pcs")

    # 4) numero nudo, prima o dopo: "2 uova", "pollo 150", "1/2 pizza"
    m = re.search(r"(?:^|\s)(\d+(?:[.,]\d+)?|\d+/\d+)(?=\s|$)", text)
    if m:
        n = _to_number(m.group(1))
        rest = _clean_food(_cut(text, m))
        if n >= BARE_NUMBER_GRAMS_THRESHOLD:
            return ParsedItem(rest, n, "g")
        return ParsedItem(rest, n, "pcs")

    # 5) parola-numero a inizio frase: "una mela", "mezzo panino", "un insalata"
    m = re.match(rf"^({'|'.join(sorted(_NUM_WORDS, key=len, reverse=True))})\s+", text)
    if m:
        return ParsedItem(_clean_food(text[m.end():]), _NUM_WORDS[m.group(1)], "pcs")

    return ParsedItem(_clean_food(text), 1.0, "pcs")


# ── RICERCA NEL DATABASE ─────────────────────────────────────────────────────


def _variants(name: str) -> list[str]:
    """Singolari italiani da un possibile plurale (mele → mela, cornetti → cornetto)."""
    out = [name]
    last = name.split(" ")[-1]
    head = name[: len(name) - len(last)]
    if last.endswith("i"):
        out += [head + last[:-1] + "o", head + last[:-1] + "e", head + last[:-1] + "a"]
    if last.endswith("e"):
        out += [head + last[:-1] + "a", head + last[:-1] + "o"]
    if last.endswith("he"):    # pesche → pesca, albicocche → albicocca
        out += [head + last[:-2] + "a"]
    return out


# Parole generiche → voce più comune in Italia
ALIASES: dict[str, str] = {
    "olio": "olio di oliva",
    "olio evo": "olio di oliva",
    "olio extravergine": "olio di oliva",
}


def lookup(food_text: str) -> tuple[Optional[str], bool]:
    """Ritorna (chiave FOODS, fuzzy?) oppure (None, False)."""
    name = _strip_accents(normalize(food_text))
    if not name:
        return None, False
    if name in ALIASES and ALIASES[name] in FOODS:
        return ALIASES[name], False
    variants = _variants(name)

    # 1. corrispondenza esatta
    for v in variants:
        if v in _INDEX:
            return _INDEX[v], False

    # 2. una chiave (la più lunga) è contenuta come parola intera nel testo
    #    "pasta al pomodoro fresco" → "pasta al pomodoro"
    for k in _KEYS_BY_LEN:
        for v in variants:
            if re.search(rf"\b{re.escape(k)}\b", v):
                return _INDEX[k], False

    # 3. il testo è contenuto come parola intera in una chiave: "bresaola" in "bresaola punta d anca"
    for v in variants:
        hits = [k for k in _KEYS_BY_LEN if re.search(rf"\b{re.escape(v)}\b", k)]
        if hits:
            return _INDEX[min(hits, key=len)], False

    # 4. fuzzy (errori di battitura)
    for v in variants:
        m = get_close_matches(v, list(_INDEX), n=1, cutoff=0.75)
        if m:
            return _INDEX[m[0]], True
    return None, False


def suggest(food_text: str, n: int = 5, exclude: Optional[str] = None) -> list[str]:
    """Alternative plausibili per un testo (per i pulsanti 'intendevi…?')."""
    name = _strip_accents(normalize(food_text))
    out: list[str] = []
    words = [w for w in name.split() if len(w) >= 3]
    # chiavi che condividono una parola (es. 'pasta' → tutte le paste)
    for k in sorted(_INDEX, key=len):
        if any(re.search(rf"\b{re.escape(w[:-1])}", k) for w in words):
            out.append(_INDEX[k])
    for k in get_close_matches(name, list(_INDEX), n=n * 2, cutoff=0.5):
        out.append(_INDEX[k])
    seen, res = set(), []
    for k in out:
        if k != exclude and k not in seen:
            seen.add(k)
            res.append(k)
    # prima i più simili
    res.sort(key=lambda k: -_similarity(name, _strip_accents(k)))
    return res[:n]


def _similarity(a: str, b: str) -> float:
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a, b).ratio()


# ── CALCOLO ──────────────────────────────────────────────────────────────────


def portion_grams(key: str, unit_word: Optional[str]) -> int:
    std_g = FOODS[key][1]
    if unit_word:
        return PORTION_OVERRIDES.get(key, {}).get(unit_word, std_g)
    return std_g


def build_item(key: str, qty: float, unit: str, unit_word: Optional[str] = None,
               fuzzy: bool = False, raw: str = "") -> dict:
    """Crea una voce (dict serializzabile) e ne calcola kcal e macro."""
    item = {
        "key": key, "qty": qty, "unit": unit, "unit_word": unit_word,
        "fuzzy": fuzzy, "raw": raw,
    }
    return recompute(item)


def recompute(item: dict) -> dict:
    key = item["key"]
    kcal_100, std_g, label = FOODS[key]
    if item["unit"] == "g":
        grams = item["qty"]
    else:
        grams = portion_grams(key, item.get("unit_word")) * item["qty"]
    item["grams"] = round(grams, 1)
    item["kcal"] = max(0, round(kcal_100 * grams / 100))
    macros = MACROS.get(key)
    if macros:
        p, c, f = macros
        item["p"], item["c"], item["f"] = (round(x * grams / 100, 1) for x in (p, c, f))
    else:
        item["p"] = item["c"] = item["f"] = None
    item["desc"] = qty_desc(item)
    return item


def _fmt_num(n: float) -> str:
    if n == int(n):
        return str(int(n))
    if n == 0.5:
        return "½"
    return f"{n:g}".replace(".", ",")


def qty_desc(item: dict) -> str:
    if item["unit"] == "g":
        return f"{round(item['grams'])} g"
    key, n, word = item["key"], item["qty"], item.get("unit_word")
    _, std_g, label = FOODS[key]
    g = round(item["grams"])
    if word:
        return f"{_fmt_num(n)} {word} · {g} g"
    if n == 1:
        return f"{label} · {g} g"
    return f"{_fmt_num(n)} × {label} · {g} g"


def display_name(key: str) -> str:
    return key[:1].upper() + key[1:]


# ── API PRINCIPALE ───────────────────────────────────────────────────────────


def parse_message(text: str) -> dict:
    """Testo libero → {'items': [...], 'unknown': [{'text', 'suggestions'}], 'meal': str|None}."""
    text = normalize(text)
    text = _PREFIX_RE.sub("", text)
    text, meal = extract_meal(text)
    items, unknown = [], []
    for raw in split_items(text):
        p = parse_item(raw)
        if not p.food:
            continue
        key, fuzzy = lookup(p.food)
        if key is None:
            unknown.append({"text": p.food, "qty": p.qty, "unit": p.unit,
                            "unit_word": p.unit_word, "suggestions": suggest(p.food)})
            continue
        items.append(build_item(key, p.qty, p.unit, p.unit_word, fuzzy=fuzzy, raw=raw))
    return {"items": items, "unknown": unknown, "meal": meal}


def estimate_calories(raw_text: str) -> Optional[dict]:
    """Compatibilità con la v1 (usata da test_food.py): un solo alimento."""
    res = parse_message(raw_text)
    if not res["items"]:
        return None
    it = res["items"][0]
    return {"food": display_name(it["key"]), "matched": it["key"], "calories": it["kcal"],
            "qty_desc": it["desc"], "protein": it["p"], "carbs": it["c"], "fat": it["f"]}
