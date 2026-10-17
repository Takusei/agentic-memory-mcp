const assert = require("node:assert/strict");
const test = require("node:test");

const { shouldRetry } = require("../src/retryPolicy");

test("webhook provider 503 retries", () => {
  assert.equal(shouldRetry("webhook", { code: "WEBHOOK_503" }), true);
});

test("webhook provider 410 does not retry", () => {
  assert.equal(shouldRetry("webhook", { code: "WEBHOOK_410" }), false);
});
