# Secretario IA — Dashboard Web + Telegram Bot

Aplicación web completa con dashboard de eventos, chat con IA y bot de Telegram.

---

## Estructura de archivos

```
/
├── bot.py            ← Servidor principal (Flask + bot Telegram)
├── index.html        ← Dashboard web (pegar en la raíz del proyecto)
├── requirements.txt  ← Dependencias Python
└── README.md
```

---

## Configuración en Render

### 1. Sube los archivos a GitHub

Asegúrate de que tu repositorio en GitHub tiene estos 4 archivos:
- `bot.py`
- `index.html`
- `requirements.txt`
- `README.md`

### 2. Variables de entorno en Render

Ve a tu servicio en Render → **Environment** y añade:

| Variable              | Valor                          |
|-----------------------|-------------------------------|
| `TELEGRAM_TOKEN`      | Token de tu bot de Telegram    |
| `SUPABASE_URL`        | URL de tu proyecto Supabase    |
| `SUPABASE_KEY`        | Anon key de Supabase           |
| `GROQ_API_KEY`        | Tu API key de Groq             |
| `FOOTBALL_DATA_TOKEN` | Tu token de api-sports.io      |

### 3. Build & Start Command en Render

- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn bot:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120`

---

## Tabla de Supabase — eventos

Tu tabla `eventos` debería tener estas columnas (añade las que no tengas):

```sql
CREATE TABLE eventos (
  id            bigint generated always as identity primary key,
  nombre_evento text not null,
  fecha         text,
  hora          text,
  lugar         text,
  categoria     text default 'Work',  -- Work | Marketing | Social | Finance | HR
  eta           text,                 -- ej: "12"  (minutos)
  distancia     text                  -- ej: "3.2" (km)
);
```

Si tu tabla ya existe y tiene columnas distintas, el dashboard las mostrará igualmente
(adaptará `nombre_evento` y `fecha` como mínimo).

---

## Endpoints disponibles

| Ruta           | Método | Descripción                          |
|----------------|--------|--------------------------------------|
| `/`            | GET    | Sirve el dashboard web               |
| `/api/eventos` | GET    | Devuelve eventos en JSON             |
| `/api/chat`    | POST   | Chat con la IA (`{"message":"..."}`) |
| `/health`      | GET    | Estado del servidor                  |

---

## Filtros de categoría del dashboard

Los eventos se filtran por el campo `categoria` en Supabase.
Valores soportados: `Work`, `Marketing`, `Social`, `Finance`, `HR`.

---

## Notas

- El bot de Telegram sigue funcionando exactamente igual que antes.
- El dashboard web es independiente; no interfiere con el bot.
- La URL del dashboard es la misma de tu servicio Render: `https://secretario-ia.onrender.com`
