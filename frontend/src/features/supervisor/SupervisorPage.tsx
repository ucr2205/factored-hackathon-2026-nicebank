import {
  Alert,
  Box,
  Chip,
  LinearProgress,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import type { AdminConfig, Summary } from "../../api/types";
import { useResource } from "../../api/useResource";
import { LANGS } from "../console/labels";

const OUTCOMES: Record<string, string> = {
  resolve: "Resuelto",
  clarify: "Aclaración",
  abstain: "Abstención",
  escalate: "Escalado",
  confirm: "Pide confirmación",
};

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Paper sx={{ p: 2, flex: 1, minWidth: 150 }}>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="h5">{value}</Typography>
      {hint && (
        <Typography variant="caption" color="text.secondary">
          {hint}
        </Typography>
      )}
    </Paper>
  );
}

export default function SupervisorPage() {
  const summary = useResource<Summary>("/api/admin/summary", 15_000);
  const config = useResource<AdminConfig>("/api/admin/config");
  const s = summary.data;
  const c = config.data;

  return (
    <Stack spacing={3}>
      <Typography variant="h5">Supervisión</Typography>
      {(summary.error || config.error) && <Alert severity="error">{summary.error ?? config.error}</Alert>}
      {!s && <LinearProgress />}

      {s && (
        <>
          <Stack direction="row" spacing={2} sx={{ flexWrap: "wrap", rowGap: 2 }}>
            <Stat label="Turnos atendidos" value={String(s.turns)} hint="Medición local (offline), no producción" />
            <Stat label="Latencia p50" value={`${Math.round(s.p50_latency_ms)} ms`} />
            <Stat label="Latencia p95" value={`${Math.round(s.p95_latency_ms)} ms`} />
            <Stat label="Handoffs abiertos" value={String(s.open_handoffs)} />
          </Stack>
          <Paper>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Resultado del turno</TableCell>
                    <TableCell>Idioma</TableCell>
                    <TableCell>Modo</TableCell>
                    <TableCell align="right">Turnos</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {s.by_outcome.map((o) => (
                    <TableRow key={`${o.outcome}-${o.lang}-${o.mode}`}>
                      <TableCell>{OUTCOMES[o.outcome] ?? o.outcome}</TableCell>
                      <TableCell>{LANGS[o.lang] ?? o.lang}</TableCell>
                      <TableCell>{o.mode === "baseline" ? "Baseline (reglas)" : "Sistema"}</TableCell>
                      <TableCell align="right">{o.count}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </>
      )}

      {c && (
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>
            Configuración activa
          </Typography>
          <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", rowGap: 1, mb: 2 }}>
            <Chip label={`Política v${c.policy_version}`} color="primary" />
            <Chip label={`LLM: ${c.llm_provider} (${c.prompt_version})`} variant="outlined" />
            <Chip label={`Clasificador: ${c.classifier_model}`} variant="outlined" />
            <Chip label={`Fecha de demo: ${c.demo_today}`} variant="outlined" />
          </Stack>
          <Typography variant="caption" color="text.secondary">
            {c.policy_origin}
          </Typography>
          <TableContainer sx={{ mt: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Tipo de disputa</TableCell>
                  <TableCell>Acción automática</TableCell>
                  <TableCell align="right">Máx. automático (USD)</TableCell>
                  <TableCell align="right">Antigüedad máx. (días)</TableCell>
                  <TableCell>Escalamiento</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {c.policy.dispute_types.map((d) => (
                  <TableRow key={d.id}>
                    <TableCell>{d.display_name.es}</TableCell>
                    <TableCell>
                      <code>{d.auto_action}</code>
                    </TableCell>
                    <TableCell align="right">{d.max_auto_amount_usd || "—"}</TableCell>
                    <TableCell align="right">{d.eligible_if.max_age_days || "—"}</TableCell>
                    <TableCell>{d.escalate_if?.map((e) => e.rule_id).join(", ") || "siempre"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
          <Box sx={{ mt: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              Reglas globales
            </Typography>
            {c.policy.globals.rules.map((r) => (
              <Typography key={r.rule_id} variant="body2" sx={{ mb: 0.5 }}>
                <code>{r.rule_id}</code> → {r.outcome}: {r.description}
              </Typography>
            ))}
          </Box>
        </Paper>
      )}
    </Stack>
  );
}
