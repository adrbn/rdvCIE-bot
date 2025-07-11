import asyncio
import os
import requests
from playwright.async_api import async_playwright

# ————— CONFIG —————
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text
    })

DUMMY = {
    "motivo": "Primo Documento",      # label exact de l'option
    "nome": "Mario",
    "cognome": "Rossi",
    "codice_fiscale": "RSSMRA80A01H501X",
    "comune": "ROMA"
}

START_URL = "https://www.prenotazionicie.interno.gov.it/cittadino/n/sc/wizardAppuntamentoCittadino/home"

async def check_dispo():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page    = await browser.new_page()

        # ─── STEP 1 ───
        await page.goto(START_URL)
        await page.wait_for_load_state("networkidle", timeout=30000)

        # On attend le select du motif par son id
        await page.wait_for_selector(
            "#selectTipoDocumento",
            state="visible",
            timeout=30000
        )
        # On choisit l'option par son label
        await page.select_option(
            "#selectTipoDocumento",
            label=DUMMY["motivo"]
        )

        # On remplit les autres champs
        await page.fill("input[name=nome]", DUMMY["nome"])
        await page.fill("input[name=cognome]", DUMMY["cognome"])
        await page.fill("input[name=codiceFiscale]", DUMMY["codice_fiscale"])
        await page.click("button:has-text('Continua')")

        # ─── STEP 2 ───
        await page.wait_for_url("**/sceltaComune**", timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=30000)
        await page.wait_for_selector("input[aria-label='Comune']", timeout=30000)
        await page.fill("input[aria-label='Comune']", DUMMY["comune"])
        await page.click("//li[contains(., 'ROMA')]")
        await page.click("button:has-text('Continua')")

        # ─── STEP 3 ───
        await page.wait_for_selector("label.sr-only[for^='sede-']", timeout=30000)
        dispo = []
        for lbl in await page.query_selector_all("label.sr-only[for^='sede-']"):
            parent = await lbl.evaluate_handle("e => e.closest('tr')")
            cells  = await parent.query_selector_all("td")
            texts  = [await c.inner_text() for c in cells]
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
            send_telegram(msg)
    except Exception as e:
        send_telegram(f"❌ Erreur : {e}")

if __name__ == "__main__":
    asyncio.run(main())
