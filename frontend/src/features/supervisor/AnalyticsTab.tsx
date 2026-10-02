import { useMemo, useState } from "react";
import { Alert, Box, Chip, Grid, LinearProgress, Link, Stack, ToggleButton, ToggleButtonGroup, Typography } from "@mui/material";
import { BarChart } from "@mui/x-charts/BarChart";
import {
  Activity,
  Ban,
  CircleAlert,
  Clock,
  ExternalLink,
  FileSearch,
  Gauge,
  Headset,
  Languages,
  ListChecks,
  Lock,
  Mail,
  MessagesSquare,
  Scale,
  ShieldAlert,
  Timer,
  UserCheck,
  Waypoints,
} from "lucide-react";
import type { Analytics, AnalyticsRange } from "../../api/types";
import { useResource } from "../../api/useResource";
import { brand } from "../../app/theme";
import { Section, Stat } from "../../components/Panels";
import { RULE_NAMES } from "../console/auditText";
import { LANGS, REASONS, STEPS } from "../console/labels";

// Categorical colors for how an answer ended. Validated (dataviz validator, light surface): adjacent CVD ΔE ≥ 9.1,
// normal-vision ΔE ≥ 22.9. The stack order below IS the validated order; three hues sit under 3:1 contrast, so
// every chart also carries a legend, tooltips and value labels (color is never the only cue).
const OUTCOMES = [
  { key: "escalate", label: "Pasó a un especialista", color: "#a8325a" },
  { key: "confirm", label: "Esperando confirmación", color: "#2a78d6" },
  { key: "clarify", label: "Pidió más datos", color: "#eda100" },
  { key: "resolve", label: "Resuelto o explicado", color: "#1baf7a" },
  { key: "abstain", label: "Fuera de alcance o bloqueado", color: "#4a3aa7" },
] as const;
const ASSISTANT = { label: "Asistente", color: "#a8325a" };
const BASELINE = { label: "Baseline (todo a una persona)", color: "#9a8f94" }; // neutral reference, not a hue
const SINGLE = brand.burgundy; // one-series bars
const PRIORITY = [
  { key: "high", label: "Prioridad alta", color: "#a8325a" },
  { key: "medium", label: "Prioridad media", color: "#d98aa5" }, // same hue, lighter: an ordinal pair
];
const FUNNEL: Record<string, string> = {
  understood: "Entendió el mensaje",
  found: "Encontró el movimiento",
  proposed: "Propuso una acción",
  confirmed: "El cliente confirmó",
  verified: "Acción verificada",
};
const RANGES: { value: AnalyticsRange; label: string }[] = [
  { value: "24h", label: "24 horas" },
  { value: "7d", label: "7 días" },
  { value: "30d", label: "30 días" },
  { value: "all", label: "Todo" },
];

const PROMETHEUS_URL = import.meta.env.VITE_PROMETHEUS_URL ?? "http://localhost:9090";
const JAEGER_URL = import.meta.env.VITE_JAEGER_URL ?? "http://localhost:16686";

/** Prometheus with several graphs at once (the nicebank:* recording rules). */
function prometheusLink(exprs: string[], window = "6h") {
  const q = new URLSearchParams();
  exprs.forEach((e, i) => {
    q.set(`g${i}.expr`, e);
    q.set(`g${i}.tab`, "0");
    q.set(`g${i}.range_input`, window);
  });
  return `${PROMETHEUS_URL}/graph?${q}`;
}
const jaegerSearch = (tags: Record<string, string>) =>
  `${JAEGER_URL}/search?service=disputes-backend&limit=50&lookback=24h&tags=${encodeURIComponent(JSON.stringify(tags))}`;

const nf = new Intl.NumberFormat("es");
const pct = (n: number, d: number) => (d > 0 ? `${Math.round((n / d) * 100)}%` : "—");
const seconds = (ms: number) => `${(ms / 1000).toFixed(1)} s`;
function duration(s: number) {
  if (!s) return "—";
  if (s < 90) return `${Math.round(s)} s`;
  if (s < 5400) return `${Math.round(s / 60)} min`;
  return `${(s / 3600).toFixed(1)} h`;
}
const showValue = (v: number | null) => (v ? nf.format(v) : "");

export default function AnalyticsTab({ technical }: { technical: boolean }) {
  const [range, setRange] = useState<AnalyticsRange>("24h");
  const { data: a, error } = useResource<Analytics>(`/api/admin/analytics?range=${range}`, 30_000);

  return (
    <Stack spacing={3}>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} sx={{ alignItems: { sm: "center" }, justifyContent: "space-between" }}>
        <ToggleButtonGroup
          size="small"
          exclusive
          value={range}
          onChange={(_, v: AnalyticsRange | null) => v && setRange(v)}
          aria-label="Periodo"
          sx={{ bgcolor: "background.paper", "& .Mui-selected": { bgcolor: `${brand.burgundy} !important`, color: "#FFFFFF !important" } }}
        >
          {RANGES.map((r) => (
            <ToggleButton key={r.value} value={r.value} sx={{ px: 2, fontWeight: 700, textTransform: "none" }}>
              {r.label}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
        {technical && (
          <Stack direction="row" spacing={2} sx={{ flexWrap: "wrap" }}>
            <Link
              href={prometheusLink([
                "nicebank:turns_by_outcome:rate5m",
                "nicebank:escalation_ratio:5m",
                "nicebank:turn_latency_seconds:p95_5m",
                "handoffs_open",
                "nicebank:llm_cost_usd:increase1h",
              ])}
              target="_blank"
              rel="noreferrer"
              sx={{ display: "inline-flex", gap: 0.5, alignItems: "center", fontWeight: 600 }}
            >
              Ver en Prometheus <ExternalLink size={14} />
            </Link>
            <Link href={`${JAEGER_URL}/monitor`} target="_blank" rel="noreferrer" sx={{ display: "inline-flex", gap: 0.5, alignItems: "center", fontWeight: 600 }}>
              Jaeger: rendimiento por operación <ExternalLink size={14} />
            </Link>
          </Stack>
        )}
      </Stack>

      {error && <Alert severity="error">{error}</Alert>}
      {!a && !error && <LinearProgress />}
      {a && <Dashboard a={a} technical={technical} />}
    </Stack>
  );
}

function Dashboard({ a, technical }: { a: Analytics; technical: boolean }) {
  const k = a.kpis;
  const solvedAlone = k.cases_opened + k.explained;

  const timeline = useMemo(() => {
    const fmt =
      a.bucket === "hour"
        ? new Intl.DateTimeFormat("es", { hour: "2-digit", minute: "2-digit" })
        : new Intl.DateTimeFormat("es", { day: "numeric", month: "short" });
    const buckets = [...new Set(a.series.filter((p) => p.mode === "system").map((p) => p.bucket))].sort();
    const count = (b: string, o: string) => a.series.find((p) => p.mode === "system" && p.bucket === b && p.outcome === o)?.count ?? 0;
    return {
      labels: buckets.map((b) => fmt.format(new Date(b))),
      series: OUTCOMES.map((o) => ({ label: o.label, color: o.color, stack: "turns", data: buckets.map((b) => count(b, o.key)), valueFormatter: showValue })),
    };
  }, [a]);

  const comparison = useMemo(() => {
    const total = (mode: string) => a.by_mode.filter((m) => m.mode === mode).reduce((s, m) => s + m.count, 0);
    const share = (mode: string, o: string) => {
      const t = total(mode);
      const n = a.by_mode.find((m) => m.mode === mode && m.outcome === o)?.count ?? 0;
      return t ? Math.round((n / t) * 100) : 0;
    };
    return {
      hasBaseline: total("baseline") > 0,
      labels: OUTCOMES.map((o) => o.label),
      series: [
        { ...ASSISTANT, data: OUTCOMES.map((o) => share("system", o.key)) },
        { ...BASELINE, data: OUTCOMES.map((o) => share("baseline", o.key)) },
      ].map((s) => ({ ...s, valueFormatter: (v: number | null) => (v == null ? "" : `${v}%`), barLabel: (it: { value: number | null }) => (it.value ? `${it.value}%` : "") })),
    };
  }, [a]);

  const handoffs = useMemo(() => {
    const reasons = [...new Set(a.handoffs.map((h) => h.reason))];
    const n = (r: string, p: string) => a.handoffs.find((h) => h.reason === r && h.priority === p)?.count ?? 0;
    reasons.sort((x, y) => PRIORITY.reduce((s, p) => s + n(y, p.key) - n(x, p.key), 0));
    return {
      labels: reasons.map((r) => REASONS[r] ?? r),
      series: PRIORITY.map((p) => ({ label: p.label, color: p.color, stack: "h", data: reasons.map((r) => n(r, p.key)), valueFormatter: showValue })),
    };
  }, [a]);

  const empty = k.turns === 0;
  return (
    <>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Stat hero icon={MessagesSquare} label="Conversaciones con el asistente" value={nf.format(k.conversations)} hint={`${nf.format(k.turns)} respuestas`} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Stat icon={UserCheck} label="Resueltas sin una persona" value={pct(solvedAlone, k.conversations)}
            hint={`${nf.format(k.cases_opened)} disputas abiertas · ${nf.format(k.explained)} cobros explicados`} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Stat icon={Headset} label="Pasaron a un especialista" value={pct(k.escalated, k.conversations)} hint={`${nf.format(k.escalated)} conversaciones`} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Stat icon={Timer} label="Tiempo de respuesta típico" value={seconds(k.p50_latency_ms)} hint={`El 5% más lento: ${seconds(k.p95_latency_ms)}`} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Stat icon={Clock} label="Casos esperando ahora" value={nf.format(k.handoffs_open)} hint={`${nf.format(k.handoffs_claimed)} en atención · ${nf.format(k.handoffs_closed)} cerrados`} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Stat icon={Gauge} label="Tiempo hasta que un especialista toma el caso" value={duration(k.median_claim_seconds)} hint="Mediana del periodo" />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Stat icon={Lock} label="Tarjetas bloqueadas" value={nf.format(k.cards_blocked)} hint="Siempre con código de verificación" />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Stat icon={Mail} label="Correos al cliente" value={nf.format(k.emails_sent)}
            hint={k.emails_failed ? `${nf.format(k.emails_failed)} no se pudieron entregar` : "Todos entregados"} />
        </Grid>
      </Grid>

      <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", rowGap: 1 }}>
        <Chip icon={<ShieldAlert size={16} />} variant="outlined" color="primary" label={`${nf.format(k.injections_blocked)} intentos de manipulación bloqueados`} />
        <Chip icon={<CircleAlert size={16} />} variant="outlined" color="primary" label={`${nf.format(k.tech_failures)} fallas técnicas (pasaron a una persona)`} />
        <Chip icon={<Scale size={16} />} variant="outlined" color="primary"
          label={`Especialistas: ${nf.format(k.accepted)} disputas aceptadas · ${nf.format(k.rejected)} rechazadas`} />
      </Stack>

      {empty ? (
        <Alert severity="info">Todavía no hay conversaciones en este periodo. Prueba con "7 días" o "Todo".</Alert>
      ) : (
        <Grid container spacing={2}>
          <Grid size={12}>
            <Section icon={Activity} title="Respuestas del asistente en el tiempo" subtitle={`Cuántas respuestas dio por ${a.bucket === "hour" ? "hora" : "día"} y cómo terminó cada una.`}>
              <BarChart
                height={300}
                xAxis={[{ scaleType: "band", data: timeline.labels }]}
                yAxis={[{ valueFormatter: (v: number) => nf.format(v) }]}
                series={timeline.series}
                borderRadius={4}
                grid={{ horizontal: true }}
                margin={{ left: 8, right: 8 }}
              />
            </Section>
          </Grid>

          <Grid size={{ xs: 12, md: 6 }}>
            <Section icon={Scale} title="Asistente vs. baseline" subtitle="Porcentaje de respuestas de cada uno según cómo terminaron. El baseline pasa toda disputa a una persona.">
              {comparison.hasBaseline ? (
                <BarChart
                  height={320}
                  layout="horizontal"
                  yAxis={[{ scaleType: "band", data: comparison.labels, width: 170 }]}
                  xAxis={[{ max: 100, valueFormatter: (v: number) => `${v}%` }]}
                  series={comparison.series}
                  borderRadius={4}
                  grid={{ vertical: true }}
                />
              ) : (
                <Typography variant="body2" color="text.secondary">
                  No hay respuestas del baseline en este periodo. El arnés de evaluación las genera con <code>?mode=baseline</code>.
                </Typography>
              )}
            </Section>
          </Grid>

          <Grid size={{ xs: 12, md: 6 }}>
            <Section icon={ListChecks} title="Qué regla decidió cada respuesta" subtitle="Las 10 reglas de la política que más se aplicaron.">
              <BarChart
                height={320}
                layout="horizontal"
                xAxis={[{ valueFormatter: (v: number) => nf.format(v) }]}
                yAxis={[{ scaleType: "band", data: a.top_rules.map((r) => RULE_NAMES[r.label] ?? r.label), width: 190 }]}
                series={[{ data: a.top_rules.map((r) => r.count), color: SINGLE, label: "Respuestas", valueFormatter: showValue, barLabel: "value", barLabelPlacement: "outside" }]}
                borderRadius={4}
                hideLegend
                grid={{ vertical: true }}
              />
              {technical && (
                <Typography variant="caption" color="text.secondary" sx={{ fontFamily: "monospace" }}>
                  {a.top_rules.map((r) => `${r.label}=${r.count}`).join(" · ")}
                </Typography>
              )}
            </Section>
          </Grid>

          <Grid size={{ xs: 12, md: 6 }}>
            <Section icon={Waypoints} title="Hasta dónde llegan las conversaciones" subtitle="Conversaciones que alcanzaron cada paso. Ninguna acción se ejecuta sin confirmación.">
              <BarChart
                height={260}
                layout="horizontal"
                xAxis={[{ valueFormatter: (v: number) => nf.format(v) }]}
                yAxis={[{ scaleType: "band", data: a.funnel.map((f) => FUNNEL[f.step] ?? f.step), width: 170 }]}
                series={[{ data: a.funnel.map((f) => f.sessions), color: SINGLE, label: "Conversaciones", valueFormatter: showValue, barLabel: "value", barLabelPlacement: "outside" }]}
                borderRadius={4}
                hideLegend
                grid={{ vertical: true }}
              />
            </Section>
          </Grid>

          <Grid size={{ xs: 12, md: 6 }}>
            <Section icon={Headset} title="Casos para especialistas por motivo" subtitle="Creados en el periodo, según la prioridad con que llegaron a la cola.">
              {handoffs.labels.length ? (
                <BarChart
                  height={260}
                  layout="horizontal"
                  xAxis={[{ valueFormatter: (v: number) => nf.format(v) }]}
                  yAxis={[{ scaleType: "band", data: handoffs.labels, width: 190 }]}
                  series={handoffs.series}
                  borderRadius={4}
                  grid={{ vertical: true }}
                />
              ) : (
                <Typography variant="body2" color="text.secondary">
                  Ningún caso pasó a un especialista en este periodo.
                </Typography>
              )}
            </Section>
          </Grid>

          <Grid size={{ xs: 12, md: 6 }}>
            <Section icon={FileSearch} title="Dónde se va el tiempo" subtitle="Promedio por paso del turno (milisegundos). El detalle de cada caso está en Jaeger.">
              <BarChart
                height={260}
                layout="horizontal"
                xAxis={[{ valueFormatter: (v: number) => nf.format(v) }]}
                yAxis={[{ scaleType: "band", data: a.step_latency.map((s) => (s.step === "respond" ? "Turno completo" : STEPS[s.step] ?? s.step)), width: 150 }]}
                series={[
                  {
                    data: a.step_latency.map((s) => Math.round(s.avg_ms)),
                    color: SINGLE,
                    label: "Promedio (ms)",
                    valueFormatter: (v: number | null) => (v == null ? "" : `${nf.format(v)} ms`),
                    barLabel: "value",
                    barLabelPlacement: "outside",
                  },
                ]}
                borderRadius={4}
                hideLegend
                grid={{ vertical: true }}
              />
            </Section>
          </Grid>

          <Grid size={{ xs: 12, md: 6 }}>
            <Section icon={Languages} title="Idioma de las conversaciones" subtitle="Español y portugués se atienden con las mismas reglas.">
              <Stack spacing={1.5} sx={{ pt: 1 }}>
                {a.by_lang.map((l) => {
                  const total = a.by_lang.reduce((s, x) => s + x.count, 0);
                  const share = total ? (l.count / total) * 100 : 0;
                  return (
                    <Box key={l.label}>
                      <Stack direction="row" sx={{ justifyContent: "space-between", mb: 0.5 }}>
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>
                          {LANGS[l.label] ?? (l.label || "Sin idioma")}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {nf.format(l.count)} · {Math.round(share)}%
                        </Typography>
                      </Stack>
                      <LinearProgress variant="determinate" value={share} sx={{ height: 10, borderRadius: 5 }} />
                    </Box>
                  );
                })}
              </Stack>
              {technical && (
                <Stack direction="row" spacing={2} sx={{ mt: 2, flexWrap: "wrap" }}>
                  <Link href={jaegerSearch({ "chat.outcome": "escalate" })} target="_blank" rel="noreferrer" sx={{ display: "inline-flex", gap: 0.5, alignItems: "center" }}>
                    Trazas de escalamientos <ExternalLink size={14} />
                  </Link>
                  <Link href={jaegerSearch({ error: "true" })} target="_blank" rel="noreferrer" sx={{ display: "inline-flex", gap: 0.5, alignItems: "center" }}>
                    Trazas con error <Ban size={14} />
                  </Link>
                </Stack>
              )}
            </Section>
          </Grid>
        </Grid>
      )}
    </>
  );
}
