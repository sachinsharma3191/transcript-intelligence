// Console logger for the browser. Level comes from NEXT_PUBLIC_LOG_LEVEL at build time:
// debug | info | warn | error. Default is info.
const LEVELS = { debug: 10, info: 20, warn: 30, error: 40 };
const threshold = LEVELS[(process.env.NEXT_PUBLIC_LOG_LEVEL || "info").toLowerCase()] ?? LEVELS.info;

function emit(level, message, data) {
  if (LEVELS[level] < threshold) return;
  const line = `${new Date().toISOString()} ${level.toUpperCase().padEnd(5)} [ui] ${message}`;
  const sink = level === "error" ? console.error : level === "warn" ? console.warn : console.log;
  data === undefined ? sink(line) : sink(line, data);
}

export const logger = {
  debug: (message, data) => emit("debug", message, data),
  info: (message, data) => emit("info", message, data),
  warn: (message, data) => emit("warn", message, data),
  error: (message, data) => emit("error", message, data),
};
