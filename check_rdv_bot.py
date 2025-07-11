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
    "motivo": "Primo documento",
    "nome": "Mario",
    "cognome": "Rossi",
    "codice_fiscale": "RSSMRA80A01H501X",
    "comune": "ROMA"
}

START_URL = "https://www.prenotazionicie.interno.gov.it/cittadino/n/sc/wizardAppuntamentoCittadino/home"

async def check_dispo():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # STEP 1
        await page.goto(START_URL)
        await page.wait_for_load_state("networkidle", timeout=30000)

        # On cherche tous les <select>
        selects = await page.query_selector_all("select")
        if not selects:
            send_telegram("❌ Debug: aucun <select> trouvé sur la page STEP 1.")
            await browser.close()
            return []

        # Si aucun ne porte name=motivoAppuntamento, on dump leur HTML
        try:
            await page.wait_for_selector(
                "select[name=motivoAppuntamento]",
                state="visible",
                timeout=10000
            )
        except Exception:
            htmls = []
            for s in selects:
                outer = await s.evaluate("e => e.outerHTML")
                htmls.append(outer)
            debug_msg = "❌ Debug: pas de select[name=motivoAppuntamento].\n\n"
            debug_msg += "\n\n".join(htmls)
            # Attention à la limite de longueur de Telegram : on peut tronquer si trop long
            send_telegram(debug_msg[:3500])
            await browser.close()
            return []

        # (S'il existait, on exécuterait la suite – mais on est ici que pour debugger)
        await browser.close()
        return []

async def main():
    try:
        await check_dispo()
    except Exception as e:
        send_telegram(f"❌ Erreur fatale : {e}")

if __name__ == "__main__":
    asyncio.run(main())
