"""Test del parser — esegui con:  python -m pytest -q  (oppure  python test_nutrition.py)"""

from nutrition import parse_item, parse_message, split_items


def keys(text):
    return [(i["key"], round(i["grams"])) for i in parse_message(text)["items"]]


# ── split ────────────────────────────────────────────────────────────────────

def test_split_separatori():
    assert split_items("pasta, pollo; mela + pane") == ["pasta", "pollo", "mela", "pane"]
    assert split_items("pasta e pollo con insalata") == ["pasta", "pollo", "insalata"]


def test_split_piatti_composti_non_spezzati():
    assert split_items("pasta e fagioli e una mela") == ["pasta e fagioli", "una mela"]
    assert split_items("cappuccino con zucchero e 2 cornetti") == ["cappuccino con zucchero", "2 cornetti"]


# ── quantità prima o dopo ────────────────────────────────────────────────────

def test_grammi_prima_e_dopo():
    for t in ("200g pasta", "pasta 200g", "pasta 200 g", "200 grammi di pasta", "pasta da 200g"):
        p = parse_item(t)
        assert (p.food, p.qty, p.unit) == ("pasta", 200, "g"), t


def test_numero_nudo():
    assert parse_item("pollo 150") == parse_item("150 pollo")
    assert parse_item("pollo 150").unit == "g"
    p = parse_item("uova 2")
    assert (p.food, p.qty, p.unit) == ("uova", 2, "pcs")


def test_moltiplicatore_e_parole():
    assert parse_item("uova x2").qty == 2
    assert parse_item("2x uova").qty == 2
    assert parse_item("due mele").qty == 2
    assert parse_item("mezzo panino").qty == 0.5
    assert parse_item("1/2 avocado").qty == 0.5


def test_unita():
    assert parse_item("un etto di prosciutto").qty == 100
    assert parse_item("mezzo litro di latte").qty == 500
    assert parse_item("una tazza di latte").qty == 240
    p = parse_item("pane 2 fette")
    assert (p.food, p.qty, p.unit, p.unit_word) == ("pane", 2, "pcs", "fette")


# ── frasi complete ───────────────────────────────────────────────────────────

def test_frase_completa():
    r = parse_message("a pranzo 200g pasta al pomodoro, 2 uova e un'insalata con olio 10g")
    assert r["meal"] == "pranzo"
    assert [i["key"] for i in r["items"]] == ["pasta al pomodoro", "uova", "insalata", "olio di oliva"]
    assert not r["unknown"]


def test_colazione_con_plus():
    r = parse_message("colazione: yogurt greco 170g + 30 g avena + banana")
    assert r["meal"] == "colazione"
    assert keys("yogurt greco 170g + 30 g avena") == [("yogurt greco", 170), ("avena", 30)]


def test_pizza_fetta_override():
    assert keys("una fetta di pizza") == [("pizza", 140)]


def test_sconosciuto_con_suggerimenti():
    r = parse_message("200g blablabla")
    assert not r["items"] and r["unknown"][0]["text"] == "blablabla"


def test_errore_battitura_fuzzy():
    it = parse_message("200g salmne")["items"][0]
    assert it["key"] == "salmone" and it["fuzzy"]


if __name__ == "__main__":
    import sys
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print("✓", name)
            except AssertionError as e:
                fails += 1
                print("✗", name, e)
    sys.exit(1 if fails else 0)
