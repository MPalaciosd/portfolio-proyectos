/**
 * ╔══════════════════════════════════════════════════════╗
 * ║   BARBERSHOP AGENT — Setup Automatizado              ║
 * ║   Solo necesitas iniciar sesión en los servicios.    ║
 * ╚══════════════════════════════════════════════════════╝
 *
 * Servicios gratuitos que se configuran:
 *   1. MongoDB Atlas M0  (base de datos, gratis)
 *   2. Render.com        (hosting web, gratis)
 *
 * Servicios que ya tienes configurados:
 *   ✅ Groq API (IA)
 *   ✅ Telegram Bot
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const ENV_PATH = path.join(ROOT, '.env');

// ── Cargar .env actual ────────────────────────────────────────────────────────
function loadEnv() {
  const env = {};
  if (fs.existsSync(ENV_PATH)) {
    const lines = fs.readFileSync(ENV_PATH, 'utf8').split('\n');
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#')) continue;
      const idx = trimmed.indexOf('=');
      if (idx > 0) {
        env[trimmed.slice(0, idx)] = trimmed.slice(idx + 1);
      }
    }
  }
  return env;
}

// ── Guardar/actualizar .env ───────────────────────────────────────────────────
function updateEnv(updates) {
  let content = '';
  if (fs.existsSync(ENV_PATH)) {
    content = fs.readFileSync(ENV_PATH, 'utf8');
  }

  for (const [key, value] of Object.entries(updates)) {
    const regex = new RegExp(`^${key}=.*$`, 'm');
    if (regex.test(content)) {
      content = content.replace(regex, `${key}=${value}`);
    } else {
      content += `\n${key}=${value}`;
    }
  }

  fs.writeFileSync(ENV_PATH, content.trim() + '\n', 'utf8');
  console.log(`✅ .env actualizado con: ${Object.keys(updates).join(', ')}`);
}

// ── Main ──────────────────────────────────────────────────────────────────────
async function main() {
  printHeader();

  const env = loadEnv();

  // ── PASO 1: MongoDB Atlas ─────────────────────────────────────────────────
  let mongoUri = env.MONGODB_URI;

  if (!mongoUri || mongoUri.includes('usuario:password')) {
    console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('PASO 1/2 — MongoDB Atlas (base de datos gratuita)');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('El navegador se abrirá en mongodb.com/atlas');
    console.log('Inicia sesión o crea una cuenta gratuita (sin tarjeta).\n');

    const { setupMongoAtlas } = require('./atlas');

    try {
      const result = await setupMongoAtlas();
      mongoUri = result.uri;

      if (result.user) {
        console.log(`\n🔑 Usuario DB: ${result.user}`);
        console.log(`🔑 Contraseña DB: ${result.pass}`);
        console.log('   (guárdalas en un lugar seguro)\n');
      }

      updateEnv({ MONGODB_URI: mongoUri });
    } catch (err) {
      console.error('\n❌ Error en la configuración de MongoDB:', err.message);
      console.log('\n   Por favor, obtén la URI manualmente en mongodb.com/atlas');
      console.log('   y añádela al archivo .env como MONGODB_URI=...');
      process.exit(1);
    }
  } else {
    console.log('\n✅ PASO 1/2 — MongoDB Atlas ya configurado.');
  }

  // ── PASO 2: Render.com (hosting) ─────────────────────────────────────────
  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('PASO 2/2 — Render.com (hosting gratuito)');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('Necesitas subir el proyecto a GitHub antes de desplegarlo.');
  console.log('');

  // Preguntar si ya tiene GitHub o quiere hacerlo manualmente
  const readline = require('readline');
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });

  const answer = await new Promise(resolve => {
    rl.question(
      '¿Quieres que abra Render.com para configurar el hosting? (s/n): ',
      ans => { rl.close(); resolve(ans.toLowerCase()); }
    );
  });

  if (answer === 's' || answer === 'si' || answer === 'sí' || answer === 'y') {
    // Obtener todas las variables de entorno para pasarlas a Render
    const freshEnv = loadEnv();

    const { deployToRender } = require('./deploy');
    await deployToRender(freshEnv);
  } else {
    printManualDeployInstructions(loadEnv());
  }

  // ── UptimeRobot — mantener el servicio despierto ──────────────────────────
  await openUptimeRobot();

  printFinish();
}

async function openUptimeRobot() {
  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('EXTRA — UptimeRobot (mantener el servidor despierto)');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('Render.com apaga el servidor si no recibe peticiones.');
  console.log('UptimeRobot lo pinga cada 5 min para mantenerlo activo (gratis).\n');

  const readline = require('readline');
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });

  const answer = await new Promise(resolve => {
    rl.question(
      '¿Abrir UptimeRobot para configurarlo? (s/n): ',
      ans => { rl.close(); resolve(ans.toLowerCase()); }
    );
  });

  if (answer === 's' || answer === 'si' || answer === 'sí' || answer === 'y') {
    const { chromium } = require('playwright');
    const browser = await chromium.launch({ headless: false, args: ['--start-maximized'] });
    const page = await (await browser.newContext({ viewport: null })).newPage();
    await page.goto('https://uptimerobot.com/dashboard', { waitUntil: 'domcontentloaded' });

    console.log('\n⏳ Abriendo UptimeRobot...');
    console.log('   1. Crea una cuenta gratuita (o inicia sesión)');
    console.log('   2. Haz clic en "+ New Monitor"');
    console.log('   3. Monitor Type: HTTP(s)');
    console.log('   4. URL: tu URL de Render (ej: https://barbershop-agent.onrender.com)');
    console.log('   5. Monitoring Interval: Every 5 minutes');
    console.log('   6. Haz clic en "Create Monitor"\n');
    console.log('   Cierra el navegador cuando termines.');

    // Esperar a que el usuario cierre el navegador
    await browser.waitForEvent('disconnected', { timeout: 600_000 }).catch(() => {});
  }
}

function printManualDeployInstructions(env) {
  console.log('\n📋 Instrucciones para desplegar manualmente en Render.com:');
  console.log('   1. Sube este proyecto a GitHub (github.com/new)');
  console.log('   2. Ve a dashboard.render.com > New > Web Service');
  console.log('   3. Conecta tu repositorio de GitHub');
  console.log('   4. Configura:');
  console.log('      - Build Command: npm install');
  console.log('      - Start Command: node index.js');
  console.log('   5. Añade estas variables de entorno:');

  for (const [key, value] of Object.entries(env)) {
    if (value) console.log(`      ${key}=${value}`);
  }

  console.log('   6. Haz clic en "Create Web Service"\n');
}

function printHeader() {
  console.clear();
  console.log('');
  console.log('╔══════════════════════════════════════════════════════╗');
  console.log('║   🔱 BARBERSHOP AGENT — Setup Automatizado           ║');
  console.log('║   Servicios 100% gratuitos, sin tarjeta de crédito   ║');
  console.log('╚══════════════════════════════════════════════════════╝');
  console.log('');
  console.log('  Este script configura todo automáticamente.');
  console.log('  Solo tendrás que iniciar sesión en los servicios.');
  console.log('');
}

function printFinish() {
  console.log('\n╔══════════════════════════════════════════════════════╗');
  console.log('║   ✅ ¡Setup completado!                              ║');
  console.log('╠══════════════════════════════════════════════════════╣');
  console.log('║                                                      ║');
  console.log('║  Tu agente de citas está configurado y en marcha.   ║');
  console.log('║                                                      ║');
  console.log('║  ✅ Base de datos: MongoDB Atlas (gratis)            ║');
  console.log('║  ✅ IA: Groq / Llama 4 Scout (gratis)               ║');
  console.log('║  ✅ Bot Telegram: activo                             ║');
  console.log('║  ✅ Servidor web: Render.com (gratis)               ║');
  console.log('║                                                      ║');
  console.log('║  Para probar localmente:                             ║');
  console.log('║    cd .. && npm start                                ║');
  console.log('║                                                      ║');
  console.log('╚══════════════════════════════════════════════════════╝');
  console.log('');
}

main().catch(err => {
  console.error('\n❌ Error en el setup:', err.message);
  process.exit(1);
});
