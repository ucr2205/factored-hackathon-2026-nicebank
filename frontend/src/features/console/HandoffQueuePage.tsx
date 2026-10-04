// Agent console queue (/console): GET /api/handoffs?status=open|claimed|closed, refreshed every 10 s; a row opens
// the case detail.
import { useState } from "react";
import { useNavigate } from "react-router";
import {
  Alert,
  Box,
  LinearProgress,
  Paper,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  Typography,
} from "@mui/material";
import type { HandoffSummary } from "../../api/types";
import { useResource } from "../../api/useResource";
import { brand } from "../../app/theme";
import { formatDateTime, useLang } from "../../app/i18n";
import { DISPUTE_TYPES, LANGS, queueLabel, REASONS } from "./labels";
import { elapsed, PriorityBadge, priorityBar, WaitTime } from "./priority";

type QueueStatus = "open" | "claimed" | "closed";

const TEXT = {
  es: {
    title: "Casos escalados",
    subtitle: {
      open: "Ordenados por prioridad y por quién lleva más tiempo esperando.",
      claimed: "Casos que ya tiene un agente, del más reciente al más antiguo.",
      closed: "Casos cerrados por un agente, con su resolución.",
    },
    refresh: "Se actualiza cada 10 s",
    tabs: { open: "Abiertos", claimed: "Tomados", closed: "Cerrados" },
    loadError: "No se pudo cargar la cola:",
    priority: "Prioridad",
    reason: "Motivo",
    language: "Idioma",
    queue: "Cola sugerida",
    waiting: "Esperando",
    claimedBy: "Tomado por",
    created: "Creado",
    ago: (t: string) => `hace ${t}`,
    empty: { open: "No hay casos esperando. ¡Todo al día!", claimed: "Nadie ha tomado casos todavía.", closed: "Todavía no hay casos cerrados." },
    cases: (n: number) => `${n} ${n === 1 ? "caso" : "casos"}`,
    high: (n: number) => `${n} de prioridad alta`,
    oldest: (t: string) => `el que más espera lleva ${t}`,
  },
  pt: {
    title: "Casos escalonados",
    subtitle: {
      open: "Ordenados por prioridade e por quem está esperando há mais tempo.",
      claimed: "Casos que já estão com um agente, do mais recente ao mais antigo.",
      closed: "Casos encerrados por um agente, com a resolução.",
    },
    refresh: "Atualiza a cada 10 s",
    tabs: { open: "Abertos", claimed: "Assumidos", closed: "Encerrados" },
    loadError: "Não foi possível carregar a fila:",
    priority: "Prioridade",
    reason: "Motivo",
    language: "Idioma",
    queue: "Fila sugerida",
    waiting: "Aguardando",
    claimedBy: "Assumido por",
    created: "Criado",
    ago: (t: string) => `há ${t}`,
    empty: { open: "Não há casos aguardando. Tudo em dia!", claimed: "Ninguém assumiu casos ainda.", closed: "Ainda não há casos encerrados." },
    cases: (n: number) => `${n} ${n === 1 ? "caso" : "casos"}`,
    high: (n: number) => `${n} de prioridade alta`,
    oldest: (t: string) => `o mais antigo espera há ${t}`,
  },
} as const;

function QueueSummary({ items, status }: { items: HandoffSummary[]; status: QueueStatus }) {
  const { lang } = useLang();
  const tx = TEXT[lang];
  if (items.length === 0) return null;
  const high = items.filter((h) => h.priority === "high").length;
  const oldest = items.reduce((a, b) => (a.created_at < b.created_at ? a : b));
  const parts = [tx.cases(items.length)];
  if (high) parts.push(tx.high(high));
  if (status === "open") parts.push(tx.oldest(elapsed(oldest.created_at)));
  return (
    <Typography variant="body2" color="text.secondary">
      {parts.join(" · ")}
    </Typography>
  );
}

/** Tabbed table of escalated cases in the order the backend returns them (open: priority, then longest wait). */
export default function HandoffQueuePage() {
  const { lang } = useLang();
  const tx = TEXT[lang];
  const [status, setStatus] = useState<QueueStatus>("open");
  const { data, error, loading } = useResource<HandoffSummary[]>(`/api/handoffs?status=${status}`, 10_000);
  const navigate = useNavigate();
  const open = status === "open";

  return (
    <Stack spacing={2}>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={0.5} sx={{ alignItems: { sm: "baseline" }, justifyContent: "space-between" }}>
        <Box>
          <Typography variant="h5">{tx.title}</Typography>
          <Typography variant="body2" color="text.secondary">
            {tx.subtitle[status]}
          </Typography>
        </Box>
        <Typography variant="caption" color="text.secondary">
          {tx.refresh}
        </Typography>
      </Stack>
      <Tabs value={status} onChange={(_, v) => setStatus(v)}>
        <Tab value="open" label={tx.tabs.open} />
        <Tab value="claimed" label={tx.tabs.claimed} />
        <Tab value="closed" label={tx.tabs.closed} />
      </Tabs>
      {data && <QueueSummary items={data} status={status} />}
      {error && <Alert severity="error">{tx.loadError} {error}</Alert>}
      <Paper>
        {loading && !data && <LinearProgress />}
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>{tx.priority}</TableCell>
                <TableCell>{tx.reason}</TableCell>
                <TableCell>{tx.language}</TableCell>
                <TableCell>{tx.queue}</TableCell>
                {open ? <TableCell>{tx.waiting}</TableCell> : <TableCell>{tx.claimedBy}</TableCell>}
                <TableCell>{tx.created}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data?.map((h) => (
                <TableRow
                  key={h.handoff_id}
                  hover
                  sx={{ cursor: "pointer", "& > td": { py: 1.25 } }}
                  onClick={() => navigate(`/console/${h.handoff_id}`)}
                >
                  <TableCell sx={{ borderLeft: `4px solid ${priorityBar(h.priority)}` }}>
                    <PriorityBadge priority={h.priority} />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {REASONS[lang][h.reason] ?? h.reason}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {DISPUTE_TYPES[lang][h.dispute_type] ?? (h.dispute_type || "—")}
                    </Typography>
                  </TableCell>
                  <TableCell>{LANGS[lang][h.language] ?? h.language}</TableCell>
                  <TableCell>{queueLabel(h.suggested_queue, lang)}</TableCell>
                  {open ? (
                    <TableCell>
                      <WaitTime since={h.created_at} priority={h.priority} exact={formatDateTime(h.created_at, lang)} />
                    </TableCell>
                  ) : (
                    <TableCell>
                      <Typography variant="body2" sx={{ fontWeight: 600, color: brand.burgundy }}>
                        {h.claimed_by}
                      </Typography>
                      {h.claimed_at && (
                        <Typography variant="caption" color="text.secondary">
                          {tx.ago(elapsed(h.claimed_at))}
                        </Typography>
                      )}
                    </TableCell>
                  )}
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">
                      {formatDateTime(h.created_at, lang)}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}
              {data?.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6}>
                    <Typography variant="body2" color="text.secondary" sx={{ py: 3, textAlign: "center" }}>
                      {tx.empty[status]}
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>
    </Stack>
  );
}
