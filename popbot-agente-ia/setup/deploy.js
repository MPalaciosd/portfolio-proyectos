/**
 * Despliegue automático a Render.com con Playwright
 * Solo necesitas iniciar sesión — el script hace el resto
 */

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const RENDER_URL = 'https://render.com/';
const PROJECT_ROOT = path.join(__dirname, '..');

async function deployToRender(envVars) {
  console.log('\n🚀 Abriendo Render.com para desplegar tu agente...');
  console.log('   ➜ Inicia sesión con GitHub (recomendado) o con tu email\n');

  const browser = await chromium.launch({
    headless: false,
    args: ['--start-maximized'],
  });

  const context = await browser.newContext({ viewport: null });
  const page = await context.newPage();

  await page.goto('https://dashboard.render.com/', { waitUntil: 'domcontentloaded' });

  // ── Esperar login ────────────────────────────────────────────────────────
  console.log('⏳ Esperando que inicies sesión en Render.com...\n');

  await page.waitForURL(/dashboard\.render\.com\/(projects|services|new)/, {
    timeout: 300_000,
  });

  await page.waitForLoadState('networkidle', { timeout: 20_000 }).catch(() => {});
  await page.waitForTimeout(2000);

  console.log('✅ Sesión detectada. Creando nuevo servicio web...');

  // ── Crear nuevo Web Service ──────────────────────────────────────────────
  await page.goto('https://dashboard.render.com/new/web', { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle', { timeout: 20_000 }).catch(() => {});
  await page.waitForTimeout(2000);

  // Seleccionar "Deploy an existing image or use a Git repository"
  // Render pedirá conectar un repo de GitHub o subir manualmente

  // Buscar opción de "Public Git repository" (sin necesidad de conectar GitHub)
  const publicGitOption = page.locator(
    'a:has-text("Public Git"), button:has-text("Public Git"), [data-value*="public"]'
  ).first();

  if (await publicGitOption.isVisible({ timeout: 8000 }).catch(() => false)) {
    await publicGitOption.click();
    await page.waitForTimeout(1500);
  } else {
    // Buscar la opción de conectar con GitHub
    const githubBtn = page.locator('a:has-text("Connect GitHub"), button:has-text("GitHub")').first();
    if (await githubBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
      console.log('\n⚠️  Render necesita un repositorio de GitHub.');
      console.log('   El script abrirá el paso de conexión. Conecta tu GitHub si aún no lo has hecho.');
      await githubBtn.click();
      await page.waitForTimeout(3000);
    }
  }

  // Configurar el servicio si ya pasamos al formulario
  await configurarServicio(page, envVars);

  console.log('\n🎉 ¡Despliegue iniciado en Render.com!');
  console.log('   Tu agente estará listo en ~3-5 minutos.');
  console.log('   Render te enviará un email cuando esté en línea.\n');

  // Obtener la URL del servicio
  try {
    const serviceUrl = await page.locator('[data-testid*="service-url"], a[href*=".onrender.com"]')
      .first()
      .textContent({ timeout: 30_000 });
    if (serviceUrl) {
      console.log(`   🌐 URL de tu agente: ${serviceUrl.trim()}`);
    }
  } catch {
    console.log('   (La URL estará disponible en el panel de Render cuando el deploy termine)');
  }

  await browser.close();
}

async function configurarServicio(page, envVars) {
  await page.waitForTimeout(2000);

  // Nombre del servicio
  const nameInput = page.locator('input[name="name"], input[placeholder*="name"], input[id*="name"]').first();
  if (await nameInput.isVisible({ timeout: 8000 }).catch(() => false)) {
    await nameInput.clear();
    await nameInput.type('barbershop-agent');
  }

  // Start command
  const startInput = page.locator('input[name*="start"], input[placeholder*="start command"]').first();
  if (await startInput.isVisible({ timeout: 5000 }).catch(() => false)) {
    await startInput.clear();
    await startInput.type('node index.js');
  }

  // ── Variables de entorno ─────────────────────────────────────────────────
  const envTab = page.locator('button:has-text("Environment"), a:has-text("Environment Variables")').first();
  if (await envTab.isVisible({ timeout: 5000 }).catch(() => false)) {
    await envTab.click();
    await page.waitForTimeout(1500);
  }

  // Añadir cada variable
  for (const [key, value] of Object.entries(envVars)) {
    if (!value) continue;
    await agregarEnvVar(page, key, value);
  }

  // ── Deploy ───────────────────────────────────────────────────────────────
  const deployBtn = page.locator(
    'button:has-text("Create Web Service"), button:has-text("Deploy"), button[type="submit"]'
  ).last();

  if (await deployBtn.isVisible({ timeout: 10_000 }).catch(() => false)) {
    await deployBtn.click();
    console.log('⏳ Deploy iniciado...');
    await page.waitForTimeout(5000);
  }
}

async function agregarEnvVar(page, key, value) {
  try {
    // Buscar botón "Add Environment Variable" o el último campo vacío
    const addBtn = page.locator('button:has-text("Add"), button:has-text("+ Add")').last();
    if (await addBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await addBtn.click();
      await page.waitForTimeout(500);
    }

    // Rellenar key y value en el último par de inputs
    const keyInputs = page.locator('input[placeholder*="key" i], input[name*="key"]');
    const valueInputs = page.locator('input[placeholder*="value" i], input[name*="value"]');

    const count = await keyInputs.count();
    if (count > 0) {
      await keyInputs.nth(count - 1).fill(key);
      await valueInputs.nth(count - 1).fill(value);
    }
  } catch {
    // Ignorar si falla una variable individual
  }
}

module.exports = { deployToRender };
