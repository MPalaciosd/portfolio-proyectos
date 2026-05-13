const { Appointment } = require('../db/database');
const mongoose = require('mongoose');
const config = require('../config');

async function getAvailableSlots(dateStr, duration) {
  const dayOfWeek = new Date(dateStr + 'T12:00:00').getDay();
  if (!config.schedule.workingDays.includes(dayOfWeek)) return [];

  const dayStart = `${dateStr} 00:00:00`;
  const dayEnd   = `${dateStr} 23:59:59`;

  const dayAppointments = await Appointment.find({
    status: 'confirmed',
    start_time: { $gte: dayStart, $lte: dayEnd },
  }).sort({ start_time: 1 }).lean();

  const { startMinutes, endMinutes, slotInterval } = config.schedule;

  const busyBlocks = dayAppointments.map(apt => ({
    start: timeToMinutes(apt.start_time.slice(11, 16)),
    end:   timeToMinutes(apt.end_time.slice(11, 16)),
  }));

  const available = [];
  let cursor = startMinutes;

  while (cursor + duration <= endMinutes) {
    const slotEnd = cursor + duration;
    const hasConflict = busyBlocks.some(b => cursor < b.end && slotEnd > b.start);
    if (!hasConflict) available.push(minutesToTime(cursor));
    cursor += slotInterval;
  }

  return available;
}

async function getAvailabilityRange(duration, daysAhead = 7) {
  const result = {};
  const today = new Date();
  for (let i = 0; i < daysAhead; i++) {
    const d = new Date(today);
    d.setDate(today.getDate() + i);
    const dateStr = formatDate(d);
    const slots = await getAvailableSlots(dateStr, duration);
    if (slots.length > 0) result[dateStr] = slots;
  }
  return result;
}

async function isSlotAvailable(dateStr, timeStr, duration, excludeId = null) {
  const startDt = `${dateStr} ${timeStr}:00`;
  const endMin  = timeToMinutes(timeStr) + duration;
  const endDt   = `${dateStr} ${minutesToTime(endMin)}:00`;

  const query = {
    status: 'confirmed',
    start_time: { $lt: endDt },
    end_time:   { $gt: startDt },
  };
  if (excludeId) {
    try {
      query._id = { $ne: new mongoose.Types.ObjectId(excludeId) };
    } catch {
      // id inválido, sin exclusión
    }
  }

  const conflict = await Appointment.findOne(query).lean();
  return !conflict;
}

function timeToMinutes(t) {
  const [h, m] = t.split(':').map(Number);
  return h * 60 + m;
}
function minutesToTime(m) {
  return `${String(Math.floor(m / 60)).padStart(2,'0')}:${String(m % 60).padStart(2,'0')}`;
}
function formatDate(d) {
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}

module.exports = { getAvailableSlots, getAvailabilityRange, isSlotAvailable };
