```python
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

async def check_dispo() -> list[tuple[str, str, str]]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page    = await browser.new_page()

        # STEP 1: formulaire initial
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
        # activer et cliquer
        await page.evaluate("""document.querySelector("button[value='continua']").removeAttribute('disabled');""")
        await page.click("button[value='continua']", timeout=5000)

        # STEP 2: choix du Comune
        await page.wait_for_url("**/sceltaComune**", timeout=5000)
        await page.wait_for_load_state("networkidle", timeout=5000)
        # enlever overlay & modal
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

        # STEP 3: extraction des créneaux
        await page.wait_for_load_state("networkidle", timeout=5000)
        dispo = []
        # pour chaque ligne du tableau
        for tr in await page.query_selector_all("tbody tr"):
            # nom de la sede
            th = await tr.query_selector("th[scope='row']")
            sede = (await th.inner_text()).strip() if th else ""
            # adresse et date : td[0] et td[2]
            tds = await tr.query_selector_all("td")
            if len(tds) >= 3:
                indirizzo = (await tds[0].inner_text()).strip()
                date_txt  = (await tds[2].inner_text()).strip()
                # ne garder que si on trouve dd/mm/yyyy
                if re.search(r"\d{2}/\d{2}/\d{4}", date_txt):
                    dispo.append((sede, indirizzo, date_txt))

        await browser.close()
        return dispo

async def main():
    try:
        results = await check_dispo()
        if not results:
            send_telegram("❌ AUCUN créneau disponible pour le moment.")
            return

        lines = [f"- {s} | {i} | {d}" for s, i, d in results]
        msg   = "🔔 Nouveaux créneaux dispos :\n\n" + "\n\n".join(lines)
        send_telegram(msg)

    except Exception as e:
        send_telegram(f"❌ Erreur : {e}")

if __name__ == "__main__":
    asyncio.run(main())
```
