const http = require('http');
const https = require('https');

const INTERVAL_MS = 14 * 60 * 1000; // 14 minutos
let failCount = 0;

/**
 * Hace un ping a la propia URL del servidor para evitar cold starts
 * y detectar si el proceso está respondiendo.
 */
function startKeepAlive(port) {
  // En producción usamos la URL pública; en local usamos localhost
  const appUrl = process.env.APP_PUBLIC_URL
    ? `${process.env.APP_PUBLIC_URL}/health`
    : `http://localhost:${port}/health`;

  const client = appUrl.startsWith('https') ? https : http;

  function ping() {
    const req = client.get(appUrl, (res) => {
      if (res.statusCode === 200) {
        failCount = 0;
        console.log(`[KeepAlive] OK — ${new Date().toISOString()}`);
      } else {
        failCount++;
        console.warn(`[KeepAlive] Status inesperado: ${res.statusCode} (fallos: ${failCount})`);
      }
    });

    req.on('error', (err) => {
      failCount++;
      console.error(`[KeepAlive] Error ping: ${err.message} (fallos: ${failCount})`);
      // Si falla 5 veces seguidas algo va muy mal
      if (failCount >= 5) {
        console.error('[KeepAlive] ⚠️  El servidor no responde. Revisa los logs de Render.');
      }
    });

    req.setTimeout(10000, () => {
      req.destroy();
      console.warn('[KeepAlive] Timeout en ping.');
    });
  }

  // Primer ping a los 30s de arrancar (deja tiempo al servidor de iniciarse)
  setTimeout(ping, 30_000);
  setInterval(ping, INTERVAL_MS);

  console.log(`[KeepAlive] Iniciado — ping cada 14 min → ${appUrl}`);
}

module.exports = { startKeepAlive };
