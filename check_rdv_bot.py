import asyncio
import os
import re
import requests
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

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

        # STEP 1
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
        await page.evaluate("""
            const b = document.querySelector("button[value='continua']");
            if (b) b.removeAttribute('disabled');
        """)
        await page.click("button[value='continua']", timeout=5000)

        # STEP 2
        await page.wait_for_url("**/sceltaComune**", timeout=5000)
        await page.wait_for_load_state("networkidle", timeout=5000)
        await page.evaluate("""
            document.querySelectorAll('.black-overlay, #messageModalBox')
                    .forEach(e=>e.remove());
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
        await page.evaluate("""
            const b2 = document.querySelector("button[value='continua']");
            if (b2) b2.removeAttribute('disabled');
        """)
        await page.click("button[value='continua']", timeout=5000)

        # STEP 3
        dispo = []
        try:
            await page.wait_for_selector("label.sr-only[for^='sede-']", timeout=5000)
        except PlaywrightTimeoutError:
            # pas de créneaux du tout
            await browser.close()
            return []

        for lbl in await page.query_selector_all("label.sr-only[for^='sede-']"):
            tr    = await lbl.evaluate_handle("e=>e.closest('tr')")
            cells = await tr.query_selector_all("td")
            texts = [await c.inner_text() for c in cells][:3]
            if len(texts) == 3:
                sede, indirizzo, date = (t.strip() for t in texts)
                dispo.append((sede, indirizzo, date))

        await browser.close()
        return dispo

async def main():
    try:
        results = await check_dispo()
        if not results:
            send_telegram("❌ AUCUN créneau disponible pour le moment.")
            return

        # on garde ceux qui contiennent une date dd/mm/yyyy
        filtered = [
            (s,i,d) for s,i,d in results
            if re.search(r"\d{2}/\d{2}/\d{4}", d)
        ]
        if not filtered:
            send_telegram("❌ AUCUN créneau disponible pour le moment.")
            return

        lines = [f"- {s} | {i} | {d}" for s,i,d in filtered]
        msg   = "🔔 Nouveaux créneaux dispos :\n\n" + "\n\n".join(lines)
        send_telegram(msg)

    except Exception as e:
        send_telegram(f"❌ Erreur : {e}")

if __name__ == "__main__":
    asyncio.run(main())
