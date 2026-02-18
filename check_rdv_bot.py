import asyncio
import os
import re
import requests
import time
import random
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# ————— CONFIG —————
# Utilise les secrets configurés dans GitHub Actions
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
BOOKING_URL      = "https://www.prenotazionicie.interno.gov.it/cittadino/n/sc/loginCittadino"

# État pour éviter de notifier plusieurs fois la même date
LAST_DATE_FOUND = None

def send_telegram(text: str):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={
            "chat_id": TELEGRAM_CHAT_ID, 
            "text": text, 
            "parse_mode": "Markdown",
            "disable_web_page_preview": "true"
        }
    )

DUMMY = {
    "motivo_value":   "1",
    "nome":            "Mario",
    "cognome":         "Rossi",
    "codice_fiscale":  "RSSMRA80A01H501X",
    "comune":          "ROMA"
}

START_URL = "https://www.prenotazionicie.interno.gov.it/cittadino/n/sc/wizardAppuntamentoCittadino/home"

async def check_dispo():
    async with async_playwright() as p:
        # On ajoute des arguments pour masquer Playwright
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            # Navigation avec un timeout plus long
            await page.goto(START_URL, wait_until="networkidle", timeout=60000)
            
            # On attend que le sélecteur soit réellement visible
            selector = "#selectTipoDocumento"
            await page.wait_for_selector(selector, state="visible", timeout=20000)
            
            await page.select_option(selector, DUMMY['motivo_value'])
            await asyncio.sleep(1) # Pause humaine
            
            await page.fill("input[name=nome]", DUMMY["nome"])
            await page.fill("input[name=cognome]", DUMMY["cognome"])
            await page.fill("input[name=codiceFiscale]", DUMMY["codice_fiscale"])
            
            await page.evaluate('document.querySelector("button[value=\'continua\']").removeAttribute("disabled")')
            await asyncio.sleep(0.5)
            await page.click("button[value='continua']")

            # STEP 2
            await page.wait_for_url("**/sceltaComune**", timeout=20000)
            await page.fill("#comuneResidenzaInput", DUMMY["comune"])
            await asyncio.sleep(1)
            await page.click("ul.typeahead li:has-text('ROMA')")
            
            await page.evaluate('document.querySelector("button[value=\'continua\']").removeAttribute("disabled")')
            
            async with page.expect_response(re.compile(r".*/getDisponibilitaSedi.*"), timeout=20000) as response_info:
                await page.click("button[value='continua']")
                response = await response_info.value
                json_data = await response.json()
                return json_data.get('dati', [])

        except Exception as e:
            # On log l'erreur mais on ne crash pas le script
            print(f"⚠️ Scan ignoré (site instable ou bloqué) : {e}")
            return []
        finally:
            await browser.close()

async def main_task():
    global LAST_DATE_FOUND
    print(f"🔍 Scan @ {time.strftime('%H:%M:%S')}...")
    
    results = await check_dispo()
    
    # Filtre strict : Municipio I + Via Petroselli + Date valide
    target = next((
        (s, i, d) for s, i, d in results 
        if "Municipio I" in s and "Petroselli" in i and re.search(r"\d{2}/\d{2}/\d{4}", d)
    ), None)

    if target:
        s, i, d = target
        # Notifie seulement si la date est nouvelle
        if d != LAST_DATE_FOUND:
            msg = (
                "🚨 *CRÉNEAU MUNICIPIO I DISPO !*\n\n"
                f"🏛 *{s}*\n"
                f"🏠 {i.replace(chr(10), ' ')}\n"
                f"🗓 *{d}*\n\n"
                f"🚀 [RÉSERVER MAINTENANT]({BOOKING_URL})"
            )
            send_telegram(msg)
            LAST_DATE_FOUND = d
            print(f"✅ Alerte envoyée : {d}")
    else:
        print("ℹ️ Municipio I : Toujours aucune place.")

async def run_loop():
    while True:
        await main_task()
        # Intervalle de 60 secondes
        # J'ajoute un petit jitter de 1 à 5 sec pour ne pas être trop régulier
        wait = 60 + random.randint(1, 5)
        print(f"😴 Repos {wait}s...")
        await asyncio.sleep(wait)

if __name__ == "__main__":
    asyncio.run(run_loop())
