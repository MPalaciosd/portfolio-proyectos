const express = require('express');
const router = express.Router();
const { User } = require('../../db/database');
const { signToken, requireAuth } = require('../middleware/auth');

// POST /api/auth/register
router.post('/register', async (req, res) => {
  const { email, password, nombre } = req.body;
  if (!email || !password) return res.status(400).json({ error: 'Email y contraseña requeridos.' });
  if (password.length < 6) return res.status(400).json({ error: 'La contraseña debe tener al menos 6 caracteres.' });

  try {
    const exists = await User.findOne({ email });
    if (exists) return res.status(409).json({ error: 'Ya existe una cuenta con ese email.' });

    const user = await User.create({ email, password, nombre: nombre || email.split('@')[0] });
    const token = signToken(user._id);
    res.status(201).json({ token, user: { id: user._id, email: user.email, nombre: user.nombre, botConfig: user.botConfig } });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/auth/login
router.post('/login', async (req, res) => {
  const { email, password } = req.body;
  if (!email || !password) return res.status(400).json({ error: 'Email y contraseña requeridos.' });

  try {
    const user = await User.findOne({ email });
    if (!user || !(await user.checkPassword(password))) {
      return res.status(401).json({ error: 'Email o contraseña incorrectos.' });
    }
    const token = signToken(user._id);
    res.json({ token, user: { id: user._id, email: user.email, nombre: user.nombre, botConfig: user.botConfig } });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/auth/me — obtener perfil del usuario logueado
router.get('/me', requireAuth, async (req, res) => {
  try {
    const user = await User.findById(req.userId).select('-password');
    if (!user) return res.status(404).json({ error: 'Usuario no encontrado.' });
    res.json({ user });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// PUT /api/auth/bot-config — guardar personalización del bot del usuario
router.put('/bot-config', requireAuth, async (req, res) => {
  try {
    const { nombre, personalidad, contexto } = req.body;
    const update = {};
    if (nombre !== undefined) update['botConfig.nombre'] = nombre;
    if (personalidad !== undefined) update['botConfig.personalidad'] = personalidad;
    if (contexto !== undefined) update['botConfig.contexto'] = contexto;

    const user = await User.findByIdAndUpdate(req.userId, update, { new: true }).select('-password');
    res.json({ ok: true, botConfig: user.botConfig });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// PUT /api/auth/password — cambiar contraseña
router.put('/password', requireAuth, async (req, res) => {
  const { current, nueva } = req.body;
  if (!current || !nueva) return res.status(400).json({ error: 'Contraseña actual y nueva requeridas.' });
  if (nueva.length < 6) return res.status(400).json({ error: 'La nueva contraseña debe tener al menos 6 caracteres.' });

  try {
    const user = await User.findById(req.userId);
    if (!(await user.checkPassword(current))) {
      return res.status(401).json({ error: 'Contraseña actual incorrecta.' });
    }
    user.password = nueva;
    await user.save();
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
