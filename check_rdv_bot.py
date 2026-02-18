import asyncio
import os
import re
import requests
import time
import random
from playwright.async_api import async_playwright

# ————— CONFIG —————
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
BOOKING_URL      = "https://www.prenotazionicie.interno.gov.it/cittadino/n/sc/loginCittadino"

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

async def check_dispo():
    async with async_playwright() as p:
        # Ajout d'arguments pour éviter la détection robot
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            # STEP 1 : Identité avec attente renforcée
            await page.goto("https://www.prenotazionicie.interno.gov.it/cittadino/n/sc/wizardAppuntamentoCittadino/home", wait_until="networkidle", timeout=60000)
            
            # Correction du Timeout : on attend que le sélecteur soit réellement prêt
            await page.wait_for_selector("#selectTipoDocumento", state="visible", timeout=30000)
            await page.select_option("#selectTipoDocumento", "1")
            
            await page.fill("input[name=nome]", "Mario")
            await page.fill("input[name=cognome]", "Rossi")
            await page.fill("input[name=codiceFiscale]", "RSSMRA80A01H501X")
            
            await page.evaluate('document.querySelector("button[value=\'continua\']").removeAttribute("disabled")')
            await page.click("button[value='continua']")

            # STEP 2 : Commune
            await page.wait_for_url("**/sceltaComune**", timeout=20000)
            await page.fill("#comuneResidenzaInput", "ROMA")
            await page.click("ul.typeahead li:has-text('ROMA')")
            await page.evaluate('document.querySelector("button[value=\'continua\']").removeAttribute("disabled")')
            
            # INTERCEPTION JSON
            async with page.expect_response(re.compile(r".*/getDisponibilitaSedi.*"), timeout=30000) as response_info:
                await page.click("button[value='continua']")
                response = await response_info.value
                json_data = await response.json()
                return json_data.get('dati', [])
        except Exception as e:
            print(f"⚠️ Erreur de navigation (Timeout possible) : {e}")
            return []
        finally:
            await browser.close()

async def main():
    global LAST_DATE_FOUND
    print(f"🔍 Vérification @ {time.strftime('%H:%M:%S')}...")
    
    data_list = await check_dispo()
    
    # Filtre strict : Municipio I - Via Luigi Petroselli
    target = next((item for item in data_list if "Municipio I" in item.get('nomeSede', '') and "Petroselli" in item.get('indirizzoSede', '')), None)

    if target:
        dispo_str = target.get('disponibilita', '')
        if re.search(r"\d{2}/\d{2}/\d{4}", dispo_str):
            if dispo_str != LAST_DATE_FOUND:
                msg = (
                    "🚨 **CRÉNEAU MUNICIPIO I DISPONIBLE !**\n\n"
                    f"🏛 *{target.get('nomeSede')}*\n"
                    f"📍 {target.get('indirizzoSede')}\n"
                    f"🗓 **{dispo_str}**\n\n"
                    f"🚀 [RÉSERVER MAINTENANT]({BOOKING_URL})"
                )
                send_telegram(msg)
                LAST_DATE_FOUND = dispo_str
                print(f"✅ Alerte envoyée : {dispo_str}")
    else:
        print("ℹ️ Aucun créneau pour le Municipio I.")

async def run_loop():
    while True:
        await main()
        # Délai de 2 minutes avec jitter pour rester discret
        wait = 120 + random.randint(1, 15)
        print(f"😴 Attente {wait}s...")
        await asyncio.sleep(wait)

if __name__ == "__main__":
    asyncio.run(run_loop())
