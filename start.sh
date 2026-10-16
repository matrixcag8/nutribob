#!/bin/bash
# Avvia NutriBob localmente con il token dal file .env

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Carica variabili da .env se esiste
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

if [ -z "$BOT_TOKEN" ]; then
    echo "Errore: BOT_TOKEN non impostato. Crea un file .env con BOT_TOKEN=il_tuo_token"
    exit 1
fi

# Attiva il virtualenv se esiste
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

echo "Avvio NutriBob..."
exec python bot.py
