const assert = require("node:assert/strict");
const test = require("node:test");

const { handleRequest } = require("../server");

test("profile returns data when x-user-id is present", () => {
  const response = handleRequest("/profile", {
    headers: { "x-user-id": "user-123" }
  });

  assert.equal(response.status, 200);
  assert.equal(response.body.id, "user-123");
});

test("profile returns 401 when x-user-id is missing", () => {
  const response = handleRequest("/profile", { headers: {} });

  assert.equal(response.status, 401);
});
