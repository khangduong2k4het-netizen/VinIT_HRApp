'use client';

import { useEffect } from 'react';

/**
 * Warn before losing unsaved work.
 *
 * Covers closing/reloading the tab (`beforeunload`), in-app links (`a[href]`),
 * and browser Back/Forward.
 *
 * Back cannot be cancelled, so the hook tags the current history entry as the
 * page (`hraUnsavedPage`) and keeps one guard entry (`hraUnsavedGuard`) on top
 * of it with the same URL:
 *
 *     [... previous, P(page), G(guard)]
 *
 * A Back press from G lands on P, which is when the hook asks:
 * - cancelling calls `history.forward(1)` to return to G, so the next Back asks
 *   again and no extra entries accumulate;
 * - confirming completes the user's original navigation with a second Back and
 *   suppresses the duplicate prompt.
 *
 * A reload can leave the browser on G; the hook detects that marker and does not
 * push another guard entry, so repeated reloads (and save-then-edit cycles) do
 * not build a stack of same-URL entries.
 *
 * This is a safety net, not storage: callers should also persist drafts (see
 * `lib/localDrafts`) because a crash, a hard reload or a browser that refuses
 * the dialog can still discard memory-only state.
 */
const PAGE_ENTRY_KEY = 'hraUnsavedPage';
const GUARD_ENTRY_KEY = 'hraUnsavedGuard';

export function useUnsavedChangesGuard(dirty: boolean, message: string, options: { fallbackHref?: string } = {}) {
  useEffect(() => {
    if (!dirty || typeof window === 'undefined') return;
    const history = window.history;
    let leaving = false;
    const current = () => (history.state || {}) as Record<string, unknown>;

    const pushGuard = () => {
      const guardState = { ...current(), [GUARD_ENTRY_KEY]: true } as Record<string, unknown>;
      delete guardState[PAGE_ENTRY_KEY];
      history.pushState(guardState, '', window.location.href);
    };
    // Three cases when the form becomes dirty:
    // - neither marker: tag this entry and stack a guard on top;
    // - already on a guard entry (a reload landed here, or the form was saved on
    //   the guard and then edited again): reuse it, so saving and re-editing does
    //   not build a stack of same-URL entries that swallow Back presses;
    // - on the page entry (guard lost, e.g. the user hit Forward into it): just
    //   restore the guard.
    if (!current()[GUARD_ENTRY_KEY]) {
      const pageState = { ...current(), [PAGE_ENTRY_KEY]: true } as Record<string, unknown>;
      delete pageState[GUARD_ENTRY_KEY];
      history.replaceState(pageState, '', window.location.href);
      pushGuard();
    }

    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (leaving) return;
      event.preventDefault();
      event.returnValue = '';
    };
    const onClick = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const anchor = (event.target as Element | null)?.closest?.('a[href]') as HTMLAnchorElement | null;
      if (!anchor || anchor.target === '_blank' || anchor.hasAttribute('download')) return;
      const url = new URL(anchor.href, window.location.href);
      if (url.origin !== window.location.origin) return;
      if (url.pathname === window.location.pathname && url.search === window.location.search) return;
      if (window.confirm(message)) { leaving = true; return; }
      event.preventDefault();
      event.stopPropagation();
    };
    const onPopState = (event: PopStateEvent) => {
      if (leaving) return;
      const state = (event.state || {}) as Record<string, unknown>;
      if (state[GUARD_ENTRY_KEY]) return; // Still on our own guard entry.
      if (state[PAGE_ENTRY_KEY]) {
        if (!window.confirm(message)) {
          // Back to the guard entry so the URL stays put and the next Back asks again.
          history.forward();
          return;
        }
        leaving = true;
        const before = window.location.href;
        history.back();
        // Bookmarked/deep-linked pages may have no earlier history entry; in that
        // case go to the caller's safe destination instead of silently staying.
        if (options.fallbackHref) {
          window.setTimeout(() => {
            if (window.location.href === before) window.location.assign(options.fallbackHref as string);
          }, 800);
        }
        return;
      }
      // Any other entry: the browser is leaving through history we do not own.
      if (!window.confirm(message)) { pushGuard(); return; }
      leaving = true;
    };

    window.addEventListener('beforeunload', beforeUnload);
    document.addEventListener('click', onClick, true);
    window.addEventListener('popstate', onPopState);
    return () => {
      window.removeEventListener('beforeunload', beforeUnload);
      document.removeEventListener('click', onClick, true);
      window.removeEventListener('popstate', onPopState);
    };
  }, [dirty, message, options.fallbackHref]);
}
