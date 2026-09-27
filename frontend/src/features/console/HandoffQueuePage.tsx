import { useState } from "react";
import { useNavigate } from "react-router";
import {
  Alert,
  Chip,
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
import { formatDateTime } from "../../app/i18n";
import { DISPUTE_TYPES, LANGS, PRIORITY_COLOR, PRIORITY_LABEL, REASONS } from "./labels";

export default function HandoffQueuePage() {
  const [status, setStatus] = useState<"open" | "claimed">("open");
  const { data, error, loading } = useResource<HandoffSummary[]>(`/api/handoffs?status=${status}`, 10_000);
  const navigate = useNavigate();

  return (
    <Stack spacing={2}>
      <Stack direction="row" sx={{ alignItems: "baseline", justifyContent: "space-between" }}>
        <Typography variant="h5">Casos escalados</Typography>
        <Typography variant="body2" color="text.secondary">
          Se actualiza cada 10 s
        </Typography>
      </Stack>
      <Tabs value={status} onChange={(_, v) => setStatus(v)}>
        <Tab value="open" label="Abiertos" />
        <Tab value="claimed" label="Tomados" />
      </Tabs>
      {error && <Alert severity="error">No se pudo cargar la cola: {error}</Alert>}
      <Paper>
        {loading && !data && <LinearProgress />}
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Prioridad</TableCell>
                <TableCell>Motivo</TableCell>
                <TableCell>Tipo</TableCell>
                <TableCell>Idioma</TableCell>
                <TableCell>Cola sugerida</TableCell>
                <TableCell>Creado</TableCell>
                {status === "claimed" && <TableCell>Agente</TableCell>}
              </TableRow>
            </TableHead>
            <TableBody>
              {data?.map((h) => (
                <TableRow key={h.handoff_id} hover sx={{ cursor: "pointer" }} onClick={() => navigate(`/console/${h.handoff_id}`)}>
                  <TableCell>
                    <Chip size="small" color={PRIORITY_COLOR[h.priority]} label={PRIORITY_LABEL[h.priority]} />
                  </TableCell>
                  <TableCell>{REASONS[h.reason] ?? h.reason}</TableCell>
                  <TableCell>{DISPUTE_TYPES[h.dispute_type] ?? (h.dispute_type || "—")}</TableCell>
                  <TableCell>{LANGS[h.language] ?? h.language}</TableCell>
                  <TableCell>
                    <code>{h.suggested_queue}</code>
                  </TableCell>
                  <TableCell>{formatDateTime(h.created_at, "es")}</TableCell>
                  {status === "claimed" && <TableCell>{h.claimed_by}</TableCell>}
                </TableRow>
              ))}
              {data?.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7}>
                    <Typography variant="body2" color="text.secondary" sx={{ py: 3, textAlign: "center" }}>
                      No hay casos en esta cola.
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
