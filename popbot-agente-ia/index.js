require('dotenv').config();

const { connectDB } = require('./src/db/database');
const { startServer, getApp } = require('./src/api/server');
const { startKeepAlive } = require('./src/keepAlive');
const config = require('./src/config');

if (!config.groq.apiKey) {
  console.error('❌ ERROR: GROQ_API_KEY no configurada en .env');
  process.exit(1);
}

async function main() {
  console.log(`\n🔱 ${config.shop.name} — pop BOT`);
  console.log('─'.repeat(45));

  // MongoDB conecta en background — no bloquea el arranque
  connectDB();
  startServer();
  startKeepAlive(config.server.port);

  console.log('\n✅ pop BOT operativo.\n');
}

main().catch(err => {
  console.error('[FATAL] Error al iniciar:', err.message);
  process.exit(1);
});

process.on('uncaughtException', (err) => {
  console.error('[ERROR] Excepción no capturada:', err.message);
  if (err.code === 'EADDRINUSE') process.exit(1);
});

process.on('unhandledRejection', (reason) => {
  console.error('[ERROR] Promesa rechazada:', reason);
});

async function shutdown(signal) {
  console.log(`\n[Shutdown] ${signal} — cerrando limpiamente...`);
  const mongoose = require('mongoose');
  await mongoose.connection.close();
  process.exit(0);
}

process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));
