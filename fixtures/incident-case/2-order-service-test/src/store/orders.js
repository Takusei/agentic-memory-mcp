function createOrderStore(initialOrders = []) {
  const orders = new Map();

  for (const order of initialOrders) {
    orders.set(order.id, {
      ...order,
      history: [...(order.history || [])]
    });
  }

  return {
    get(orderId) {
      return orders.get(orderId);
    },

    markPaid(orderId, paymentId) {
      const order = orders.get(orderId);
      if (!order) {
        return { ok: false, reason: "order_not_found" };
      }

      if (order.status === "PAID") {
        return { ok: true, duplicate: true, order };
      }

      order.status = "PAID";
      order.paymentId = paymentId;
      order.history.push({ status: "PAID", paymentId });
      return { ok: true, duplicate: false, order };
    }
  };
}

module.exports = { createOrderStore };
