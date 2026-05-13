const { Conversation, Message } = require('../db/database');
const config = require('../config');

async function getOrCreateConversation(channel, channelId, clientId = null) {
  const cid = String(channelId);
  let conv = await Conversation.findOne({ channel, channel_id: cid }).lean();

  if (!conv) {
    conv = (await Conversation.create({ client_id: clientId, channel, channel_id: cid })).toObject();
  } else if (clientId && !conv.client_id) {
    conv = await Conversation.findByIdAndUpdate(conv._id, { client_id: clientId }, { new: true }).lean();
  }
  return conv;
}

async function saveMessage(conversationId, role, content) {
  await Message.create({ conversation_id: String(conversationId), role, content });
}

async function getHistory(conversationId) {
  const limit = config.ai.maxHistoryMessages;
  const msgs = await Message.find({ conversation_id: String(conversationId) })
    .sort({ createdAt: 1 }).lean();
  return msgs.slice(-limit).map(m => ({ role: m.role, content: m.content }));
}

async function getFullConversation(conversationId) {
  return await Message.find({ conversation_id: String(conversationId) })
    .sort({ createdAt: 1 }).lean();
}

async function listConversations(limit = 50) {
  const convs = await Conversation.find({}).sort({ updatedAt: -1 }).limit(limit).lean();

  return Promise.all(
    convs.map(async (conv) => {
      const msgs = await Message.find({ conversation_id: String(conv._id) })
        .sort({ createdAt: -1 }).lean();
      const last = msgs[0];

      let clientName = 'Anónimo';
      if (conv.client_id) {
        const client = await require('./clientService').findById(conv.client_id);
        if (client) clientName = client.name;
      }

      return {
        ...conv,
        client_name: clientName,
        message_count: msgs.length,
        last_message_at: last?.createdAt || conv.createdAt,
      };
    })
  );
}

module.exports = {
  getOrCreateConversation,
  saveMessage,
  getHistory,
  getFullConversation,
  listConversations,
};
