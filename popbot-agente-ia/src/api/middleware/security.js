const rateLimit = require('express-rate-limit');

// ── Rate Limiting ─────────────────────────────────────────────────────────────
// 30 requests/minuto por IP (ajustable por ruta)
const defaultLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: 30,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: 'Demasiadas solicitudes. Intenta de nuevo en un minuto.' },
});

// Más estricto para endpoints de pago
const stripeLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: 10,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: 'Demasiadas solicitudes de pago. Intenta de nuevo en un minuto.' },
});

// ── Input Sanitization ────────────────────────────────────────────────────────
function sanitizeInput(input, maxLength = 2000) {
  if (typeof input !== 'string') return input;
  return input.trim().substring(0, maxLength).replace(/<[^>]*>/g, '');
}

function sanitizeMiddleware(req, res, next) {
  if (req.body && typeof req.body === 'object') {
    for (const key of Object.keys(req.body)) {
      if (typeof req.body[key] === 'string') {
        req.body[key] = sanitizeInput(req.body[key]);
      }
    }
  }
  next();
}

module.exports = { defaultLimiter, stripeLimiter, sanitizeMiddleware };
