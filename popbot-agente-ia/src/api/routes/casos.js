const express = require('express');
const router = express.Router();
const fs = require('fs');
const path = require('path');
const { invalidateCasosCache, loadCasos } = require('../../ai/agentEngine');

const CASOS_PATH = path.join(__dirname, '../../../config/casos.json');

// GET /api/casos — devuelve el JSON completo
router.get('/', (req, res) => {
  try {
    res.json(loadCasos());
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// PUT /api/casos — reemplaza el JSON completo (desde el editor visual)
router.put('/', (req, res) => {
  try {
    const data = req.body;
    if (!data || !Array.isArray(data.casos)) {
      return res.status(400).json({ error: 'Formato inválido. Se requiere { bot, instrucciones_globales, casos }.' });
    }
    fs.writeFileSync(CASOS_PATH, JSON.stringify(data, null, 2), 'utf8');
    invalidateCasosCache();
    res.json({ ok: true, message: 'Casos guardados. El bot los aplicará en el próximo mensaje.' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/casos — añade un caso nuevo
router.post('/', (req, res) => {
  try {
    const { nombre, descripcion, instruccion, ejemplos = [] } = req.body;
    if (!nombre || !instruccion) {
      return res.status(400).json({ error: 'nombre e instruccion son requeridos.' });
    }
    const datos = loadCasos();
    const nuevoCaso = {
      id: nombre.toLowerCase().replace(/\s+/g, '_') + '_' + Date.now(),
      nombre,
      descripcion: descripcion || '',
      instruccion,
      ejemplos,
    };
    datos.casos.push(nuevoCaso);
    fs.writeFileSync(CASOS_PATH, JSON.stringify(datos, null, 2), 'utf8');
    invalidateCasosCache();
    res.status(201).json({ ok: true, caso: nuevoCaso });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// DELETE /api/casos/:id — borra un caso por id
router.delete('/:id', (req, res) => {
  try {
    const datos = loadCasos();
    const antes = datos.casos.length;
    datos.casos = datos.casos.filter(c => c.id !== req.params.id);
    if (datos.casos.length === antes) {
      return res.status(404).json({ error: 'Caso no encontrado.' });
    }
    fs.writeFileSync(CASOS_PATH, JSON.stringify(datos, null, 2), 'utf8');
    invalidateCasosCache();
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
