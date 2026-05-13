const { Client } = require('../db/database');

async function findOrCreate({ name, phone, channel = 'web' }) {
  if (phone) {
    const existing = await Client.findOne({ phone }).lean();
    if (existing) return existing;
  }
  return (await Client.create({ name, phone: phone || null, channel })).toObject();
}

async function findById(id) {
  try {
    return await Client.findById(id).lean();
  } catch {
    return null;
  }
}

async function findByPhone(phone) {
  return await Client.findOne({ phone }).lean();
}

async function updateName(id, name) {
  return await Client.findByIdAndUpdate(id, { name }, { new: true }).lean();
}

async function listAll() {
  return await Client.find({}).sort({ createdAt: -1 }).lean();
}

module.exports = { findOrCreate, findById, findByPhone, updateName, listAll };
