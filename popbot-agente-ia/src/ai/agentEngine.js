const Groq = require('groq-sdk');
const fs = require('fs');
const path = require('path');
const config = require('../config');
const conversationService = require('../services/conversationService');
const { TrainingExample, User } = require('../db/database');
const { Evento } = require('../db/userDataSchema');

const groq = new Groq({ apiKey: config.groq.apiKey });

const CASOS_PATH = path.join(__dirname, '../../config/casos.json');

// ── Caché de casos.json ────────────────────────────────────────────────────────
let casosCache = null;
let casosCacheTime = 0;

function loadCasos() {
  const now = Date.now();
  if (casosCache && now - casosCacheTime < 60_000) return casosCache;
  try {
    casosCache = JSON.parse(fs.readFileSync(CASOS_PATH, 'utf8'));
    casosCacheTime = now;
  } catch {
    if (!casosCache) casosCache = { bot: {}, instrucciones_globales: [], casos: [] };
  }
  return casosCache;
}

function invalidateCasosCache() { casosCache = null; }

// ── Caché de ejemplos de entrenamiento ────────────────────────────────────────
let trainingCache = [];
let trainingCacheTime = 0;

async function loadTrainingExamples(userId) {
  const now = Date.now();
  if (trainingCache.length > 0 && now - trainingCacheTime < 120_000) return trainingCache;
  try {
    // Ejemplos globales (sin user_id) + los del usuario
    const filter = { activo: true, $or: [{ user_id: { $exists: false } }, { user_id: userId }] };
    trainingCache = await TrainingExample.find(filter).sort({ createdAt: -1 }).limit(80).lean();
    trainingCacheTime = now;
  } catch { /* usar caché anterior */ }
  return trainingCache;
}

// ── System prompt personalizado por usuario ───────────────────────────────────
function buildSystemPrompt(user, trainingExamples = []) {
  const casos = loadCasos();
  const botCfg = user?.botConfig || {};
  const nombre = botCfg.nombre || 'Asistente';
  const personalidad = botCfg.personalidad || 'Eres un asistente personal útil, organizado y proactivo. Hablas siempre en español.';
  const contexto = botCfg.contexto || '';

  const today = new Date();
  const todayStr = today.toLocaleDateString('es-ES', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
  const todayISO = today.toISOString().split('T')[0];
  const manana = new Date(today); manana.setDate(manana.getDate() + 1);
  const mananaISO = manana.toISOString().split('T')[0];
  const lunesProximo = (() => {
    const d = new Date(today);
    const dia = d.getDay();
    d.setDate(d.getDate() + ((8 - dia) % 7 || 7));
    return d.toISOString().split('T')[0];
  })();

  // Instrucciones globales del casos.json
  const instrucciones = (casos.instrucciones_globales || []).map((i, n) => `${n + 1}. ${i}`).join('\n');

  // Casos del casos.json
  const casosBlocks = (casos.casos || []).map(c => {
    const ejs = (c.ejemplos || []).map(e => `  Usuario: "${e.usuario}"\n  Tú: "${e.asistente}"`).join('\n');
    return `### ${c.nombre}\n${c.instruccion}${ejs ? `\nEjemplos:\n${ejs}` : ''}`;
  }).join('\n\n');

  // Ejemplos de entrenamiento de BD
  let trainingBlock = '';
  if (trainingExamples.length > 0) {
    trainingBlock = '\n\nEJEMPLOS DE CÓMO ACTUAR (aprende estos patrones y aplícalos):\n' +
      trainingExamples.map(e => `  Usuario: "${e.input}"\n  Tú: "${e.output}"`).join('\n');
  }

  return `Eres ${nombre}, el asistente personal de ${user?.nombre || 'tu usuario'}.
${personalidad}
${contexto ? `\nCONTEXTO DEL USUARIO:\n${contexto}` : ''}

HOY ES: ${todayStr} (${todayISO})
MAÑANA: ${mananaISO}
LUNES PRÓXIMO: ${lunesProximo}

REGLAS CLAVE:
1. Cuando el usuario pida añadir algo al calendario, usa SIEMPRE la herramienta crear_evento. No solo respondas, ACTÚA.
2. Cuando pida ver agenda o eventos, usa listar_eventos.
3. Cuando pida crear un plan semanal, crea los eventos uno a uno con crear_evento.
4. Interpreta el lenguaje natural: "fuerza 45 min" = entreno de fuerza 45 minutos, "PPL" = rutina Push/Pull/Legs, "la semana que viene" = a partir de ${lunesProximo}.
5. Responde siempre en español, de forma breve y confirmando lo que has hecho.
6. Después de actuar, resume brevemente lo que hiciste.
${instrucciones ? `\nINSTRUCCIONES ADICIONALES:\n${instrucciones}` : ''}
${casosBlocks ? `\nCASOS ESPECÍFICOS:\n${casosBlocks}` : ''}
${trainingBlock}`;
}

// ── Herramientas del bot ───────────────────────────────────────────────────────
const TOOLS = [
  {
    type: 'function',
    function: {
      name: 'crear_evento',
      description: 'Crea un evento, tarea, entrenamiento o recordatorio en el calendario del usuario. Usar siempre que el usuario pida añadir algo.',
      parameters: {
        type: 'object',
        properties: {
          titulo:       { type: 'string', description: 'Nombre del evento. Ej: "Entrenamiento de fuerza", "Reunión con Juan"' },
          fecha:        { type: 'string', description: 'Fecha en formato YYYY-MM-DD' },
          hora_inicio:  { type: 'string', description: 'Hora de inicio HH:MM (opcional)' },
          duracion_min: { type: 'number', description: 'Duración en minutos (opcional)' },
          tipo:         { type: 'string', description: 'Tipo: evento, tarea, entreno, reunion, recordatorio' },
          notas:        { type: 'string', description: 'Notas adicionales (opcional)' },
        },
        required: ['titulo', 'fecha'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'listar_eventos',
      description: 'Lista los eventos del usuario para una fecha o rango de fechas.',
      parameters: {
        type: 'object',
        properties: {
          fecha_inicio: { type: 'string', description: 'Fecha inicio YYYY-MM-DD' },
          fecha_fin:    { type: 'string', description: 'Fecha fin YYYY-MM-DD (opcional, si no se da solo muestra ese día)' },
        },
        required: ['fecha_inicio'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'borrar_evento',
      description: 'Borra un evento del calendario por su ID.',
      parameters: {
        type: 'object',
        properties: {
          evento_id: { type: 'string', description: 'ID del evento a borrar' },
        },
        required: ['evento_id'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'marcar_completado',
      description: 'Marca una tarea o evento como completado.',
      parameters: {
        type: 'object',
        properties: {
          evento_id: { type: 'string', description: 'ID del evento' },
        },
        required: ['evento_id'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'crear_plan_semanal',
      description: 'Crea un plan completo de la semana (ej: rutina de entrenamiento, plan de trabajo). Llama a crear_evento por cada sesión.',
      parameters: {
        type: 'object',
        properties: {
          tipo_plan:    { type: 'string', description: 'Tipo de plan. Ej: "PPL", "fullbody", "cardio", "trabajo"' },
          semana_inicio:{ type: 'string', description: 'Fecha del lunes de la semana YYYY-MM-DD' },
          preferencias: { type: 'string', description: 'Detalles: días, duración, horario, etc.' },
        },
        required: ['tipo_plan', 'semana_inicio'],
      },
    },
  },
];

// ── Ejecutor de herramientas ───────────────────────────────────────────────────
async function executeTool(toolName, args, userId) {
  console.log(`[AI] Tool: ${toolName}`, JSON.stringify(args));
  try {
    switch (toolName) {

      case 'crear_evento': {
        const { titulo, fecha, hora_inicio, duracion_min, tipo = 'evento', notas = '' } = args;
        const evento = await Evento.create({
          user_id: userId, titulo, fecha,
          hora_inicio: hora_inicio || null,
          hora_fin: hora_inicio && duracion_min ? calcHoraFin(hora_inicio, duracion_min) : null,
          duracion_min: duracion_min || null,
          tipo, notas,
        });
        return { ok: true, id: evento._id, mensaje: `"${titulo}" añadido al ${fecha}${hora_inicio ? ` a las ${hora_inicio}` : ''}` };
      }

      case 'listar_eventos': {
        const { fecha_inicio, fecha_fin } = args;
        const filter = { user_id: userId, fecha: fecha_fin ? { $gte: fecha_inicio, $lte: fecha_fin } : fecha_inicio };
        const eventos = await Evento.find(filter).sort({ fecha: 1, hora_inicio: 1 }).lean();
        if (eventos.length === 0) return { eventos: [], mensaje: 'No hay eventos en ese período.' };
        return {
          eventos: eventos.map(e => ({
            id: e._id, titulo: e.titulo, fecha: e.fecha,
            hora: e.hora_inicio || 'sin hora', duracion: e.duracion_min ? `${e.duracion_min} min` : null,
            tipo: e.tipo, completado: e.completado, notas: e.notas,
          })),
        };
      }

      case 'borrar_evento': {
        const deleted = await Evento.findOneAndDelete({ _id: args.evento_id, user_id: userId });
        if (!deleted) return { ok: false, error: 'Evento no encontrado.' };
        return { ok: true, mensaje: `"${deleted.titulo}" eliminado.` };
      }

      case 'marcar_completado': {
        const evt = await Evento.findOneAndUpdate(
          { _id: args.evento_id, user_id: userId },
          { completado: true }, { new: true }
        );
        if (!evt) return { ok: false, error: 'Evento no encontrado.' };
        return { ok: true, mensaje: `"${evt.titulo}" marcado como completado.` };
      }

      case 'crear_plan_semanal': {
        // El modelo decide las sesiones según el tipo de plan
        // Aquí solo devolvemos contexto para que el modelo llame a crear_evento por cada sesión
        return {
          instruccion: `Crea los eventos individuales llamando a crear_evento para cada sesión del plan "${args.tipo_plan}" empezando el ${args.semana_inicio}. Preferencias: ${args.preferencias || 'estándar'}.`,
          semana_inicio: args.semana_inicio,
        };
      }

      default:
        return { error: `Herramienta '${toolName}' no reconocida.` };
    }
  } catch (err) {
    console.error(`[AI] Error en tool ${toolName}:`, err.message);
    return { error: 'Error interno al ejecutar la acción.' };
  }
}

function calcHoraFin(horaInicio, minutos) {
  const [h, m] = horaInicio.split(':').map(Number);
  const total = h * 60 + m + minutos;
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
}

// ── Motor principal ────────────────────────────────────────────────────────────
async function processMessage(userMessage, channel, channelId, userId = null) {
  const conversation = await conversationService.getOrCreateConversation(channel, channelId, userId);
  await conversationService.saveMessage(conversation._id, 'user', userMessage);

  const history = await conversationService.getHistory(conversation._id);

  // Cargar datos del usuario y ejemplos de entrenamiento
  const [user, trainingExamples] = await Promise.all([
    userId ? User.findById(userId).lean() : null,
    loadTrainingExamples(userId),
  ]);

  const systemPrompt = buildSystemPrompt(user, trainingExamples);

  const messages = [
    { role: 'system', content: systemPrompt },
    ...history,
  ];

  let response = '';
  let maxIterations = 10;

  while (maxIterations-- > 0) {
    let completion;
    try {
      completion = await groq.chat.completions.create({
        model: config.groq.model,
        messages,
        tools: TOOLS,
        tool_choice: 'auto',
        max_tokens: 1024,
        temperature: 0.3,
      });
    } catch (apiErr) {
      console.error('[AI] Error API Groq:', apiErr.message);
      const fallback = await groq.chat.completions.create({
        model: config.groq.model,
        messages,
        max_tokens: 1024,
        temperature: 0.3,
      });
      response = (fallback.choices[0].message.content || '').trim();
      break;
    }

    const choice = completion.choices[0];
    const message = choice.message;

    if (choice.finish_reason === 'tool_calls' && message.tool_calls?.length > 0) {
      messages.push({ role: 'assistant', content: message.content || '', tool_calls: message.tool_calls });

      for (const toolCall of message.tool_calls) {
        let args = {};
        try { args = JSON.parse(toolCall.function.arguments); } catch {}
        const result = await executeTool(toolCall.function.name, args, userId);
        console.log(`[AI] Resultado:`, JSON.stringify(result));
        messages.push({ role: 'tool', tool_call_id: toolCall.id, content: JSON.stringify(result) });
      }
    } else {
      response = (message.content || '').trim();
      break;
    }
  }

  if (response) await conversationService.saveMessage(conversation._id, 'assistant', response);
  return response || 'Lo siento, no pude procesar tu mensaje. ¿Puedes intentarlo de nuevo?';
}

module.exports = { processMessage, invalidateCasosCache, loadCasos };
