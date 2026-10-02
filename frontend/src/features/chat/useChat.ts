// Customer chat state: POST /api/chat (messages and candidate picks), POST /api/chat/confirm (confirm or decline a
// pending action, retried after a TOTP step-up) and GET /api/sessions/{id} to restore it after a full-page step-up.
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../../api/client";
import type { Candidate, ChatTurn, SessionView } from "../../api/types";
import { useAuth } from "../../auth/AuthProvider";
import { useLang } from "../../app/i18n";

export type ChatEntry = { id: string; role: "customer" | "assistant"; text: string; turn?: ChatTurn };

const SESSION_KEY = "nicebank.chat.session"; // conversation id only; no tokens or personal data

/** All chat behavior lives here; the components only render entries and call these actions. */
export function useChat() {
  const { user, resume, clearResume, stepUp } = useAuth();
  const { lang, t } = useLang();
  const token = user?.access_token ?? "";
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [entries, setEntries] = useState<ChatEntry[]>([]);
  const [busy, setBusy] = useState(false);
  const [expired, setExpired] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [decided, setDecided] = useState<Set<string>>(new Set());
  const resumed = useRef(false);

  const push = (entry: Omit<ChatEntry, "id">) =>
    setEntries((prev) => [...prev, { ...entry, id: crypto.randomUUID() }]);

  const handleError = useCallback(
    (e: unknown) => {
      if (e instanceof ApiError && e.code === "session_expired") setExpired(true);
      else setError(t.errorGeneric);
    },
    [t.errorGeneric],
  );

  const receive = (turn: ChatTurn) => {
    setSessionId(turn.session_id);
    sessionStorage.setItem(SESSION_KEY, turn.session_id);
    push({ role: "assistant", text: turn.reply, turn });
  };

  const send = useCallback(
    async (message: string, selectTransactionId?: string) => {
      if (!token || busy) return;
      setError(null);
      if (message) push({ role: "customer", text: message });
      setBusy(true);
      try {
        receive(
          await api<ChatTurn>("/api/chat", token, {
            method: "POST",
            body: { session_id: sessionId, message, lang, select_transaction_id: selectTransactionId ?? null },
          }),
        );
      } catch (e) {
        handleError(e);
      } finally {
        setBusy(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [token, busy, sessionId, lang, handleError],
  );

  const pick = useCallback(
    (c: Candidate) => send(`${c.merchant} · ${c.card_last4}`, c.transaction_id),
    [send],
  );

  const decide = useCallback(
    async (actionId: string, confirm: boolean, overrideSession?: string, overrideToken?: string) => {
      const sid = overrideSession ?? sessionId;
      const tok = overrideToken ?? token;
      if (!sid || !tok) return;
      setError(null);
      setBusy(true);
      try {
        const turn = await api<ChatTurn>("/api/chat/confirm", tok, {
          method: "POST",
          body: { session_id: sid, action_id: actionId, confirm },
        });
        setDecided((prev) => new Set(prev).add(actionId));
        receive(turn);
      } catch (e) {
        if (e instanceof ApiError && e.code === "step_up_required") {
          // In-page dialog first: with the level-2 token the same confirmation is sent again right away.
          // (Full-page fallback: the page leaves and the resume effect below completes it on return.)
          const upgraded = await stepUp({ sessionId: sid, actionId });
          if (upgraded) await decide(actionId, true, sid, upgraded.access_token);
          return;
        }
        handleError(e);
      } finally {
        setBusy(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [sessionId, token, stepUp, handleError],
  );

  // After a step-up redirect: restore the conversation, then complete the confirmed action with the new token.
  useEffect(() => {
    if (!resume || !token || resumed.current) return;
    resumed.current = true;
    (async () => {
      try {
        const view = await api<SessionView>(`/api/sessions/${resume.sessionId}`, token);
        setSessionId(view.session_id);
        setEntries(view.messages.map((m) => ({ id: crypto.randomUUID(), role: m.role, text: m.text })));
        clearResume();
        await decide(resume.actionId, true, view.session_id, token);
      } catch (e) {
        handleError(e);
      }
    })();
  }, [resume, token, clearResume, decide, handleError]);

  const reset = useCallback(() => {
    sessionStorage.removeItem(SESSION_KEY);
    setSessionId(null);
    setEntries([]);
    setDecided(new Set());
    setExpired(false);
    setError(null);
  }, []);

  return { entries, busy, expired, error, decided, send, pick, decide, reset, welcome: t.welcome };
}
