const express = require('express');
const router = express.Router();
const { Credits, Subscription, PaymentHistory, AdReward, addCredits } = require('../../db/database');

const AD_REWARD_AMOUNT = 5;
const AD_REWARD_DAILY_LIMIT = 10;

// ── GET /api/credits/:clientId ────────────────────────────────────────────────
router.get('/:clientId', async (req, res) => {
  const { clientId } = req.params;
  try {
    const [credits, sub] = await Promise.all([
      Credits.findOne({ client_id: clientId }),
      Subscription.findOne({ client_id: clientId }),
    ]);

    res.json({
      balance: credits?.balance ?? 0,
      total_earned: credits?.total_earned ?? 0,
      total_consumed: credits?.total_consumed ?? 0,
      plan: sub?.plan ?? 'free',
      subscription_status: sub?.status ?? 'active',
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── GET /api/credits/:clientId/history ───────────────────────────────────────
router.get('/:clientId/history', async (req, res) => {
  const { clientId } = req.params;
  try {
    const history = await PaymentHistory.find({ client_id: clientId })
      .sort({ createdAt: -1 })
      .limit(20);
    res.json({ history });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── POST /api/credits/:clientId/ad-reward ────────────────────────────────────
// Recompensa por ver un anuncio (+5 créditos, máx 10/día)
router.post('/:clientId/ad-reward', async (req, res) => {
  const { clientId } = req.params;

  // Solo usuarios free pueden usar ad-rewards
  const sub = await Subscription.findOne({ client_id: clientId });
  if (sub && sub.plan !== 'free') {
    return res.status(400).json({ error: 'Los anuncios solo están disponibles para usuarios del plan Free.' });
  }

  const today = new Date().toISOString().split('T')[0];

  try {
    const rewardsToday = await AdReward.countDocuments({ client_id: clientId, date: today });
    if (rewardsToday >= AD_REWARD_DAILY_LIMIT) {
      return res.status(429).json({
        error: `Límite diario alcanzado (${AD_REWARD_DAILY_LIMIT} anuncios/día).`,
        next_reset: `${today}T23:59:59Z`,
      });
    }

    await AdReward.create({ client_id: clientId, credits_awarded: AD_REWARD_AMOUNT, date: today });
    const result = await addCredits(clientId, AD_REWARD_AMOUNT, 'ad_reward');

    res.json({
      success: true,
      credits_awarded: AD_REWARD_AMOUNT,
      balance: result.balance,
      rewards_today: rewardsToday + 1,
      remaining_today: AD_REWARD_DAILY_LIMIT - rewardsToday - 1,
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
