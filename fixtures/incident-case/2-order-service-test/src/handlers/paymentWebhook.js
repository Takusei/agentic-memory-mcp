function handlePaymentWebhook(event, orders) {
  if (!event || !event.type) {
    return { ok: false, ignored: true, reason: "missing_event_type" };
  }

  // BUG: production logs show payment.captured, but this handler only accepts
  // the older payment.succeeded event name.
  if (event.type !== "payment.succeeded") {
    return { ok: true, ignored: true, reason: "unhandled_event_type" };
  }

  return orders.markPaid(event.orderId, event.paymentId);
}

module.exports = { handlePaymentWebhook };
