import { logger } from "@/lib/logger";

// Browser code calls the backend directly. The URL is baked in at build time (see docker-compose.yml).
export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function api(path, options = {}) {
  const method = options.method || "GET";
  const started = performance.now();
  let res;
  try {
    res = await fetch(`${API}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (err) {
    logger.error(`${method} ${path} failed: network error`, err.message);
    throw new Error(`Cannot reach the API at ${API}`);
  }
  const body = await res.json().catch(() => ({}));
  const ms = (performance.now() - started).toFixed(0);

  if (!res.ok) {
    const detail = Array.isArray(body.detail) ? body.detail[0]?.msg : body.detail;
    logger.warn(`${method} ${path} -> ${res.status} (${ms} ms): ${detail}`);
    throw new Error(detail || `Request failed (${res.status})`);
  }
  logger.info(`${method} ${path} -> ${res.status} (${ms} ms)`);
  return body;
}

export function query(params) {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v) p.set(k, v);
  });
  const s = p.toString();
  return s ? `?${s}` : "";
}

export const fmt = (n) => (n === null || n === undefined ? "–" : Number(n).toFixed(2));
export const pct = (n) => (n === null || n === undefined ? "–" : `${Math.round(n * 100)}%`);
export const CALL_TYPES = ["support", "external", "internal"];
