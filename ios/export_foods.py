"""Esporta le tabelle di foods.py per le app iOS (Grillo/foods.json) e Android (assets).

Uso: ../.venv/bin/python export_foods.py  (dalla cartella ios/)
"""

import json
import sys
from pathlib import Path

here = Path(__file__).parent
sys.path.insert(0, str(here.parent))
from foods import FOODS, MACROS  # noqa: E402

# foods.py ha "orzo" due volte e vince il caffè d'orzo (5 kcal), che non combacia coi macro del cereale
FOODS["orzo"] = (354, 80, "1 porzione secco")

# micronutrienti per 100 g da usda_micros.py (assenti per i piatti composti)
MICROS = json.loads((here / "micros.json").read_text())

out = []
for name, (kcal, portion, label) in sorted(FOODS.items()):
    p, c, f = MACROS.get(name, (None, None, None))
    out.append({"name": name, "kcal": kcal, "protein": p, "carbs": c, "fat": f,
                "portion": portion, "portionLabel": label, "micros": MICROS.get(name)})

assert all(f["kcal"] >= 0 and f["portion"] > 0 for f in out)
for dest in (here / "Grillo", here.parent / "android" / "app" / "src" / "main" / "assets"):
    (dest / "foods.json").write_text(json.dumps(out, ensure_ascii=False, indent=0))
print(f"{len(out)} alimenti, {sum(f['protein'] is None for f in out)} senza macro")
