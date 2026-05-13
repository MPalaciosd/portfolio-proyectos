const express = require('express');
const router = express.Router();
const { TrainingExample } = require('../../db/database');

// GET /api/training — listar todos los ejemplos
router.get('/', async (req, res) => {
  try {
    const { categoria, activo } = req.query;
    const filter = {};
    if (categoria) filter.categoria = categoria;
    if (activo !== undefined) filter.activo = activo === 'true';

    const examples = await TrainingExample.find(filter)
      .sort({ createdAt: -1 })
      .lean();
    res.json({ examples, total: examples.length });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/training/categorias — lista de categorías únicas
router.get('/categorias', async (req, res) => {
  try {
    const cats = await TrainingExample.distinct('categoria');
    res.json({ categorias: cats });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/training — crear ejemplo
router.post('/', async (req, res) => {
  try {
    const { input, output, categoria = 'general', notas = '' } = req.body;
    if (!input?.trim() || !output?.trim()) {
      return res.status(400).json({ error: 'input y output son obligatorios.' });
    }
    const example = await TrainingExample.create({
      input: input.trim(),
      output: output.trim(),
      categoria: categoria.trim() || 'general',
      notas: notas.trim(),
    });
    res.status(201).json({ ok: true, example });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// PUT /api/training/:id — editar ejemplo
router.put('/:id', async (req, res) => {
  try {
    const { input, output, categoria, notas, activo } = req.body;
    const update = {};
    if (input !== undefined) update.input = input.trim();
    if (output !== undefined) update.output = output.trim();
    if (categoria !== undefined) update.categoria = categoria.trim();
    if (notas !== undefined) update.notas = notas.trim();
    if (activo !== undefined) update.activo = activo;

    const example = await TrainingExample.findByIdAndUpdate(
      req.params.id, update, { new: true }
    );
    if (!example) return res.status(404).json({ error: 'Ejemplo no encontrado.' });
    res.json({ ok: true, example });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// DELETE /api/training/:id — borrar ejemplo
router.delete('/:id', async (req, res) => {
  try {
    await TrainingExample.findByIdAndDelete(req.params.id);
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
