const { Appointment } = require('../db/database');
const config = require('../config');
const { isSlotAvailable } = require('./availabilityService');

function timeToMinutes(t) {
  const [h, m] = t.split(':').map(Number);
  return h * 60 + m;
}
function minutesToTime(m) {
  return `${String(Math.floor(m / 60)).padStart(2,'0')}:${String(m % 60).padStart(2,'0')}`;
}

async function createAppointment({ clientId, serviceKey, datetime }) {
  const service = config.services[serviceKey];
  if (!service) return { success: false, error: `Servicio '${serviceKey}' no encontrado.` };

  const parts = datetime.trim().split(' ');
  if (parts.length !== 2) return { success: false, error: 'Formato incorrecto. Usa YYYY-MM-DD HH:MM' };
  const [dateStr, timeStr] = parts;

  const available = await isSlotAvailable(dateStr, timeStr, service.duration);
  if (!available) return { success: false, error: 'Ese horario ya está ocupado. Por favor elige otro.' };

  const endMin  = timeToMinutes(timeStr) + service.duration;
  const startDt = `${dateStr} ${timeStr}:00`;
  const endDt   = `${dateStr} ${minutesToTime(endMin)}:00`;

  const appointment = (await Appointment.create({
    client_id:    clientId,
    service_key:  serviceKey,
    service_name: service.name,
    duration:     service.duration,
    start_time:   startDt,
    end_time:     endDt,
    status:       'confirmed',
    notes:        null,
  })).toObject();

  return { success: true, appointment };
}

async function cancelAppointment(appointmentId) {
  let apt;
  try { apt = await Appointment.findById(appointmentId).lean(); } catch { apt = null; }
  if (!apt) return { success: false, error: 'Cita no encontrada.' };
  if (apt.status === 'cancelled') return { success: false, error: 'La cita ya está cancelada.' };

  await Appointment.findByIdAndUpdate(appointmentId, { status: 'cancelled' });
  return { success: true };
}

async function rescheduleAppointment(appointmentId, newDatetime) {
  let apt;
  try { apt = await Appointment.findById(appointmentId).lean(); } catch { apt = null; }
  if (!apt) return { success: false, error: 'Cita no encontrada.' };
  if (apt.status === 'cancelled') return { success: false, error: 'No se puede reprogramar una cita cancelada.' };

  const parts = newDatetime.trim().split(' ');
  if (parts.length !== 2) return { success: false, error: 'Formato incorrecto. Usa YYYY-MM-DD HH:MM' };
  const [dateStr, timeStr] = parts;

  const available = await isSlotAvailable(dateStr, timeStr, apt.duration, appointmentId);
  if (!available) return { success: false, error: 'Ese nuevo horario ya está ocupado.' };

  const endMin  = timeToMinutes(timeStr) + apt.duration;
  const startDt = `${dateStr} ${timeStr}:00`;
  const endDt   = `${dateStr} ${minutesToTime(endMin)}:00`;

  const updated = await Appointment.findByIdAndUpdate(
    appointmentId,
    { start_time: startDt, end_time: endDt },
    { new: true }
  ).lean();

  return { success: true, appointment: updated };
}

async function getClientAppointments(clientId, statusFilter = null) {
  const query = { client_id: clientId };
  if (statusFilter) query.status = statusFilter;
  return await Appointment.find(query).sort({ start_time: 1 }).lean();
}

async function getUpcomingAppointments(limit = 100) {
  const now = new Date().toISOString().replace('T', ' ').slice(0, 19);
  const apts = await Appointment.find({
    status: 'confirmed',
    start_time: { $gte: now },
  }).sort({ start_time: 1 }).limit(limit).lean();

  return Promise.all(
    apts.map(async (a) => {
      const client = await require('./clientService').findById(a.client_id);
      return { ...a, client_name: client?.name || '—', client_phone: client?.phone || null };
    })
  );
}

async function getAppointmentsByDate(dateStr) {
  const dayStart = `${dateStr} 00:00:00`;
  const dayEnd   = `${dateStr} 23:59:59`;

  const apts = await Appointment.find({
    status: 'confirmed',
    start_time: { $gte: dayStart, $lte: dayEnd },
  }).sort({ start_time: 1 }).lean();

  return Promise.all(
    apts.map(async (a) => {
      const client = await require('./clientService').findById(a.client_id);
      return { ...a, client_name: client?.name || '—', client_phone: client?.phone || null };
    })
  );
}

async function getAppointmentById(id) {
  try { return await Appointment.findById(id).lean(); } catch { return null; }
}

module.exports = {
  createAppointment,
  cancelAppointment,
  rescheduleAppointment,
  getClientAppointments,
  getUpcomingAppointments,
  getAppointmentsByDate,
  getAppointmentById,
};
