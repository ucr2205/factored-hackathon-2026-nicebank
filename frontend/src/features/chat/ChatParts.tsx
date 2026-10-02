// Presentational pieces of a chat turn: message bubble, transaction candidates, confirm card and verified badges.
import { Box, Button, Card, CardActionArea, Chip, Paper, Stack, Typography } from "@mui/material";
import { BadgeCheck, CreditCard, Headset, KeyRound } from "lucide-react";
import type { Candidate, ChatTurn, PendingAction } from "../../api/types";
import { formatDateTime, formatMoney, useLang } from "../../app/i18n";

/** One message; the customer's own messages sit on the right in burgundy. */
export function Bubble({ role, text }: { role: "customer" | "assistant"; text: string }) {
  const mine = role === "customer";
  return (
    <Box sx={{ display: "flex", justifyContent: mine ? "flex-end" : "flex-start" }}>
      <Box
        sx={{
          maxWidth: "80%",
          px: 2,
          py: 1.25,
          borderRadius: 3,
          borderBottomRightRadius: mine ? 4 : undefined,
          borderBottomLeftRadius: mine ? undefined : 4,
          bgcolor: mine ? "primary.main" : "background.default",
          color: mine ? "primary.contrastText" : "text.primary",
          whiteSpace: "pre-wrap",
        }}
      >
        <Typography variant="body2">{text}</Typography>
      </Box>
    </Box>
  );
}

/** Transactions matching the customer's description; clickable only on the latest turn while the chat is idle. */
export function CandidateList({ candidates, active, onPick }: { candidates: Candidate[]; active: boolean; onPick: (c: Candidate) => void }) {
  const { lang, t } = useLang();
  return (
    <Stack spacing={1} sx={{ pl: { sm: 1 }, maxWidth: 520 }}>
      {candidates.map((c) => (
        <Card key={c.transaction_id} variant="outlined">
          <CardActionArea disabled={!active} onClick={() => onPick(c)} sx={{ p: 1.5 }}>
            <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
              <CreditCard size={20} color="#7A1F3D" />
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography variant="subtitle2" noWrap>
                  {c.merchant || "—"}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {formatDateTime(c.date, lang)} · {t.card} •••• {c.card_last4}
                  {c.country ? ` · ${c.country}` : ""}
                </Typography>
              </Box>
              <Typography variant="subtitle2">{formatMoney(c.amount, c.currency, lang)}</Typography>
              {active && (
                <Chip label={t.pickCandidate} size="small" color="primary" variant="outlined" />
              )}
            </Stack>
          </CardActionArea>
        </Card>
      ))}
    </Stack>
  );
}

/** Confirm / decline buttons for a pending action, with a note when it will ask for the TOTP code. */
export function ActionCard({ action, active, onDecide }: { action: PendingAction; active: boolean; onDecide: (confirm: boolean) => void }) {
  const { t } = useLang();
  return (
    <Paper sx={{ p: 2, maxWidth: 520, borderColor: "secondary.main" }}>
      {action.requires_step_up && (
        <Stack direction="row" spacing={1} sx={{ alignItems: "center", mb: 1.5 }}>
          <KeyRound size={16} color="#7A1F3D" />
          <Typography variant="caption" color="text.secondary">
            {t.stepUpNote}
          </Typography>
        </Stack>
      )}
      <Stack direction="row" spacing={1}>
        <Button variant="contained" color="secondary" disabled={!active} onClick={() => onDecide(true)}>
          {t.confirm}
        </Button>
        <Button variant="text" disabled={!active} onClick={() => onDecide(false)}>
          {t.cancel}
        </Button>
      </Stack>
    </Paper>
  );
}

/** Chips for actions verified by read-back (with their reference) and for a handoff to a specialist. */
export function TurnBadges({ turn }: { turn: ChatTurn }) {
  const { t } = useLang();
  if (!turn.actions_verified.length && !turn.handoff_id) return null;
  return (
    <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", rowGap: 1 }}>
      {turn.actions_verified.map((a) => (
        <Chip
          key={a.reference}
          icon={<BadgeCheck size={16} />}
          color="success"
          variant="outlined"
          size="small"
          label={`${t.verified} · ${a.reference}`}
        />
      ))}
      {turn.handoff_id && (
        <Chip icon={<Headset size={16} />} color="info" variant="outlined" size="small" label={t.handoffNote} />
      )}
    </Stack>
  );
}
