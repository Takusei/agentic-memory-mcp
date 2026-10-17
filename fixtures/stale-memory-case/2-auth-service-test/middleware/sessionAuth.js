function requireSession(req) {
  if (!req.session || !req.session.userId) {
    return {
      ok: false,
      status: 401,
      body: { error: "Session required" }
    };
  }

  // BUG: this repo moved away from req.user, but this middleware still
  // exposes the old field. The profile route expects req.authenticatedUserId.
  req.user = { id: String(req.session.userId) };
  return { ok: true };
}

module.exports = { requireSession };
