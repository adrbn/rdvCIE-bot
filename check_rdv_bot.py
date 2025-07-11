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
        await page.wait_for_load_state("networkidle", timeout=10000)

        # injecte le select masqué
        await page.wait_for_selector("#selectTipoDocumento", state="attached", timeout=10000)
        await page.evaluate(f"""
            const sel = document.getElementById('selectTipoDocumento');
            sel.value = '{DUMMY['motivo_value']}';
            sel.dispatchEvent(new Event('input', {{ bubbles: true }}));
            sel.dispatchEvent(new Event('change', {{ bubbles: true }}));
        """)

        # remplis les autres champs obligatoires
        await page.fill("input[name=nome]", DUMMY["nome"], timeout=5000)
        await page.fill("input[name=cognome]", DUMMY["cognome"], timeout=5000)
        await page.fill("input[name=codiceFiscale]", DUMMY["codice_fiscale"], timeout=5000)

        # force le bouton Continua et clique
        await page.evaluate("""
            const btn = document.querySelector("button[value='continua']");
            if (btn) btn.removeAttribute('disabled');
        """)
        await page.click("button[value='continua']", timeout=10000)

        # ─── STEP 2 ───
        await page.wait_for_url("**/sceltaComune**", timeout=10000)
        await page.wait_for_load_state("networkidle", timeout=10000)

        # ─── Supprime le modal et l’overlay qui bloquent la page ───
        await page.evaluate("""
            const ov = document.querySelector('.black-overlay');
            if (ov) ov.remove();
            const md = document.getElementById('messageModalBox');
            if (md) md.remove();
        """)

        # simule un vrai typing pour déclencher le typeahead
        await page.click("#comuneResidenzaInput", timeout=5000)
        await page.type("#comuneResidenzaInput", DUMMY["comune"], delay=100, timeout=5000)

        # attends et clique la suggestion
        await page.wait_for_selector(
            "comune-typeahead ul.typeahead.dropdown-menu li:has-text('ROMA')",
            timeout=5000
        )
        await page.click(
            "comune-typeahead ul.typeahead.dropdown-menu li:has-text('ROMA')",
            timeout=5000
        )

        # force de nouveau Continua et clique
        await page.evaluate("""
            const btn2 = document.querySelector("button[value='continua']");
            if (btn2) btn2.removeAttribute('disabled');
        """)
        await page.click("button[value='continua']", timeout=10000)

        # ─── STEP 3 ───
        await page.wait_for_selector("label.sr-only[for^='sede-']", timeout=10000)
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
