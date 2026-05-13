const express = require('express');
const router = express.Router();
const appointmentService = require('../../services/appointmentService');
const availabilityService = require('../../services/availabilityService');
const clientService = require('../../services/clientService');
const conversationService = require('../../services/conversationService');
const config = require('../../config');

// GET /api/appointments — próximas citas
router.get('/', async (req, res) => {
  try {
    const appointments = await appointmentService.getUpcomingAppointments(100);
    res.json({ appointments });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/appointments/services
router.get('/services', (req, res) => {
  res.json({ services: config.services });
});

// GET /api/appointments/clients
router.get('/clients', async (req, res) => {
  try {
    const clients = await clientService.listAll();
    res.json({ clients });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/appointments/conversations
router.get('/conversations', async (req, res) => {
  try {
    const conversations = await conversationService.listConversations(50);
    res.json({ conversations });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/appointments/availability
router.get('/availability', async (req, res) => {
  try {
    const { date, service } = req.query;
    if (!date || !service) return res.status(400).json({ error: 'date y service requeridos.' });
    const svc = config.services[service];
    if (!svc) return res.status(400).json({ error: `Servicio '${service}' no encontrado.` });
    const slots = await availabilityService.getAvailableSlots(date, svc.duration);
    res.json({ date, service, slots });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/appointments/date/:date
router.get('/date/:date', async (req, res) => {
  try {
    const appointments = await appointmentService.getAppointmentsByDate(req.params.date);
    res.json({ date: req.params.date, appointments });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// DELETE /api/appointments/:id — cancelar cita
router.delete('/:id', async (req, res) => {
  try {
    const result = await appointmentService.cancelAppointment(req.params.id);
    if (!result.success) return res.status(400).json({ error: result.error });
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
