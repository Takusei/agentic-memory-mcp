const { getProfile } = require("./routes/profile");

function handleRequest(path, req) {
  if (path === "/profile") {
    return getProfile(req);
  }

  return {
    ok: false,
    status: 404,
    body: { error: "Not found" }
  };
}

module.exports = { handleRequest };
