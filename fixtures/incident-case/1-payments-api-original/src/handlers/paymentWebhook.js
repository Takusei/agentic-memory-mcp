function handlePaymentWebhook(event, orders) {
  if (!event || !event.type) {
    return { ok: false, ignored: true, reason: "missing_event_type" };
  }

  if (event.type !== "payment.succeeded" && event.type !== "payment.captured") {
    return { ok: true, ignored: true, reason: "unhandled_event_type" };
  }

  return orders.markPaid(event.orderId, event.paymentId);
}

module.exports = { handlePaymentWebhook };
