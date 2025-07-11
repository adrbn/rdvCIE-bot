import asyncio
import os
import re
import requests
from playwright.async_api import async_playwright

# ————— CONFIG —————
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def send_telegram(text: str):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={
            "chat_id":    TELEGRAM_CHAT_ID,
            "text":       text,
            "parse_mode": "Markdown"
        }
    )

DUMMY = {
    "motivo_value":  "1",               # 1 = Primo Documento
    "nome":           "Mario",
    "cognome":        "Rossi",
    "codice_fiscale": "RSSMRA80A01H501X",
    "comune":         "ROMA"
}

START_URL = (
    "https://www.prenotazionicie.interno.gov.it"
    "/cittadino/n/sc/wizardAppuntamentoCittadino/home"
)

async def check_dispo():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page    = await browser.new_page()

        # STEP 1 — motif + infos personnelles
        await page.goto(START_URL)
        await page.wait_for_load_state("networkidle", timeout=5000)
        await page.wait_for_selector("#selectTipoDocumento", state="attached", timeout=5000)
        await page.evaluate(f"""
            const sel = document.getElementById('selectTipoDocumento');
            sel.value = '{DUMMY['motivo_value']}';
            sel.dispatchEvent(new Event('input', {{ bubbles: true }}));
            sel.dispatchEvent(new Event('change', {{ bubbles: true }}));
        """)
        await page.fill("input[name=nome]", DUMMY["nome"], timeout=3000)
        await page.fill("input[name=cognome]", DUMMY["cognome"], timeout=3000)
        await page.fill("input[name=codiceFiscale]", DUMMY["codice_fiscale"], timeout=3000)
        await page.evaluate("document.querySelector(\"button[value='continua']\").removeAttribute('disabled')")
        await page.click("button[value='continua']", timeout=5000)

        # STEP 2 — choix du Comune
        await page.wait_for_url("**/sceltaComune**", timeout=5000)
        await page.wait_for_load_state("networkidle", timeout=5000)
        # on supprime overlay / modal
        await page.evaluate("""
            document.querySelectorAll('.black-overlay, #messageModalBox').forEach(el => el.remove());
        """)
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
        await page.evaluate("document.querySelector(\"button[value='continua']\").removeAttribute('disabled')")
        await page.click("button[value='continua']", timeout=5000)

        # STEP 3 — scraping des créneaux
        await page.wait_for_selector("label.sr-only[for^='sede-']", timeout=5000)
        dispo = []
        for lbl in await page.query_selector_all("label.sr-only[for^='sede-']"):
            tr    = await lbl.evaluate_handle("e => e.closest('tr')")
            cells = await tr.query_selector_all("td")
            texts = [await c.inner_text() for c in cells]
            # On s'assure d'avoir au moins 4 colonnes : Sede, Adresse, Sans RDV, Date
            if len(texts) < 4:
                continue
            sede       = texts[0].strip()
            indirizzo  = texts[1].strip()
            sans_rdv   = texts[2].strip()  # "-" ou "non"
            date_creneau = texts[3].strip()
            # On ne garde que les vrais créneaux (date au format dd/MM/yyyy)
            if not re.match(r"\d{2}/\d{2}/\d{4}", date_creneau):
                continue
            dispo.append((sede, indirizzo, sans_rdv, date_creneau))

        await browser.close()
        return dispo

async def main():
    try:
        results = await check_dispo()
        if results:
            msg = ["*🔔 Nouveaux créneaux disponibles :*\n"]
            for sede, adr, sans, date in results:
                msg.append(
                    f"*{sede}*\n"
                    f"  - Adresse : _{adr}_\n"
                    f"  - Sans RDV : `{sans}`\n"
                    f"  - Date : *{date}*\n"
                )
            send_telegram("\n".join(msg))
    except Exception as e:
        send_telegram(f"❌ Erreur : {e}")

if __name__ == "__main__":
    asyncio.run(main())
