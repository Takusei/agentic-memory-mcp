const { requireSession } = require("../middleware/sessionAuth");

function getProfile(req) {
  const auth = requireSession(req);
  if (!auth.ok) {
    return auth;
  }

  if (!req.authenticatedUserId) {
    return {
      ok: false,
      status: 401,
      body: { error: "Authenticated session did not include a user id" }
    };
  }

  return {
    ok: true,
    status: 200,
    body: {
      id: req.authenticatedUserId,
      displayName: `Session user ${req.authenticatedUserId}`
    }
  };
}

module.exports = { getProfile };
