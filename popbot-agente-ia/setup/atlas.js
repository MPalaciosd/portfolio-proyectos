/**
 * Automatización MongoDB Atlas con Playwright
 * Abre el navegador, espera login del usuario, crea cluster M0 gratis y extrae la URI
 */

const { chromium } = require('playwright');

const ATLAS_URL = 'https://cloud.mongodb.com/';
const CLUSTER_NAME = 'barbershop-cluster';
const DB_NAME = 'barbershop';

async function setupMongoAtlas() {
  console.log('\n📦 Abriendo MongoDB Atlas...');
  console.log('   ➜ Inicia sesión (o crea cuenta gratuita) en el navegador\n');

  const browser = await chromium.launch({
    headless: false,
    args: ['--start-maximized'],
  });

  const context = await browser.newContext({ viewport: null });
  const page = await context.newPage();

  await page.goto(ATLAS_URL, { waitUntil: 'domcontentloaded' });

  // ── Esperar a que el usuario inicie sesión (dashboard visible) ───────────
  console.log('⏳ Esperando que inicies sesión en MongoDB Atlas...');
  console.log('   (El script continuará automáticamente)\n');

  await page.waitForURL(/cloud\.mongodb\.com\/(v2|#\/org)/, {
    timeout: 300_000, // 5 minutos para que el usuario haga login
  });

  // Esperar a que cargue el dashboard
  await page.waitForLoadState('networkidle', { timeout: 30_000 }).catch(() => {});
  await page.waitForTimeout(2000);

  console.log('✅ Sesión detectada. Buscando clusters...');

  // ── Navegar a la sección de clusters ────────────────────────────────────
  const currentUrl = page.url();

  // Ir a la página principal de clusters
  if (!currentUrl.includes('/clusters')) {
    // Buscar el link de "Database" o "Clusters" en el menú
    const dbLink = page.locator('a[href*="/clusters"], a:has-text("Database"), nav a:has-text("Clusters")').first();
    if (await dbLink.isVisible({ timeout: 5000 }).catch(() => false)) {
      await dbLink.click();
      await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
    }
  }

  await page.waitForTimeout(2000);

  // ── Verificar si ya existe un cluster ───────────────────────────────────
  const existingCluster = await page.locator(`text="${CLUSTER_NAME}"`).isVisible({ timeout: 5000 }).catch(() => false);

  if (existingCluster) {
    console.log(`✅ Cluster "${CLUSTER_NAME}" ya existe. Obteniendo URI de conexión...`);
    return await getConnectionString(page, browser, CLUSTER_NAME, DB_NAME);
  }

  // ── Crear nuevo cluster gratuito ─────────────────────────────────────────
  console.log('🔧 No se encontró cluster. Creando cluster M0 gratuito...');

  // Buscar botón "Create" o "Build a Database" o "Create cluster"
  const createBtn = page.locator(
    'button:has-text("Create"), button:has-text("Build a Database"), a:has-text("Create"), button:has-text("+ Create")'
  ).first();

  if (await createBtn.isVisible({ timeout: 10_000 }).catch(() => false)) {
    await createBtn.click();
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
    await page.waitForTimeout(2000);
  }

  // ── Seleccionar plan M0 (Free) ───────────────────────────────────────────
  const freeOption = page.locator('text="M0", text="Free", [data-testid="cluster-type-free"]').first();
  if (await freeOption.isVisible({ timeout: 10_000 }).catch(() => false)) {
    await freeOption.click();
    await page.waitForTimeout(1000);
  }

  // ── Nombrar el cluster ────────────────────────────────────────────────────
  const nameInput = page.locator('input[name*="cluster"], input[placeholder*="luster"], input[id*="cluster"]').first();
  if (await nameInput.isVisible({ timeout: 5000 }).catch(() => false)) {
    await nameInput.clear();
    await nameInput.type(CLUSTER_NAME);
  }

  // ── Crear el cluster ──────────────────────────────────────────────────────
  const submitBtn = page.locator(
    'button:has-text("Create Cluster"), button:has-text("Create Deployment"), button[type="submit"]'
  ).last();

  if (await submitBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
    await submitBtn.click();
    console.log('⏳ Creando cluster... (puede tardar 1-3 minutos)\n');
  }

  // ── Esperar creación del cluster ──────────────────────────────────────────
  // Atlas mostrará un modal de "Security Quickstart" o irá al dashboard
  await page.waitForTimeout(3000);

  // Manejar el modal de Security Quickstart si aparece
  await handleSecurityQuickstart(page);

  // Esperar a que el cluster esté listo (botón Connect disponible)
  console.log('⏳ Esperando que el cluster esté activo...');

  try {
    await page.waitForSelector(
      'button:has-text("Connect"), [data-testid="connect-button"]',
      { timeout: 300_000 } // hasta 5 minutos
    );
    console.log('✅ Cluster listo!');
  } catch {
    console.log('⚠️  El cluster puede tardar unos minutos más. Continuando...');
  }

  return await getConnectionString(page, browser, CLUSTER_NAME, DB_NAME);
}

async function handleSecurityQuickstart(page) {
  await page.waitForTimeout(2000);

  // Si hay un formulario de usuario/contraseña de database
  const userInput = page.locator('input[name*="username"], input[placeholder*="username"], input[id*="username"]').first();

  if (await userInput.isVisible({ timeout: 8000 }).catch(() => false)) {
    console.log('🔐 Configurando usuario de base de datos...');

    const dbUser = 'barbershop_admin';
    const dbPass = generatePassword();

    await userInput.clear();
    await userInput.type(dbUser);

    const passInput = page.locator('input[type="password"], input[name*="password"]').first();
    if (await passInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      await passInput.clear();
      await passInput.type(dbPass);
    }

    // Guardar usuario y contraseña para usarlos después
    page._dbUser = dbUser;
    page._dbPass = dbPass;

    // Click en "Create User" o "Add User"
    const createUserBtn = page.locator('button:has-text("Create User"), button:has-text("Add User")').first();
    if (await createUserBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await createUserBtn.click();
      await page.waitForTimeout(2000);
    }
  }

  // Si pide IP de acceso — añadir 0.0.0.0/0 (todas las IPs) para que funcione en la nube
  const ipInput = page.locator('input[placeholder*="IP"], input[name*="ip"]').first();
  if (await ipInput.isVisible({ timeout: 5000 }).catch(() => false)) {
    console.log('🌐 Configurando acceso desde cualquier IP (necesario para hosting en la nube)...');

    // Buscar "Allow Access from Anywhere"
    const anywhereBtn = page.locator('button:has-text("Allow Access from Anywhere"), a:has-text("Allow Access from Anywhere")').first();
    if (await anywhereBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await anywhereBtn.click();
    } else {
      await ipInput.clear();
      await ipInput.type('0.0.0.0/0');
      const addIpBtn = page.locator('button:has-text("Add Entry"), button:has-text("Confirm")').first();
      if (await addIpBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
        await addIpBtn.click();
      }
    }
    await page.waitForTimeout(2000);
  }

  // Finalizar quickstart
  const finishBtn = page.locator('button:has-text("Finish"), button:has-text("Done"), button:has-text("Go to Database")').first();
  if (await finishBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
    await finishBtn.click();
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
  }
}

async function getConnectionString(page, browser, clusterName, dbName) {
  try {
    // Buscar el botón "Connect" del cluster
    const connectBtn = page.locator(
      `[data-testid="connect-button"], button:has-text("Connect")`
    ).first();

    await connectBtn.waitFor({ state: 'visible', timeout: 30_000 });
    await connectBtn.click();
    await page.waitForTimeout(2000);

    // Seleccionar "Drivers" (Connect your application)
    const driversOption = page.locator(
      'a:has-text("Drivers"), button:has-text("Drivers"), [data-testid*="driver"]'
    ).first();

    if (await driversOption.isVisible({ timeout: 10_000 }).catch(() => false)) {
      await driversOption.click();
      await page.waitForTimeout(2000);
    }

    // Extraer la connection string
    const connStringEl = page.locator('code, pre, input[value*="mongodb+srv"]').first();
    const connString = await connStringEl.textContent({ timeout: 10_000 }).catch(() => '');

    if (connString && connString.includes('mongodb+srv')) {
      const cleanUri = connString.trim();
      const finalUri = cleanUri.replace('<password>', page._dbPass || '<PASSWORD>').replace('<db_name>', dbName);

      await browser.close();
      return {
        uri: finalUri,
        user: page._dbUser,
        pass: page._dbPass,
        clusterName,
      };
    }

    // Si no encontró la string, mostrar instrucciones manuales
    console.log('\n⚠️  No se pudo extraer automáticamente la URI.');
    console.log('   Por favor, en el navegador que está abierto:');
    console.log('   1. Haz clic en "Connect" en tu cluster');
    console.log('   2. Selecciona "Drivers"');
    console.log('   3. Copia la URI que empieza con mongodb+srv://');
    console.log('\n   Pégala aquí cuando la tengas:');

    // Esperar input del usuario por consola
    const uri = await waitForUserInput('   URI de MongoDB: ');
    await browser.close();
    return { uri: uri.trim(), clusterName };

  } catch (err) {
    console.error('[Atlas] Error al obtener connection string:', err.message);
    await browser.close();
    throw err;
  }
}

function generatePassword() {
  const chars = 'ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789!@#$';
  let pass = '';
  for (let i = 0; i < 20; i++) {
    pass += chars[Math.floor(Math.random() * chars.length)];
  }
  return pass;
}

function waitForUserInput(prompt) {
  const readline = require('readline');
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise(resolve => {
    rl.question(prompt, answer => {
      rl.close();
      resolve(answer);
    });
  });
}

module.exports = { setupMongoAtlas };
