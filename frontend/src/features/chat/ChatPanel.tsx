import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  IconButton,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { MessageSquarePlus, SendHorizontal } from "lucide-react";
import { useLang } from "../../app/i18n";
import { ActionCard, Bubble, CandidateList, TurnBadges } from "./ChatParts";
import type { useChat } from "./useChat";

export default function ChatPanel({ chat }: { chat: ReturnType<typeof useChat> }) {
  const { t } = useLang();
  const [draft, setDraft] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const last = chat.entries.at(-1);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [chat.entries.length, chat.busy]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const text = draft.trim();
    if (!text) return;
    setDraft("");
    void chat.send(text);
  };

  return (
    <Paper sx={{ display: "flex", flexDirection: "column", height: { xs: "calc(100dvh - 96px)", md: "calc(100dvh - 120px)" }, border: "none", boxShadow: "0 12px 32px rgba(74, 16, 38, 0.10)" }}>
      <Stack direction="row" sx={{ alignItems: "center", px: 2, py: 1.5, borderBottom: 1, borderColor: "divider" }}>
        <Typography variant="h6" sx={{ flex: 1 }}>
          {t.chatTitle}
        </Typography>
        <Tooltip title={t.newChat}>
          <IconButton onClick={chat.reset} aria-label={t.newChat}>
            <MessageSquarePlus size={20} />
          </IconButton>
        </Tooltip>
      </Stack>

      <Stack spacing={1.5} sx={{ flex: 1, overflowY: "auto", p: 2 }}>
        <Bubble role="assistant" text={chat.welcome} />
        {chat.entries.map((entry) => {
          const isLast = entry === last;
          const turn = entry.turn;
          return (
            <Stack key={entry.id} spacing={1}>
              <Bubble role={entry.role} text={entry.text} />
              {turn?.candidates && (
                <CandidateList candidates={turn.candidates} active={isLast && !chat.busy} onPick={chat.pick} />
              )}
              {turn?.pending_action && (
                <ActionCard
                  action={turn.pending_action}
                  active={isLast && !chat.busy && !chat.decided.has(turn.pending_action.id)}
                  onDecide={(ok) => chat.decide(turn.pending_action!.id, ok)}
                />
              )}
              {turn && <TurnBadges turn={turn} />}
            </Stack>
          );
        })}
        {chat.busy && (
          <Stack direction="row" spacing={1} sx={{ alignItems: "center", color: "text.secondary" }}>
            <CircularProgress size={16} />
            <Typography variant="caption">{t.thinking}</Typography>
          </Stack>
        )}
        {chat.error && <Alert severity="warning">{chat.error}</Alert>}
        <div ref={endRef} />
      </Stack>

      {chat.entries.length === 0 && (
        <Stack direction="row" spacing={1} sx={{ px: 2, pb: 1, flexWrap: "wrap", rowGap: 1 }}>
          {t.suggestions.map((s) => (
            <Chip key={s} label={s} variant="outlined" onClick={() => void chat.send(s)} />
          ))}
        </Stack>
      )}

      <Box component="form" onSubmit={submit} sx={{ display: "flex", gap: 1, p: 2, borderTop: 1, borderColor: "divider" }}>
        <TextField
          fullWidth
          size="small"
          autoComplete="off"
          placeholder={t.chatPlaceholder}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={chat.busy}
          slotProps={{ htmlInput: { maxLength: 2000, "aria-label": t.chatPlaceholder } }}
        />
        <Button type="submit" variant="contained" endIcon={<SendHorizontal size={16} />} disabled={chat.busy || !draft.trim()}>
          {t.send}
        </Button>
      </Box>

      <Dialog open={chat.expired} onClose={chat.reset}>
        <DialogTitle>{t.sessionExpiredTitle}</DialogTitle>
        <DialogContent>
          <DialogContentText>{t.sessionExpiredBody}</DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={chat.reset} variant="contained">
            {t.startAgain}
          </Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
}
