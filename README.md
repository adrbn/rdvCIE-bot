rdvCIE-Bot

Un bot Telegram che controlla i posti disponibili per la Carta d’Identità Elettronica su [prenotazionicie.interno.gov.it](https://www.prenotazionicie.interno.gov.it) e ti avvisa non appena viene individuata una data.

---

## 📋 Funzionalità

- **/check** : esegue subito un controllo e restituisce i prossimi slot liberi.
- **/watch** : avvia una sorveglianza in background ogni 5 minuti e notifica solo i **nuovi** slot.
- **/unwatch** : interrompe la sorveglianza continua.

---

## 🚀 Prerequisiti

- Python **≥ 3.9**
- [Playwright](https://playwright.dev/python/) (Chromium)
- Un bot Telegram (token da ottenere tramite [@BotFather](https://t.me/BotFather))
- `chat_id` Telegram (ID del tuo account o del gruppo)

---

## ⚙️ Installazione

1. **Clona il repository**

   ```bash
   git clone https://github.com/adrbn/rdvCIE-bot.git
   cd rdv-cie-bot
   ```

2. **Crea e attiva un ambiente virtuale**

   ```bash
   python -m venv .venv
   source .venv/bin/activate    # Linux/macOS
   .venv\Scripts\activate     # Windows
   ```

3. **Installa le dipendenze**

   ```bash
   pip install --upgrade pip
   pip install playwright python-telegram-bot requests
   playwright install chromium
   ```

4. **Configura le variabili d’ambiente**

   ```bash
   export TELEGRAM_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
   export TELEGRAM_CHAT_ID="987654321"
   ```

   > Su PowerShell (Windows):
   >
   > ```powershell
   > $Env:TELEGRAM_TOKEN="…"
   > $Env:TELEGRAM_CHAT_ID="…"
   > ```

---

## ▶️ Esecuzione in locale

```bash
python check_rdv_bot.py
```

Apri Telegram e invia:

- `/check`   → controllo istantaneo
- `/watch`   → attiva la sorveglianza ogni 5 minuti
- `/unwatch` → disattiva la sorveglianza

---

## 🕒 Deploy con GitHub Actions

Per eseguire il controllo ogni 5 minuti via Actions, crea `.github/workflows/check-rdv.yml`:

```yaml
name: RDV CIE Scheduler

on:
  schedule:
    - cron: '*/5 * * * *'   # ogni 5 minuti
  workflow_dispatch:       # permette l’avvio manuale

jobs:
  check-every-5min:
    runs-on: ubuntu-latest
    timeout-minutes: 6     # massimo 6 ore per job
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.x'

      - name: Install dependencies
        run: |
          pip install --upgrade pip
          pip install playwright requests
          playwright install chromium

      - name: Run RDV-Bot
        env:
          TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: |
          python check_rdv_bot.py
```

1. Aggiungi i secret in **Impostazioni → Segreti e variabili → Azioni**:
   - `TELEGRAM_TOKEN`
   - `TELEGRAM_CHAT_ID`
2. Effettua il push: il workflow partirà al deploy e poi ogni 5 minuti.

> ⚠️ GitHub Actions può eseguire un job continuativo fino a **6 ore**. Per un bot *always-on* illimitato, valuta PaaS come Replit, Deta, Railway o un runner self-hosted.

---

## 📄 Licenza

MIT © adrbn

