const assert = require("node:assert/strict");
const test = require("node:test");

const { handleRequest } = require("../server");

test("profile returns data when a valid session is present", () => {
  const response = handleRequest("/profile", {
    session: { userId: "session-user-123" }
  });

  assert.equal(response.status, 200);
  assert.equal(response.body.id, "session-user-123");
});

test("profile returns 401 when session is missing", () => {
  const response = handleRequest("/profile", {});

  assert.equal(response.status, 401);
});
