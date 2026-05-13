const express = require('express');
const router = express.Router();
const { processMessage } = require('../../ai/agentEngine');
const conversationService = require('../../services/conversationService');

/**
 * POST /api/chat
 * Body: { message: string, sessionId: string }
 */
router.post('/', async (req, res) => {
  const { message, sessionId } = req.body;

  if (!message || !sessionId) {
    return res.status(400).json({ error: 'message y sessionId son requeridos.' });
  }

  try {
    const response = await processMessage(message, 'web', sessionId);
    res.json({ response });
  } catch (err) {
    console.error('[API Chat] Error:', err.message);
    res.status(500).json({ error: 'Error interno del servidor.' });
  }
});

/**
 * GET /api/chat/history/:sessionId
 * Devuelve el historial de mensajes de una sesión web.
 */
router.get('/history/:sessionId', (req, res) => {
  const { sessionId } = req.params;
  const conversation = conversationService.getOrCreateConversation('web', sessionId);
  const history = conversationService.getHistory(conversation.id);
  res.json({ history });
});

module.exports = router;
