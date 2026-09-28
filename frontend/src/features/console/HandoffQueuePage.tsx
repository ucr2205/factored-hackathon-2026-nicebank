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
import { formatDateTime } from "../../app/i18n";
import { DISPUTE_TYPES, LANGS, queueLabel, REASONS } from "./labels";
import { elapsed, PriorityBadge, priorityBar, WaitTime } from "./priority";

function QueueSummary({ items, status }: { items: HandoffSummary[]; status: "open" | "claimed" }) {
  if (items.length === 0) return null;
  const high = items.filter((h) => h.priority === "high").length;
  const oldest = items.reduce((a, b) => (a.created_at < b.created_at ? a : b));
  const parts = [`${items.length} ${items.length === 1 ? "caso" : "casos"}`];
  if (high) parts.push(`${high} de prioridad alta`);
  if (status === "open") parts.push(`el que más espera lleva ${elapsed(oldest.created_at)}`);
  return (
    <Typography variant="body2" color="text.secondary">
      {parts.join(" · ")}
    </Typography>
  );
}

export default function HandoffQueuePage() {
  const [status, setStatus] = useState<"open" | "claimed">("open");
  const { data, error, loading } = useResource<HandoffSummary[]>(`/api/handoffs?status=${status}`, 10_000);
  const navigate = useNavigate();
  const open = status === "open";

  return (
    <Stack spacing={2}>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={0.5} sx={{ alignItems: { sm: "baseline" }, justifyContent: "space-between" }}>
        <Box>
          <Typography variant="h5">Casos escalados</Typography>
          <Typography variant="body2" color="text.secondary">
            {open ? "Ordenados por prioridad y por quién lleva más tiempo esperando." : "Casos que ya tiene un agente, del más reciente al más antiguo."}
          </Typography>
        </Box>
        <Typography variant="caption" color="text.secondary">
          Se actualiza cada 10 s
        </Typography>
      </Stack>
      <Tabs value={status} onChange={(_, v) => setStatus(v)}>
        <Tab value="open" label="Abiertos" />
        <Tab value="claimed" label="Tomados" />
      </Tabs>
      {data && <QueueSummary items={data} status={status} />}
      {error && <Alert severity="error">No se pudo cargar la cola: {error}</Alert>}
      <Paper>
        {loading && !data && <LinearProgress />}
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Prioridad</TableCell>
                <TableCell>Motivo</TableCell>
                <TableCell>Idioma</TableCell>
                <TableCell>Cola sugerida</TableCell>
                {open ? <TableCell>Esperando</TableCell> : <TableCell>Tomado por</TableCell>}
                <TableCell>Creado</TableCell>
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
                      {REASONS[h.reason] ?? h.reason}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {DISPUTE_TYPES[h.dispute_type] ?? (h.dispute_type || "—")}
                    </Typography>
                  </TableCell>
                  <TableCell>{LANGS[h.language] ?? h.language}</TableCell>
                  <TableCell>{queueLabel(h.suggested_queue)}</TableCell>
                  {open ? (
                    <TableCell>
                      <WaitTime since={h.created_at} priority={h.priority} exact={formatDateTime(h.created_at, "es")} />
                    </TableCell>
                  ) : (
                    <TableCell>
                      <Typography variant="body2" sx={{ fontWeight: 600, color: brand.burgundy }}>
                        {h.claimed_by}
                      </Typography>
                      {h.claimed_at && (
                        <Typography variant="caption" color="text.secondary">
                          hace {elapsed(h.claimed_at)}
                        </Typography>
                      )}
                    </TableCell>
                  )}
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">
                      {formatDateTime(h.created_at, "es")}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}
              {data?.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6}>
                    <Typography variant="body2" color="text.secondary" sx={{ py: 3, textAlign: "center" }}>
                      {open ? "No hay casos esperando. ¡Todo al día!" : "Nadie ha tomado casos todavía."}
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
