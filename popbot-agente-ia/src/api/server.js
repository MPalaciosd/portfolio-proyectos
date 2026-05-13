const express = require('express');
const http = require('http');
const helmet = require('helmet');
const cors = require('cors');
const { Server } = require('socket.io');
const path = require('path');
const config = require('../config');
const { processMessage } = require('../ai/agentEngine');
const { defaultLimiter, sanitizeMiddleware } = require('./middleware/security');

const app = express();
const server = http.createServer(app);

// Dominios permitidos (configurar en variable de entorno en producción)
const ALLOWED_ORIGINS = (process.env.ALLOWED_ORIGINS || 'http://localhost:3000')
  .split(',')
  .map(o => o.trim());

const io = new Server(server, {
  cors: { origin: ALLOWED_ORIGINS, credentials: true },
});

// ── Middleware de seguridad ───────────────────────────────────────────────────
app.use(helmet());
app.use(cors({
  origin: ALLOWED_ORIGINS,
  methods: ['GET', 'POST', 'PUT', 'DELETE'],
  allowedHeaders: ['Content-Type', 'Authorization'],
  credentials: true,
  maxAge: 86400,
}));

// Webhook de Stripe necesita body raw — va ANTES de express.json()
app.use('/api/stripe/webhook', express.raw({ type: 'application/json' }));

app.use(express.json({ limit: '50kb' }));
app.use(sanitizeMiddleware);
app.use(defaultLimiter);
app.use(express.static(path.join(__dirname, '../../public')));

// ── Health check (evita cold starts en Render) ────────────────────────────────
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString(), uptime: process.uptime() });
});

// ── Rutas API ────────────────────────────────────────────────────────────────
app.use('/api/chat', require('./routes/chat'));
app.use('/api/appointments', require('./routes/appointments'));
app.use('/api/stripe', require('./routes/stripe'));
app.use('/api/credits', require('./routes/credits'));
app.use('/api/casos', require('./routes/casos'));
app.use('/api/training', require('./routes/training'));

// ── Rutas de páginas ─────────────────────────────────────────────────────────
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, '../../public/index.html'));
});
app.get('/admin', (req, res) => {
  res.sendFile(path.join(__dirname, '../../public/admin.html'));
});
app.get('/pricing', (req, res) => {
  res.sendFile(path.join(__dirname, '../../public/pricing.html'));
});
app.get('/dashboard', (req, res) => {
  res.sendFile(path.join(__dirname, '../../public/dashboard.html'));
});
app.get('/training', (req, res) => {
  res.sendFile(path.join(__dirname, '../../public/training.html'));
});

// ── Socket.io — Chat en tiempo real ──────────────────────────────────────────
io.on('connection', (socket) => {
  const sessionId = `web_${socket.id}`;
  console.log(`[Socket.io] Cliente conectado: ${sessionId}`);

  socket.on('message', async (data) => {
    const userMessage = typeof data === 'string' ? data : data.message;
    if (!userMessage?.trim()) return;

    console.log(`[Socket.io] Mensaje de ${sessionId}: ${userMessage}`);
    socket.emit('user_message', { text: userMessage });

    try {
      socket.emit('typing', true);
      const response = await processMessage(userMessage, 'web', sessionId);
      socket.emit('typing', false);
      socket.emit('bot_message', { text: response });
    } catch (err) {
      console.error('[Socket.io] Error:', err.message);
      socket.emit('typing', false);
      socket.emit('bot_message', {
        text: 'Lo siento, tuve un problema técnico. ¿Puedes repetir tu mensaje?',
      });
    }
  });

  socket.on('disconnect', () => {
    console.log(`[Socket.io] Cliente desconectado: ${sessionId}`);
  });
});

// ── Arrancar servidor ────────────────────────────────────────────────────────
function startServer() {
  server.listen(config.server.port, () => {
    console.log(`\n✅ Servidor web iniciado`);
    console.log(`   Chat widget:  http://localhost:${config.server.port}`);
    console.log(`   Panel admin:  http://localhost:${config.server.port}/admin`);
    console.log(`   Pricing:      http://localhost:${config.server.port}/pricing`);
    console.log(`   Dashboard:    http://localhost:${config.server.port}/dashboard`);
    console.log(`   Health check: http://localhost:${config.server.port}/health\n`);
  });
}

module.exports = { startServer, app, io, getApp: () => app };
