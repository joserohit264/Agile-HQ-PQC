/* Tiny pub/sub so the autopilot can drive tabs ("privacy:eps", "security:tamper", ...)
   while the same tabs stay fully usable by hand. */
const handlers = new Map();

export function on(evt, fn) {
  if (!handlers.has(evt)) handlers.set(evt, new Set());
  handlers.get(evt).add(fn);
  return () => handlers.get(evt).delete(fn);
}

export function emit(evt, payload) {
  (handlers.get(evt) || []).forEach((fn) => fn(payload));
}
