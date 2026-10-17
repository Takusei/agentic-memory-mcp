const assert = require("node:assert/strict");
const test = require("node:test");

const { handlePaymentWebhook } = require("../src/handlers/paymentWebhook");
const { createOrderStore } = require("../src/store/orders");

function makeStore() {
  return createOrderStore([
    { id: "order-1001", status: "PENDING", history: [{ status: "PENDING" }] }
  ]);
}

test("payment.captured marks a pending order as paid", () => {
  const orders = makeStore();

  const result = handlePaymentWebhook(
    { type: "payment.captured", orderId: "order-1001", paymentId: "pay_77" },
    orders
  );

  assert.equal(result.ok, true);
  assert.equal(orders.get("order-1001").status, "PAID");
});

test("duplicate payment.captured delivery is idempotent", () => {
  const orders = makeStore();
  const event = { type: "payment.captured", orderId: "order-1001", paymentId: "pay_77" };

  handlePaymentWebhook(event, orders);
  const second = handlePaymentWebhook(event, orders);

  assert.equal(second.duplicate, true);
  assert.equal(orders.get("order-1001").history.length, 2);
});
