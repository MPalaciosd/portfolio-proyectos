const { Resend } = require('resend');

// Se instancia con un placeholder si no hay clave — send() lo detecta y loguea sin romper
const resend = new Resend(process.env.RESEND_API_KEY || 'placeholder');
const FROM = process.env.EMAIL_FROM || 'noreply@popbot.app';
const APP_NAME = process.env.SHOP_NAME || 'pop BOT';

// Helper para enviar sin romper si Resend no está configurado
async function send(to, subject, html) {
  if (!process.env.RESEND_API_KEY) {
    console.warn(`[Email] RESEND_API_KEY no configurada. Email no enviado a ${to}: ${subject}`);
    return;
  }
  try {
    const { error } = await resend.emails.send({ from: FROM, to, subject, html });
    if (error) console.error('[Email] Error Resend:', error);
    else console.log(`[Email] Enviado a ${to}: ${subject}`);
  } catch (err) {
    console.error('[Email] Error:', err.message);
  }
}

// ── Templates ─────────────────────────────────────────────────────────────────

function baseTemplate(content) {
  return `
<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; margin: 0; padding: 20px; }
  .container { max-width: 600px; margin: 0 auto; background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
  .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 32px; text-align: center; }
  .header h1 { color: #fff; margin: 0; font-size: 28px; }
  .body { padding: 32px; color: #333; line-height: 1.6; }
  .btn { display: inline-block; background: #667eea; color: #fff; text-decoration: none; padding: 12px 28px; border-radius: 8px; font-weight: 600; margin: 16px 0; }
  .footer { background: #f9f9f9; padding: 16px 32px; text-align: center; color: #888; font-size: 12px; }
  .badge { display: inline-block; background: #e8f4fd; color: #667eea; padding: 4px 12px; border-radius: 20px; font-weight: 600; }
</style></head>
<body><div class="container">
  <div class="header"><h1>${APP_NAME}</h1></div>
  <div class="body">${content}</div>
  <div class="footer">© ${new Date().getFullYear()} ${APP_NAME} · <a href="${process.env.FRONTEND_URL}/dashboard">Mi cuenta</a></div>
</div></body></html>`;
}

// ── Email de bienvenida ───────────────────────────────────────────────────────
async function sendWelcome(to, name) {
  const html = baseTemplate(`
    <h2>¡Bienvenido/a a ${APP_NAME}, ${name}! 👋</h2>
    <p>Estamos encantados de tenerte. Tu cuenta está lista y puedes empezar a usar el bot ahora mismo.</p>
    <p>Con el plan <span class="badge">Free</span> tienes acceso básico. Cuando quieras más potencia, echa un vistazo a nuestros planes.</p>
    <a class="btn" href="${process.env.FRONTEND_URL}/pricing">Ver planes</a>
    <p>Si tienes alguna duda, responde a este email y te ayudamos.</p>
  `);
  await send(to, `¡Bienvenido/a a ${APP_NAME}!`, html);
}

// ── Email de confirmación de pago ─────────────────────────────────────────────
async function sendPaymentConfirmation(to, name, planName, amount) {
  const html = baseTemplate(`
    <h2>Pago confirmado ✅</h2>
    <p>Hola ${name}, hemos recibido tu pago correctamente.</p>
    <table style="width:100%;border-collapse:collapse;margin:16px 0;">
      <tr><td style="padding:8px;border-bottom:1px solid #eee;color:#666;">Plan</td><td style="padding:8px;border-bottom:1px solid #eee;font-weight:600;">${planName}</td></tr>
      <tr><td style="padding:8px;color:#666;">Importe</td><td style="padding:8px;font-weight:600;">$${amount.toFixed(2)}/mes</td></tr>
    </table>
    <p>Tus créditos ya están disponibles en tu cuenta.</p>
    <a class="btn" href="${process.env.FRONTEND_URL}/dashboard">Ver mi dashboard</a>
  `);
  await send(to, `Confirmación de pago — ${planName}`, html);
}

// ── Email de pago fallido ─────────────────────────────────────────────────────
async function sendPaymentFailed(to, name) {
  const html = baseTemplate(`
    <h2>Problema con tu pago ⚠️</h2>
    <p>Hola ${name}, no hemos podido procesar el pago de tu suscripción.</p>
    <p>Para evitar la interrupción del servicio, actualiza tu método de pago.</p>
    <a class="btn" href="${process.env.FRONTEND_URL}/api/stripe/portal">Actualizar pago</a>
    <p>Si necesitas ayuda, contáctanos respondiendo a este email.</p>
  `);
  await send(to, 'Acción requerida: problema con tu pago', html);
}

// ── Email de créditos bajos ───────────────────────────────────────────────────
async function sendLowCredits(to, name, balance, planName) {
  const html = baseTemplate(`
    <h2>Tus créditos están bajando 📉</h2>
    <p>Hola ${name}, te quedan solo <strong>${balance} créditos</strong> en tu plan ${planName}.</p>
    <p>Cuando lleguen a 0 no podrás usar el bot hasta el próximo ciclo de facturación.</p>
    <a class="btn" href="${process.env.FRONTEND_URL}/pricing">Subir de plan</a>
    <p>O puedes ganar créditos gratis viendo anuncios desde tu dashboard.</p>
  `);
  await send(to, `Créditos bajos — te quedan ${balance}`, html);
}

// ── Email de renovación ───────────────────────────────────────────────────────
async function sendRenewal(to, name, planName, creditsAdded) {
  const html = baseTemplate(`
    <h2>Suscripción renovada 🔄</h2>
    <p>Hola ${name}, tu plan <strong>${planName}</strong> se ha renovado correctamente.</p>
    <p>Hemos añadido <strong>${creditsAdded} créditos</strong> a tu cuenta.</p>
    <a class="btn" href="${process.env.FRONTEND_URL}/dashboard">Ver mi saldo</a>
  `);
  await send(to, `Renovación exitosa — ${planName}`, html);
}

// ── Email de cancelación ──────────────────────────────────────────────────────
async function sendCancellationConfirmation(to, name) {
  const html = baseTemplate(`
    <h2>Suscripción cancelada</h2>
    <p>Hola ${name}, hemos cancelado tu suscripción como solicitaste.</p>
    <p>Seguirás teniendo acceso hasta el final del período actual. Después pasarás al plan Free.</p>
    <p>Lamentamos verte ir. Si fue por algún problema, cuéntanos y lo resolvemos.</p>
    <a class="btn" href="${process.env.FRONTEND_URL}/pricing">Volver a suscribirme</a>
  `);
  await send(to, 'Tu suscripción ha sido cancelada', html);
}

module.exports = {
  sendWelcome,
  sendPaymentConfirmation,
  sendPaymentFailed,
  sendLowCredits,
  sendRenewal,
  sendCancellationConfirmation,
};
