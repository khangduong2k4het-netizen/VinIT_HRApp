'use client';

/**
 * Keeps the user's place while they move between sidebar sections.
 *
 * - Section memory: the last page (path + query) seen inside each sidebar section,
 *   so "Vị trí tuyển dụng" brings HR back to the applicant they were reviewing.
 * - URL state: filters, tabs, sort and search live in the query string, so Back,
 *   the section memory and shared links all reopen the same view.
 * - Scroll memory: a list page returns to where it was once its data has loaded.
 *
 * Everything is in sessionStorage (one browser tab, cleared on sign-out). Storage
 * can be unavailable (private mode, blocked); every access is guarded.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

const PREFIX = 'hra.nav.';

function storage(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.sessionStorage;
  } catch {
    return null;
  }
}

/** The section a path belongs to: the longest matching sidebar href. */
export function sectionFor(pathname: string, sections: string[]): string | null {
  let best: string | null = null;
  for (const href of sections) {
    if ((pathname === href || pathname.startsWith(href + '/')) && (!best || href.length > best.length)) best = href;
  }
  return best;
}

export function rememberPage(section: string, url: string) {
  try { storage()?.setItem(PREFIX + 'section:' + section, url); } catch { /* storage full or blocked */ }
}

export function recallPage(section: string): string | null {
  try {
    const url = storage()?.getItem(PREFIX + 'section:' + section) || null;
    // Only same-origin app paths inside that section; never an external URL.
    return url && url.startsWith(section) && !url.startsWith('//') ? url : null;
  } catch {
    return null;
  }
}

/** Forget every remembered page and scroll position (sign-out, another user signs in). */
export function clearNavMemory() {
  const s = storage();
  if (!s) return;
  try {
    for (let i = s.length - 1; i >= 0; i -= 1) {
      const key = s.key(i);
      if (key && key.startsWith(PREFIX)) s.removeItem(key);
    }
  } catch { /* ignore */ }
}

function currentUrl(): string {
  return window.location.pathname + window.location.search;
}

// Listeners told when a page rewrites its query string, so the sidebar can record it.
type Listener = (url: string) => void;
const listeners = new Set<Listener>();
export function onUrlStateChange(fn: Listener) {
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}

/** Call after a page rewrites its own query string with history.replaceState. */
export function notifyUrlChanged() {
  if (typeof window !== 'undefined') listeners.forEach(fn => fn(currentUrl()));
}

export function readUrlParam(key: string): string | null {
  return readParam(key);
}

export function setUrlParam(key: string, value: string | null) {
  if (typeof window !== 'undefined') writeParam(key, value);
}

function readParam(key: string): string | null {
  if (typeof window === 'undefined') return null;
  return new URLSearchParams(window.location.search).get(key);
}

function writeParam(key: string, value: string | null) {
  const params = new URLSearchParams(window.location.search);
  if (value === null || value === '') params.delete(key); else params.set(key, value);
  const query = params.toString();
  const url = window.location.pathname + (query ? `?${query}` : '') + window.location.hash;
  // Replace, not push: changing a filter should not add a Back step.
  window.history.replaceState(window.history.state, '', url);
  listeners.forEach(fn => fn(currentUrl()));
}

/**
 * useState that mirrors one query-string parameter. The default is not written to
 * the URL. `allowed` limits accepted values (anything else falls back to the default).
 * The URL is read after mount, so server and first client render match.
 */
export function useUrlState<T extends string>(key: string, defaultValue: T, allowed?: readonly T[]):
  [T, (value: T) => void, boolean] {
  const [value, setValue] = useState<T>(defaultValue);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const raw = readParam(key);
    if (raw !== null && (!allowed || (allowed as readonly string[]).includes(raw))) setValue(raw as T);
    setReady(true);
    // Read once on mount; later changes come from this hook's own setter.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  const update = useCallback((next: T) => {
    setValue(next);
    writeParam(key, next === defaultValue ? null : next);
  }, [key, defaultValue]);
  return [value, update, ready];
}

/**
 * Restore the window scroll position of this page (path + query) once `ready`
 * turns true (its data has loaded), and keep recording it while the user scrolls.
 */
export function useScrollMemory(ready: boolean) {
  const restored = useRef(false);
  useEffect(() => {
    const keyNow = () => PREFIX + 'scroll:' + window.location.pathname;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const save = () => {
      // Not before the saved position is restored: while the page is still loading,
      // the router's scroll-to-top would overwrite it with 0.
      if (!restored.current) return;
      clearTimeout(timer);
      const key = keyNow();
      const y = Math.round(window.scrollY);
      // A timer, not requestAnimationFrame: frames do not run in a hidden tab.
      timer = setTimeout(() => { try { storage()?.setItem(key, String(y)); } catch { /* ignore */ } }, 120);
    };
    // Also save right when the user clicks (a link, the sidebar, "Quay lại") or leaves,
    // before the router scrolls the next page to the top. Scroll events alone are
    // not enough: browsers skip them in background tabs.
    const saveNow = () => {
      if (!restored.current) return;
      clearTimeout(timer);
      try { storage()?.setItem(keyNow(), String(Math.round(window.scrollY))); } catch { /* ignore */ }
    };
    window.addEventListener('scroll', save, { passive: true });
    document.addEventListener('click', saveNow, true);
    window.addEventListener('pagehide', saveNow);
    return () => {
      window.removeEventListener('scroll', save);
      document.removeEventListener('click', saveNow, true);
      window.removeEventListener('pagehide', saveNow);
      clearTimeout(timer);
    };
  }, []);
  useEffect(() => {
    if (!ready || restored.current) return;
    let y = 0;
    try { y = Number(storage()?.getItem(PREFIX + 'scroll:' + window.location.pathname) || 0); } catch { y = 0; }
    if (!(y > 0)) { restored.current = true; return; }
    // The list may still be rendering: retry until the page is tall enough (max ~2 s),
    // and stop as soon as the user scrolls on their own.
    let tries = 0;
    let userScrolled = false;
    const onUser = () => { userScrolled = true; };
    window.addEventListener('wheel', onUser, { passive: true });
    window.addEventListener('touchmove', onUser, { passive: true });
    window.addEventListener('keydown', onUser);
    const detach = () => {
      window.removeEventListener('wheel', onUser);
      window.removeEventListener('touchmove', onUser);
      window.removeEventListener('keydown', onUser);
    };
    const stop = () => { restored.current = true; detach(); };
    const attempt = () => {
      if (userScrolled) { stop(); return; }
      window.scrollTo({ top: y });
      tries += 1;
      if (Math.abs(window.scrollY - y) <= 2 || tries >= 20) { stop(); return; }
      timer = setTimeout(attempt, 100);
    };
    let timer = setTimeout(attempt, 50);
    // Cleanup does not mark it restored, so a re-run (React dev double effects) still restores.
    return () => { clearTimeout(timer); detach(); };
  }, [ready]);
}
