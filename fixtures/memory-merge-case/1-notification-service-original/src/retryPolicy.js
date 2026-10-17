function shouldRetry(channel, error) {
  if (!error || !error.code) {
    return false;
  }

  if (channel === "email") {
    return error.code === "SMTP_TEMP";
  }

  return false;
}

function nextRetryDelayMs(attempt) {
  return Math.min(30000, 1000 * 2 ** Math.max(0, attempt - 1));
}

module.exports = { shouldRetry, nextRetryDelayMs };
