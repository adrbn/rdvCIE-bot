import asyncio
import os
import requests
from playwright.async_api import async_playwright

# ————— CONFIG —————
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def send_telegram(text: str):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={"chat_id": TELEGRAM_CHAT_ID, "text": text}
    )

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

async def check_dispo():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page    = await browser.new_page()

        # ─── STEP 1 ───
        await page.goto(START_URL)
        await page.wait_for_load_state("networkidle", timeout=15000)

        # injecte la valeur dans le <select> masqué
        await page.wait_for_selector(
            "#selectTipoDocumento",
            state="attached",
            timeout=15000
        )
        await page.evaluate(f"""
            const sel = document.getElementById('selectTipoDocumento');
            sel.value = '{DUMMY["motivo_value"]}';
            sel.dispatchEvent(new Event('input',  {{ bubbles: true }}));
            sel.dispatchEvent(new Event('change', {{ bubbles: true }}));
        """)

        # remplir les champs obligatoires
        await page.fill("input[name=nome]", DUMMY["nome"])
        await page.fill("input[name=cognome]", DUMMY["cognome"])
        await page.fill("input[name=codiceFiscale]", DUMMY["codice_fiscale"])

        # attendre que le bouton Continua soit activé
        await page.wait_for_selector(
            "button:has-text('Continua'):not([disabled])",
            timeout=15000
        )
        await page.click("button:has-text('Continua')")

        # ─── STEP 2 ───
        await page.wait_for_url("**/sceltaComune**", timeout=15000)
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.fill("input[aria-label='Comune']", DUMMY["comune"])
        await page.click("//li[contains(., 'ROMA')]")
        await page.wait_for_selector(
            "button:has-text('Continua'):not([disabled])",
            timeout=15000
        )
        await page.click("button:has-text('Continua')")

        # ─── STEP 3 ───
        await page.wait_for_selector(
            "label.sr-only[for^='sede-']",
            timeout=15000
        )
        dispo = []
        for lbl in await page.query_selector_all("label.sr-only[for^='sede-']"):
            tr    = await lbl.evaluate_handle("e => e.closest('tr')")
            cells = await tr.query_selector_all("td")
            texts = [await c.inner_text() for c in cells]
            dispo.append(texts)

        await browser.close()
        return dispo

async def main():
    try:
        results = await check_dispo()
        if results:
            msg = "🔔 Nouveaux créneaux dispos :\n" + "\n".join(
                f"- {s} | {i} | {d}" for s, i, d in results
            )
            send_telegram(msg)
    except Exception as e:
        send_telegram(f"❌ Erreur : {e}")

if __name__ == "__main__":
    asyncio.run(main())
