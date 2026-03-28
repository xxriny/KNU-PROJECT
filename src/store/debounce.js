/**
 * Simple debounce utility for session auto-save.
 */
export function debounce(fn, delay = 500) {
  let timer = null;
  return (...args) => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      timer = null;
      fn(...args);
    }, delay);
  };
}
