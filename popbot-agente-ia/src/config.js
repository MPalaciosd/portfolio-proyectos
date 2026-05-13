require('dotenv').config();

const config = {
  groq: {
    apiKey: process.env.GROQ_API_KEY,
    // llama-4-scout: último modelo de Meta en Groq, mejor soporte tool use (gratis)
    model: 'meta-llama/llama-4-scout-17b-16e-instruct',
  },

  telegram: {
    token: process.env.TELEGRAM_BOT_TOKEN,
  },

  server: {
    port: parseInt(process.env.PORT) || 3000,
  },

  shop: {
    name: process.env.SHOP_NAME || 'Barbería El Maestro',
    assistantName: process.env.ASSISTANT_NAME || 'Alex',
    phone: process.env.SHOP_PHONE || '',
    address: process.env.SHOP_ADDRESS || '',
  },

  schedule: {
    startHour: process.env.BUSINESS_HOURS_START || '10:00',
    endHour: process.env.BUSINESS_HOURS_END || '20:00',
    // 0=Dom,1=Lun,...,6=Sáb
    workingDays: (process.env.WORKING_DAYS || '1,2,3,4,5,6')
      .split(',')
      .map(Number),
    slotInterval: parseInt(process.env.SLOT_INTERVAL) || 30,
  },

  ai: {
    maxHistoryMessages: parseInt(process.env.MAX_HISTORY_MESSAGES) || 20,
  },

  // Catálogo de servicios — edita aquí para añadir/quitar servicios
  services: {
    corte: { name: 'Corte de cabello', duration: 30, price: 15 },
    corte_barba: { name: 'Corte + Barba', duration: 45, price: 22 },
    barba: { name: 'Arreglo de barba', duration: 20, price: 10 },
    afeitado: { name: 'Afeitado clásico', duration: 25, price: 12 },
    tinte: { name: 'Tinte', duration: 90, price: 40 },
    decoloracion: { name: 'Decoloración', duration: 120, price: 60 },
    keratina: { name: 'Keratina', duration: 150, price: 75 },
  },
};

// Pre-calcular minutos para el motor de disponibilidad
config.schedule.startMinutes = (() => {
  const [h, m] = config.schedule.startHour.split(':').map(Number);
  return h * 60 + m;
})();

config.schedule.endMinutes = (() => {
  const [h, m] = config.schedule.endHour.split(':').map(Number);
  return h * 60 + m;
})();

module.exports = config;
