# Scraper de Directorio de Proveedores

Herramienta de extracción automática de datos de contacto de proveedores en directorios web.

## Qué hace

- Recorre las categorías configuradas de un directorio web paginado
- Entra en cada perfil de proveedor y extrae: nombre, teléfono, email, web, ubicación
- Maneja banners de cookies automáticamente
- Exporta los resultados a un CSV listo para usar

## Stack

- **Python** + **Playwright** (automatización de navegador real)
- Manejo de paginación dinámica
- Regex para extracción de teléfonos y emails
- Exportación a CSV con encoding UTF-8

## Uso

```bash
pip install -r requirements.txt
playwright install chromium
```

Configura `BASE_DOMAIN` y `CATEGORIAS` en `scraper.py` apuntando al directorio objetivo, luego:

```bash
python scraper.py
```

Genera `contactos.csv` con todos los proveedores encontrados.
