const express = require('express');
const router = express.Router();
const Stripe = require('stripe');
const { Client, Subscription, Credits, PaymentHistory, addCredits, PLAN_CREDITS } = require('../../db/database');
const emailService = require('../../services/emailService');
const { stripeLimiter } = require('../middleware/security');

// Inicialización lazy — solo falla si usas las rutas sin la key configurada
function getStripe() {
  if (!process.env.STRIPE_SECRET_KEY) {
    throw new Error('STRIPE_SECRET_KEY no configurada.');
  }
  return Stripe(process.env.STRIPE_SECRET_KEY);
}

// Planes con sus price IDs de Stripe (configurar en variables de entorno)
const PLANS = {
  basic: {
    name: 'Basic',
    priceId: process.env.STRIPE_PRICE_BASIC,       // price_xxx
    amount: 999,   // $9.99
    credits: PLAN_CREDITS.basic,
  },
  pro: {
    name: 'Pro',
    priceId: process.env.STRIPE_PRICE_PRO,          // price_xxx
    amount: 2999,  // $29.99
    credits: PLAN_CREDITS.pro,
  },
  enterprise: {
    name: 'Enterprise',
    priceId: process.env.STRIPE_PRICE_ENTERPRISE,   // price_xxx
    amount: 9999,  // $99.99
    credits: PLAN_CREDITS.enterprise,
  },
};

// ── POST /api/stripe/create-checkout ─────────────────────────────────────────
// Body: { plan: 'basic'|'pro'|'enterprise', clientId, email }
router.post('/create-checkout', stripeLimiter, async (req, res) => {
  const { plan, clientId, email } = req.body;

  if (!plan || !PLANS[plan]) {
    return res.status(400).json({ error: 'Plan inválido. Usa: basic, pro o enterprise.' });
  }
  if (!clientId || !email) {
    return res.status(400).json({ error: 'clientId y email son requeridos.' });
  }

  try {
    const planConfig = PLANS[plan];

    // Buscar o crear customer en Stripe
    let sub = await Subscription.findOne({ client_id: clientId });
    let customerId = sub?.stripe_customer_id;

    if (!customerId) {
      const customer = await getStripe().customers.create({ email, metadata: { clientId } });
      customerId = customer.id;
    }

    const session = await getStripe().checkout.sessions.create({
      customer: customerId,
      mode: 'subscription',
      payment_method_types: ['card'],
      line_items: [{ price: planConfig.priceId, quantity: 1 }],
      success_url: `${process.env.FRONTEND_URL}/dashboard?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${process.env.FRONTEND_URL}/pricing`,
      metadata: { clientId, plan },
      subscription_data: { metadata: { clientId, plan } },
    });

    res.json({ url: session.url, sessionId: session.id });
  } catch (err) {
    console.error('[Stripe] Error create-checkout:', err.message);
    res.status(500).json({ error: 'Error al crear sesión de pago.' });
  }
});

// ── POST /api/stripe/webhook ──────────────────────────────────────────────────
// Body debe ser raw (configurado en server.js)
router.post('/webhook', async (req, res) => {
  const sig = req.headers['stripe-signature'];
  let event;

  try {
    event = getStripe().webhooks.constructEvent(req.body, sig, process.env.STRIPE_WEBHOOK_SECRET);
  } catch (err) {
    console.error('[Stripe] Webhook signature inválida:', err.message);
    return res.status(400).send(`Webhook Error: ${err.message}`);
  }

  console.log(`[Stripe] Evento recibido: ${event.type}`);

  try {
    switch (event.type) {

      case 'checkout.session.completed': {
        const session = event.data.object;
        const { clientId, plan } = session.metadata;
        const planConfig = PLANS[plan];
        if (!clientId || !planConfig) break;

        // Actualizar suscripción
        await Subscription.findOneAndUpdate(
          { client_id: clientId },
          {
            plan,
            status: 'active',
            stripe_customer_id: session.customer,
            stripe_subscription_id: session.subscription,
          },
          { upsert: true, new: true }
        );

        // Dar créditos del plan
        await addCredits(clientId, planConfig.credits, `plan_${plan}`);

        // Registrar pago
        await PaymentHistory.create({
          client_id: clientId,
          stripe_payment_intent_id: session.payment_intent,
          amount: planConfig.amount,
          status: 'succeeded',
          plan,
          description: `Suscripción ${planConfig.name}`,
        });

        // Enviar email de confirmación
        const client = await Client.findById(clientId);
        if (client?.email) {
          await emailService.sendPaymentConfirmation(client.email, client.name, planConfig.name, planConfig.amount / 100);
        }

        console.log(`[Stripe] Suscripción activada: ${clientId} → plan ${plan}`);
        break;
      }

      case 'invoice.payment_succeeded': {
        const invoice = event.data.object;
        const sub = await Subscription.findOne({ stripe_subscription_id: invoice.subscription });
        if (!sub) break;

        // Renovar créditos al inicio de cada ciclo
        const planConfig = PLANS[sub.plan];
        if (planConfig) {
          await addCredits(sub.client_id, planConfig.credits, `renewal_${sub.plan}`);
          await PaymentHistory.create({
            client_id: sub.client_id,
            stripe_invoice_id: invoice.id,
            amount: invoice.amount_paid,
            status: 'succeeded',
            plan: sub.plan,
            description: `Renovación ${planConfig.name}`,
          });
        }
        break;
      }

      case 'invoice.payment_failed': {
        const invoice = event.data.object;
        const sub = await Subscription.findOne({ stripe_subscription_id: invoice.subscription });
        if (!sub) break;

        await Subscription.findOneAndUpdate(
          { stripe_subscription_id: invoice.subscription },
          { status: 'past_due' }
        );

        const client = await Client.findById(sub.client_id);
        if (client?.email) {
          await emailService.sendPaymentFailed(client.email, client.name);
        }
        break;
      }

      case 'customer.subscription.deleted': {
        const stripeSub = event.data.object;
        await Subscription.findOneAndUpdate(
          { stripe_subscription_id: stripeSub.id },
          { status: 'canceled', plan: 'free' }
        );

        const sub = await Subscription.findOne({ stripe_subscription_id: stripeSub.id });
        if (sub) {
          const client = await Client.findById(sub.client_id);
          if (client?.email) {
            await emailService.sendCancellationConfirmation(client.email, client.name);
          }
        }
        break;
      }

      case 'customer.subscription.updated': {
        const stripeSub = event.data.object;
        const newPlan = stripeSub.metadata?.plan;
        if (newPlan && PLANS[newPlan]) {
          await Subscription.findOneAndUpdate(
            { stripe_subscription_id: stripeSub.id },
            {
              plan: newPlan,
              status: stripeSub.status,
              current_period_start: new Date(stripeSub.current_period_start * 1000),
              current_period_end: new Date(stripeSub.current_period_end * 1000),
            }
          );
        }
        break;
      }

      default:
        console.log(`[Stripe] Evento no manejado: ${event.type}`);
    }
  } catch (err) {
    console.error(`[Stripe] Error procesando evento ${event.type}:`, err.message);
    return res.status(500).json({ error: 'Error interno procesando evento.' });
  }

  res.json({ received: true });
});

// ── GET /api/stripe/plans ─────────────────────────────────────────────────────
router.get('/plans', (req, res) => {
  res.json({
    plans: Object.entries(PLANS).map(([key, p]) => ({
      key,
      name: p.name,
      price: p.amount / 100,
      credits: p.credits,
    })),
  });
});

// ── POST /api/stripe/portal ───────────────────────────────────────────────────
// Abre el portal de Stripe para gestionar suscripción
router.post('/portal', stripeLimiter, async (req, res) => {
  const { clientId } = req.body;
  if (!clientId) return res.status(400).json({ error: 'clientId requerido.' });

  try {
    const sub = await Subscription.findOne({ client_id: clientId });
    if (!sub?.stripe_customer_id) {
      return res.status(404).json({ error: 'No se encontró suscripción activa.' });
    }

    const session = await getStripe().billingPortal.sessions.create({
      customer: sub.stripe_customer_id,
      return_url: `${process.env.FRONTEND_URL}/dashboard`,
    });

    res.json({ url: session.url });
  } catch (err) {
    console.error('[Stripe] Error portal:', err.message);
    res.status(500).json({ error: 'Error al abrir el portal de gestión.' });
  }
});

module.exports = router;
