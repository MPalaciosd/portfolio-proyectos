"""
Scraper de directorio de proveedores
Extrae: nombre, telefono, email, web, ubicacion
Guarda: contactos.csv
"""
from playwright.sync_api import sync_playwright
import time, csv, re
from datetime import datetime

OUTPUT_CSV = "contactos.csv"

# URLs de las categorias a scrapear
CATEGORIAS = [
    ("Categoria 1",         "https://www.directorio-ejemplo.com/categoria/subcategoria-1"),
    ("Categoria 2",       "https://www.directorio-ejemplo.com/categoria/subcategoria-2"),
    ("Categoria 3",                        "https://www.directorio-ejemplo.com/categoria/subcategoria-3"),
    ("Categoria 4",          "https://www.directorio-ejemplo.com/categoria/subcategoria-4"),
]

# Patron de URL de perfil del directorio: /categoria/nombre--eXXXXX
PERFIL_RE = re.compile(r'https?://www\.directorio-ejemplo\.com/[^/]+/[^/]+--e\d{3,}/?$')
EMAIL_RE  = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
PHONE_RE  = re.compile(r'(?:\+34[\s\-]?)?(?:6|7|8|9)\d{2}[\s.\-]?\d{3}[\s.\-]?\d{3}')

HEADERS = ["nombre", "categoria", "ubicacion", "telefono", "email", "web", "url_perfil"]
contactos = []
seen_urls = set()


def aceptar_cookies(page):
    for sel in ['#didomi-notice-agree-button', 'button:has-text("Acepto")',
                'button:has-text("Aceptar todo")', 'button:has-text("Aceptar")']:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                el.click(timeout=3000)
                time.sleep(1.5)
                return True
        except:
            pass
    return False


def extraer_perfil(page, url, categoria):
    datos = {"nombre": "", "categoria": categoria, "ubicacion": "",
             "telefono": "", "email": "", "web": "", "url_perfil": url}
    try:
        page.goto(url, timeout=30000)
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except:
            pass
        time.sleep(2)
        aceptar_cookies(page)
        time.sleep(1)

        texto = page.inner_text("body")
        html  = page.content()

        # Nombre
        for sel in ['h1', '[class*="vendor-name"]', '[class*="supplier-name"]']:
            try:
                n = page.locator(sel).first.inner_text().strip()
                if n and 3 < len(n) < 100:
                    datos["nombre"] = n
                    break
            except:
                pass

        # Ubicacion
        for sel in ['[class*="location"]', '[class*="city"]', 'address',
                    '[data-testid*="location"]', '[class*="province"]']:
            try:
                u = page.locator(sel).first.inner_text().strip()
                if u and len(u) > 2:
                    datos["ubicacion"] = u[:80]
                    break
            except:
                pass

        # Telefono: intentar clic en boton "Ver telefono"
        for sel_btn in ['button:has-text("Ver teléfono")', 'button:has-text("Llamar")',
                        'button:has-text("teléfono")', '[data-testid*="phone"]',
                        'a[href^="tel:"]']:
            try:
                el = page.locator(sel_btn).first
                if el.is_visible(timeout=2000):
                    el.click(timeout=3000)
                    time.sleep(1.5)
                    texto = page.inner_text("body")
                    html  = page.content()
                    break
            except:
                pass

        # Tel desde href tel:
        try:
            for tl in page.locator('a[href^="tel:"]').all():
                num = (tl.get_attribute("href") or "").replace("tel:", "").strip()
                if num:
                    datos["telefono"] = num
                    break
        except:
            pass

        # Tel desde regex en texto
        if not datos["telefono"]:
            phones = PHONE_RE.findall(texto)
            if phones:
                datos["telefono"] = phones[0].strip()

        # Email
        emails = EMAIL_RE.findall(html)
        emails = [e for e in emails if not any(x in e.lower() for x in
                  ["directorio-ejemplo.com", "example", "noreply", "sentry", "google",
                   "facebook", "wixpress", "schema", "@2x", "pixel"])]
        if emails:
            datos["email"] = emails[0]

        # Web externa
        try:
            for a in page.locator('a[href^="http"]').all():
                href = a.get_attribute("href") or ""
                if (href.startswith("http") and "directorio-ejemplo.com" not in href
                        and "facebook" not in href and "instagram" not in href
                        and "twitter" not in href and "tiktok" not in href
                        and "google" not in href and len(href) > 10):
                    datos["web"] = href
                    break
        except:
            pass

    except Exception as e:
        print(f"    Error perfil: {e}")
    return datos


def scrape_categoria(page, nombre_cat, url_base):
    encontrados = []

    for pagina in range(1, 10):
        if pagina == 1:
            url = url_base
        else:
            url = f"{url_base}?pagina={pagina}"

        print(f"\n  [Pag {pagina}] {url}")
        try:
            page.goto(url, timeout=30000)
            try:
                page.wait_for_load_state("networkidle", timeout=12000)
            except:
                pass
            time.sleep(3)

            # Aceptar cookies si aparece
            aceptar_cookies(page)
            time.sleep(1)

            # Scroll para cargar lazy content
            for _ in range(4):
                page.evaluate("window.scrollBy(0, 800)")
                time.sleep(1)

            html = page.content()

            # Extraer URLs de perfil con patron --eXXXXX del directorio
            hrefs = re.findall(r'href="(https?://www\.directorio-ejemplo\.com/[^"?#]+)"', html)
            hrefs += [f"https://www.directorio-ejemplo.com{h}" for h in
                      re.findall(r'href="(/[^"?#]+--e\d+[/]?)"', html)]

            perfil_urls = set()
            for h in hrefs:
                if PERFIL_RE.match(h.rstrip("/")):
                    perfil_urls.add(h.rstrip("/"))

            print(f"  Perfiles encontrados: {len(perfil_urls)}")

            if not perfil_urls:
                print(f"  Sin mas perfiles, fin del listado.")
                break

            nuevos = perfil_urls - seen_urls
            print(f"  Nuevos (no vistos aun): {len(nuevos)}")

            if not nuevos:
                print("  Todos ya procesados, siguiente pagina...")
                # Si despues de 2 paginas no hay nuevos, parar
                if pagina > 2:
                    break
                continue

            for url_p in list(nuevos):
                seen_urls.add(url_p)
                slug = url_p.split("/")[-1][:45]
                print(f"    -> {slug}")
                datos = extraer_perfil(page, url_p, nombre_cat)
                if datos["telefono"] or datos["email"]:
                    encontrados.append(datos)
                    print(f"       ✓ {datos['nombre'][:30]} | {datos['telefono']} | {datos['email'][:30]}")
                else:
                    print(f"       - {datos['nombre'][:30]} (sin contacto visible)")
                time.sleep(1.5)

        except Exception as e:
            print(f"  Error pagina {pagina}: {e}")
            break

    return encontrados


# ======================== MAIN ========================
with sync_playwright() as p:
    print("=" * 60)
    print("Scraper de directorio de proveedores")
    print(f"Inicio: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 60)

    context = p.chromium.launch_persistent_context(
        user_data_dir=".playwright_session",
        headless=False,
        slow_mo=150,
        args=["--start-maximized"],
        viewport=None
    )
    page = context.new_page()

    # Abrir home y aceptar cookies
    page.goto("https://www.directorio-ejemplo.com/", timeout=30000)
    time.sleep(3)
    aceptar_cookies(page)
    time.sleep(2)

    todos = []
    for nombre_cat, url_cat in CATEGORIAS:
        print(f"\n{'='*55}")
        print(f"CATEGORIA: {nombre_cat}")
        print(f"{'='*55}")
        res = scrape_categoria(page, nombre_cat, url_cat)
        todos.extend(res)
        print(f"\n  >> {len(res)} contactos con datos en '{nombre_cat}'")
        time.sleep(3)

    # Guardar CSV
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(todos)

    print(f"\n{'='*60}")
    print(f"COMPLETADO  {datetime.now().strftime('%H:%M:%S')}")
    print(f"Total contactos extraidos: {len(todos)}")
    print(f"CSV: {OUTPUT_CSV}")
    print(f"{'='*60}")

    time.sleep(20)
    context.close()
