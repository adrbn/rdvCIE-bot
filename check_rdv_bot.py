import asyncio
import os
import re
import requests

from playwright.async_api import async_playwright
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# ————— CONFIG —————
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]

DUMMY = {
    "motivo_value":   "1",               # 1 = Primo Documento
    "nome":            "Mario",
    "cognome":         "Rossi",
    "codice_fiscale":  "RSSMRA80A01H501X",
    "comune":          "ROMA"
}

START_URL = (
    "https://www.prenotazionicie.interno.gov.it"
    "/cittadino/n/sc/wizardAppuntamentoCittadino/home"
)

# ————— SCRAPING —————
async def check_dispo() -> list[tuple[str,str,str]]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page    = await browser.new_page()

        # STEP 1 — remplir le formulaire initial
        await page.goto(START_URL)
        await page.wait_for_load_state("networkidle", timeout=5000)
        await page.wait_for_selector("#selectTipoDocumento", timeout=5000)
        await page.evaluate(f"""
            const sel = document.getElementById('selectTipoDocumento');
            sel.value = '{DUMMY['motivo_value']}';
            sel.dispatchEvent(new Event('input', {{ bubbles: true }}));
            sel.dispatchEvent(new Event('change', {{ bubbles: true }}));
        """)
        await page.fill("input[name=nome]", DUMMY["nome"], timeout=3000)
        await page.fill("input[name=cognome]", DUMMY["cognome"], timeout=3000)
        await page.fill("input[name=codiceFiscale]", DUMMY["codice_fiscale"], timeout=3000)
        await page.evaluate("""document.querySelector("button[value='continua']").removeAttribute('disabled');""")
        await page.click("button[value='continua']", timeout=5000)

        # STEP 2 — choisir le Comune
        await page.wait_for_url("**/sceltaComune**", timeout=5000)
        await page.wait_for_load_state("networkidle", timeout=5000)
        # enlever overlay/modal
        await page.evaluate("""document.querySelectorAll('.black-overlay, #messageModalBox').forEach(e=>e.remove());""")
        await page.click("#comuneResidenzaInput", timeout=3000)
        await page.type("#comuneResidenzaInput", DUMMY["comune"], delay=100, timeout=3000)
        await page.wait_for_selector(
            "comune-typeahead ul.typeahead.dropdown-menu li:has-text('ROMA')",
            timeout=3000
        )
        await page.click(
            "comune-typeahead ul.typeahead.dropdown-menu li:has-text('ROMA')",
            timeout=3000
        )
        await page.evaluate("""document.querySelector("button[value='continua']").removeAttribute('disabled');""")
        await page.click("button[value='continua']", timeout=5000)

        # STEP 3 — extraction des dispo
        await page.wait_for_selector("label.sr-only[for^='sede-']", timeout=5000)
        dispo = []
        for lbl in await page.query_selector_all("label.sr-only[for^='sede-']"):
            tr    = await lbl.evaluate_handle("e=>e.closest('tr')")
            cells = await tr.query_selector_all("td")
            texts = [await c.inner_text() for c in cells][:3]
            if len(texts)==3:
                sede, indirizzo, date = (t.strip() for t in texts)
                dispo.append((sede, indirizzo, date))
        await browser.close()
        return dispo

# ————— HANDLERS BOT —————
async def cmd_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/check: vérifie et renvoie immédiatement."""
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id, "⏳ Je vérifie…")
    try:
        results = await check_dispo()
        # ne garder que ceux qui contiennent une date dd/mm/yyyy
        filt = [(s,i,d) for s,i,d in results if re.search(r"\d{2}/\d{2}/\d{4}", d)]
        if not filt:
            await context.bot.send_message(chat_id, "❌ Aucun créneau dispo.")
        else:
            lines = [f"- {s} | {i} | {d}" for s,i,d in filt]
            text  = "🔔 Créneaux trouvés :\n\n" + "\n\n".join(lines)
            await context.bot.send_message(chat_id, text)
    except Exception as e:
        await context.bot.send_message(chat_id, f"❌ Erreur : {e}")

async def alarm(context: ContextTypes.DEFAULT_TYPE):
    """Job /watch: notifie uniquement les nouveaux créneaux."""
    job     = context.job
    chat_id = job.chat_id
    try:
        results = await check_dispo()
        filt = [(s,i,d) for s,i,d in results if re.search(r"\d{2}/\d{2}/\d{4}", d)]
        prev = job.data.setdefault("sent", set())
        new  = []
        for entry in filt:
            key = "|".join(entry)
            if key not in prev:
                new.append(entry)
                prev.add(key)
        if new:
            lines = [f"- {s} | {i} | {d}" for s,i,d in new]
            text  = "🔔 Nouveaux créneaux détectés :\n\n" + "\n\n".join(lines)
            await context.bot.send_message(chat_id, text)
    except Exception as e:
        await context.bot.send_message(chat_id, f"❌ Erreur veille : {e}")

async def cmd_watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/watch: démarre la surveillance toutes les 5 min."""
    chat_id = update.effective_chat.id
    data    = context.bot_data.setdefault(chat_id, {})
    if "watch_job" in data:
        await update.message.reply_text("🕵️ Vous êtes déjà en mode /watch.")
        return
    # planifier job répétitif
    job = context.job_queue.run_repeating(
        alarm,
        interval=300,    # toutes les 5 min
        first=0,
        chat_id=chat_id,
        name=str(chat_id),
        data={"sent": set()}
    )
    data["watch_job"] = job
    await update.message.reply_text("✅ Surveillance activée : je vous notifie sur nouveau RDV.")

async def cmd_unwatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/unwatch: arrête la surveillance."""
    chat_id = update.effective_chat.id
    data    = context.bot_data.get(chat_id, {})
    job     = data.get("watch_job")
    if not job:
        await update.message.reply_text("❌ Vous n'êtes pas en mode /watch.")
    else:
        job.schedule_removal()
        data.pop("watch_job")
        await update.message.reply_text("🛑 Mode /watch désactivé.")

# ————— LANCEMENT —————
async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("check",   cmd_check))
    app.add_handler(CommandHandler("watch",   cmd_watch))
    app.add_handler(CommandHandler("unwatch", cmd_unwatch))
    await app.start()
    await app.updater.start_polling()
    await app.idle()

if __name__ == "__main__":
    asyncio.run(main())
