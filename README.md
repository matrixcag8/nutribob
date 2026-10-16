# NutriBob v2 — bot di prova

Diario alimentare su Telegram: scrivi cosa hai mangiato (anche più cibi in una frase,
con la quantità prima o dopo) e il bot calcola kcal e macro con una scheda modificabile.

```
a pranzo 200g pasta al pomodoro, pollo 150 e 2 uova con olio 10g
```

## Avvio in locale

1. Crea il bot su [@BotFather](https://t.me/BotFather): `/newbot` → copia il token.
2. Copia `.env.example` in `.env` e incolla il token:
   ```
   cp .env.example .env
   ```
3. Installa e avvia:
   ```
   python3.11 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ./start.sh
   ```
4. Apri il bot su Telegram e scrivi `/start`.

> Un token può essere usato da **un solo processo alla volta** in polling:
> se avvii il bot in locale, fermalo su Render (e viceversa).

## Test

```
.venv/bin/pip install pytest
.venv/bin/python -m pytest -q
```

## Struttura

| File | Cosa contiene |
|---|---|
| `foods.py` | database alimenti: kcal/100g, porzioni, unità, macro |
| `nutrition.py` | parsing del testo libero e calcoli (nessuna dipendenza da Telegram) |
| `db.py` | SQLite (`diary.db`), con migrazioni compatibili con la v1 |
| `ui.py` | testi HTML, tastiere, scheda bozza, obiettivi kcal/macro |
| `bot.py` | handler Telegram |
| `texts.py` | testi statici di `/tabella` e `/consigli` |

## Deploy su Render

`render.yaml` crea un *worker* con disco persistente. Imposta `BOT_TOKEN` nella
dashboard di Render — **mai** nel codice o in file committati.
