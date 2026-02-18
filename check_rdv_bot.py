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
        # Launch avec mode furtif pour éviter les blocages sur répétition
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page    = await context.new_page()

        try:
            # STEP 1 : Formulaire initial
            await page.goto(START_URL, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_selector("#selectTipoDocumento", timeout=10000)
            
            await page.select_option("#selectTipoDocumento", DUMMY['motivo_value'])
            await page.fill("input[name=nome]", DUMMY["nome"])
            await page.fill("input[name=cognome]", DUMMY["cognome"])
            await page.fill("input[name=codiceFiscale]", DUMMY["codice_fiscale"])
            
            await page.evaluate('document.querySelector("button[value=\'continua\']").removeAttribute("disabled")')
            await page.click("button[value='continua']")

            # STEP 2 : Choix de la commune
            await page.wait_for_url("**/sceltaComune**", timeout=10000)
            await page.type("#comuneResidenzaInput", DUMMY["comune"], delay=20) # Frappe ultra rapide
            await page.click("ul.typeahead li:has-text('ROMA')")
            
            await page.evaluate('document.querySelector("button[value=\'continua\']").removeAttribute("disabled")')
            await page.click("button[value='continua']")

            # STEP 3 : Extraction propre (Municipio I uniquement)
            await page.wait_for_selector("label.sr-only[for^='sede-']", timeout=15000)

            dispo = []
            labels = await page.query_selector_all("label.sr-only[for^='sede-']")
            
            for lbl in labels:
                tr = await lbl.evaluate_handle("e => e.closest('tr')")
                cells = await tr.query_selector_all("td")
                
                if len(cells) >= 4:
                    sede = await cells[0].inner_text()
                    addr = await cells[1].inner_text()
                    # On prend l'index 3 pour ignorer la colonne "NO"
                    date = await cells[3].inner_text() 

                    dispo.append((sede.strip(), addr.strip(), date.strip()))

            await browser.close()
            return dispo

        except Exception as e:
            print(f"Erreur technique : {e}")
            await browser.close()
            return []

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
