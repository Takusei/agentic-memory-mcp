function requireAuth(req) {
  const userId = req.headers && req.headers["x-user-id"];

  if (!userId) {
    return {
      ok: false,
      status: 401,
      body: { error: "Authentication required" }
    };
  }

  req.user = { id: String(userId) };
  return { ok: true };
}

module.exports = { requireAuth };
