const { requireAuth } = require("../middleware/auth");

function getProfile(req) {
  const auth = requireAuth(req);
  if (!auth.ok) {
    return auth;
  }

  return {
    ok: true,
    status: 200,
    body: {
      id: req.user.id,
      displayName: `User ${req.user.id}`
    }
  };
}

module.exports = { getProfile };
