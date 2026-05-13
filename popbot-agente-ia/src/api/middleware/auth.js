const jwt = require('jsonwebtoken');

const JWT_SECRET = process.env.JWT_SECRET || 'popbot-secret-dev-change-in-prod';
const JWT_EXPIRES = '90d'; // sesión de 90 días — "siempre iniciada"

function signToken(userId) {
  return jwt.sign({ id: userId }, JWT_SECRET, { expiresIn: JWT_EXPIRES });
}

// Middleware — protege rutas que requieren login
function requireAuth(req, res, next) {
  const header = req.headers.authorization || '';
  const token = header.startsWith('Bearer ') ? header.slice(7) : null;

  if (!token) return res.status(401).json({ error: 'No autenticado.' });

  try {
    const payload = jwt.verify(token, JWT_SECRET);
    req.userId = payload.id;
    next();
  } catch {
    res.status(401).json({ error: 'Token inválido o expirado.' });
  }
}

module.exports = { signToken, requireAuth };
