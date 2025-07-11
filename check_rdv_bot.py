import asyncio
from playwright.async_api import async_playwright
from telegram import Bot
import os

# ————— CONFIG —————
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

DUMMY = {
    "motivo": "Primo documento",
    "nome": "Mario",
    "cognome": "Rossi",
    "codice_fiscale": "RSSMRA80A01H501X",
    "comune": "ROMA"
}

START_URL = "https://www.prenotazionicie.interno.gov.it/cittadino/n/sc/wizardAppuntamentoCittadino/sceltaComune"
bot = Bot(token=TELEGRAM_TOKEN)

async def check_dispo():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(START_URL)

        # Remplissage du formulaire
        await page.select_option("select[name=motivoAppuntamento]", label=DUMMY["motivo"])
        await page.fill("input[name=nome]", DUMMY["nome"])
        await page.fill("input[name=cognome]", DUMMY["cognome"])
        await page.fill("input[name=codiceFiscale]", DUMMY["codice_fiscale"])
        await page.fill("input[aria-label='Comune']", DUMMY["comune"])
        await page.click("//li[contains(., 'ROMA')]")
        await page.click("button:has-text('Continua')")
        await page.wait_for_selector("label.sr-only[for^='sede-']", timeout=10000)

        dispo = []
        rows = await page.query_selector_all("label.sr-only[for^='sede-']")
        for lbl in rows:
            parent = await lbl.evaluate_handle("e => e.closest('tr')")
            cells = await parent.query_selector_all("td")
            texts = [await c.inner_text() for c in cells]
            dispo.append(texts)

        await browser.close()
        return dispo

async def main():
    try:
        results = await check_dispo()
        if results:
            msg = "🔔 Nouveaux créneaux dispos :\n"
            for sede, indirizzo, date in results:
                msg += f"- {sede} | {indirizzo} | {date}\n"
            bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
    except Exception as e:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"❌ Erreur : {e}")

if __name__ == "__main__":
    asyncio.run(main())
