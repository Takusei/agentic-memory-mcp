const assert = require("node:assert/strict");
const test = require("node:test");

const { nextRetryDelayMs, shouldRetry } = require("../src/retryPolicy");

test("email transient SMTP errors retry", () => {
  assert.equal(shouldRetry("email", { code: "SMTP_TEMP" }), true);
});

test("email permanent SMTP errors do not retry", () => {
  assert.equal(shouldRetry("email", { code: "SMTP_PERM" }), false);
});

test("retry delay uses capped exponential backoff", () => {
  assert.equal(nextRetryDelayMs(1), 1000);
  assert.equal(nextRetryDelayMs(3), 4000);
  assert.equal(nextRetryDelayMs(10), 30000);
});
