const mongoose = require('mongoose');

// Eventos de calendario del usuario
const eventoSchema = new mongoose.Schema({
  user_id:     { type: String, required: true },
  titulo:      { type: String, required: true },
  fecha:       { type: String, required: true }, // YYYY-MM-DD
  hora_inicio: { type: String, default: null },  // HH:MM
  hora_fin:    { type: String, default: null },
  duracion_min:{ type: Number, default: null },
  tipo:        { type: String, default: 'evento' }, // evento, tarea, entreno, reunion, recordatorio
  notas:       { type: String, default: '' },
  completado:  { type: Boolean, default: false },
  recurrente:  { type: String, default: null }, // 'diario', 'semanal', null
}, { timestamps: true });
eventoSchema.index({ user_id: 1, fecha: 1 });

const Evento = mongoose.model('Evento', eventoSchema);

module.exports = { Evento };
