import type { INavigator, IWindow, NavigateParams, NavigateResponse } from "oidc-client-ts";

/**
 * Step-up inside the app: oidc-client-ts's popup flow, but the authorization page opens in an iframe of our own
 * dialog (StepUpDialog) instead of a browser window. The library still builds the request (PKCE, state, nonce)
 * and validates the response; this only decides where the page is shown.
 *
 * Keycloak lets only NiceBank's origins frame it (realm browserSecurityHeaders). It redirects the iframe to
 * /stepup-callback.html, which posts the response URL back here (same origin only).
 */
export const STEP_UP_CANCELLED = "step-up cancelled";
export const STEP_UP_FULL_PAGE = "step-up full page";
const TIMEOUT_MS = 3 * 60_000; // time to open the authenticator app and type the code

type Listener = () => void;

export class ModalNavigator implements INavigator {
  private url: string | null = null;
  private listeners = new Set<Listener>();
  private abort: ((reason: string) => void) | null = null;

  /** For useSyncExternalStore: the authorization URL to show, or null when no step-up is running. */
  subscribe = (l: Listener) => {
    this.listeners.add(l);
    return () => this.listeners.delete(l);
  };
  current = () => this.url;

  /** Closes the dialog; signinPopup rejects with `reason` (STEP_UP_CANCELLED or STEP_UP_FULL_PAGE). */
  cancel(reason: string = STEP_UP_CANCELLED) {
    this.abort?.(reason);
  }

  private show(url: string | null) {
    this.url = url;
    this.listeners.forEach((l) => l());
  }

  async prepare(): Promise<IWindow> {
    return {
      navigate: (params: NavigateParams) => this.navigate(params),
      close: () => this.show(null),
    };
  }

  // The callback page talks to navigate() directly; nothing to do on the library's callback path.
  async callback(): Promise<void> {}

  private navigate({ url }: NavigateParams): Promise<NavigateResponse> {
    this.abort?.(STEP_UP_CANCELLED); // a new step-up replaces any stale one
    return new Promise((resolve, reject) => {
      const done = () => {
        window.removeEventListener("message", onMessage);
        clearTimeout(timer);
        this.abort = null;
        this.show(null);
      };
      const onMessage = (e: MessageEvent) => {
        const data = e.data as { type?: string; url?: unknown } | null;
        if (e.origin !== window.location.origin || data?.type !== "nb-stepup" || typeof data.url !== "string") return;
        done();
        resolve({ url: data.url });
      };
      const timer = setTimeout(() => {
        done();
        reject(new Error(STEP_UP_CANCELLED));
      }, TIMEOUT_MS);
      this.abort = (reason) => {
        done();
        reject(new Error(reason));
      };
      window.addEventListener("message", onMessage);
      this.show(url);
    });
  }
}

export const stepUpNavigator = new ModalNavigator();
