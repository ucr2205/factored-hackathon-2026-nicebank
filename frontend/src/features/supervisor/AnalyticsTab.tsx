// Supervisor summary tab: KPIs and charts from GET /api/admin/analytics?range=24h|7d|30d|all (refreshed every
// 30 s), assistant vs. baseline included; technical mode adds links to Prometheus and Jaeger.
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
import { JAEGER_URL, TOOLS_URL } from "../../api/client";
import { useResource } from "../../api/useResource";
import { LOCALES, useLang, type Lang } from "../../app/i18n";
import { brand } from "../../app/theme";
import { Section, Stat } from "../../components/Panels";
import { RULE_NAMES } from "../console/auditText";
import { LANGS, REASONS, STEPS } from "../console/labels";

// Categorical colors for how an answer ended. Validated (dataviz validator, light surface): adjacent CVD ΔE ≥ 9.1,
// normal-vision ΔE ≥ 22.9. The stack order below IS the validated order; three hues sit under 3:1 contrast, so
// every chart also carries a legend, tooltips and value labels (color is never the only cue).
const OUTCOMES = [
  { key: "escalate", color: "#a8325a" },
  { key: "confirm", color: "#2a78d6" },
  { key: "clarify", color: "#eda100" },
  { key: "resolve", color: "#1baf7a" },
  { key: "abstain", color: "#4a3aa7" },
] as const;
const ASSISTANT_COLOR = "#a8325a";
const BASELINE_COLOR = "#9a8f94"; // neutral reference, not a hue
const SINGLE = brand.burgundy; // one-series bars
const PRIORITY = [
  { key: "high", color: "#a8325a" },
  { key: "medium", color: "#d98aa5" }, // same hue, lighter: an ordinal pair
] as const;
const RANGES: AnalyticsRange[] = ["24h", "7d", "30d", "all"];

const TEXT = {
  es: {
    outcomes: {
      escalate: "Pasó a un especialista",
      confirm: "Esperando confirmación",
      clarify: "Pidió más datos",
      resolve: "Resuelto o explicado",
      abstain: "Fuera de alcance o bloqueado",
    },
    assistant: "Asistente",
    baseline: "Baseline (todo a una persona)",
    priority: { high: "Prioridad alta", medium: "Prioridad media" },
    funnel: {
      understood: "Entendió el mensaje",
      found: "Encontró el movimiento",
      proposed: "Propuso una acción",
      confirmed: "El cliente confirmó",
      verified: "Acción verificada",
    } as Record<string, string>,
    ranges: { "24h": "24 horas", "7d": "7 días", "30d": "30 días", all: "Todo" },
    period: "Periodo",
    prometheus: "Ver en Prometheus",
    jaegerMonitor: "Jaeger: rendimiento por operación",
    conversations: "Conversaciones con el asistente",
    replies: (n: string) => `${n} respuestas`,
    solvedAlone: "Resueltas sin una persona",
    solvedHint: (opened: string, explained: string) => `${opened} disputas abiertas · ${explained} cobros explicados`,
    escalated: "Pasaron a un especialista",
    conversationsN: (n: string) => `${n} conversaciones`,
    latency: "Tiempo de respuesta típico",
    slowest: (s: string) => `El 5% más lento: ${s}`,
    waiting: "Casos esperando ahora",
    waitingHint: (claimed: string, closed: string) => `${claimed} en atención · ${closed} cerrados`,
    claimTime: "Tiempo hasta que un especialista toma el caso",
    median: "Mediana del periodo",
    blocked: "Tarjetas bloqueadas",
    blockedHint: "Siempre con código de verificación",
    emails: "Correos al cliente",
    emailsFailed: (n: string) => `${n} no se pudieron entregar`,
    emailsOk: "Todos entregados",
    injections: (n: string) => `${n} intentos de manipulación bloqueados`,
    techFailures: (n: string) => `${n} fallas técnicas (pasaron a una persona)`,
    specialists: (accepted: string, rejected: string) => `Especialistas: ${accepted} disputas aceptadas · ${rejected} rechazadas`,
    empty: 'Todavía no hay conversaciones en este periodo. Prueba con "7 días" o "Todo".',
    timelineTitle: "Respuestas del asistente en el tiempo",
    timelineSubtitle: (hour: boolean) => `Cuántas respuestas dio por ${hour ? "hora" : "día"} y cómo terminó cada una.`,
    comparisonTitle: "Asistente vs. baseline",
    comparisonSubtitle: "Porcentaje de respuestas de cada uno según cómo terminaron. El baseline pasa toda disputa a una persona.",
    noBaseline: ["No hay respuestas del baseline en este periodo. El arnés de evaluación las genera con", "."],
    rulesTitle: "Qué regla decidió cada respuesta",
    rulesSubtitle: "Las 10 reglas de la política que más se aplicaron.",
    repliesSeries: "Respuestas",
    funnelTitle: "Hasta dónde llegan las conversaciones",
    funnelSubtitle: "Conversaciones que alcanzaron cada paso. Ninguna acción se ejecuta sin confirmación.",
    conversationsSeries: "Conversaciones",
    handoffsTitle: "Casos para especialistas por motivo",
    handoffsSubtitle: "Creados en el periodo, según la prioridad con que llegaron a la cola.",
    noHandoffs: "Ningún caso pasó a un especialista en este periodo.",
    stepsTitle: "Dónde se va el tiempo",
    stepsSubtitle: "Promedio por paso del turno (milisegundos). El detalle de cada caso está en Jaeger.",
    fullTurn: "Turno completo",
    average: "Promedio (ms)",
    langTitle: "Idioma de las conversaciones",
    langSubtitle: "Español y portugués se atienden con las mismas reglas.",
    noLang: "Sin idioma",
    escalationTraces: "Trazas de escalamientos",
    errorTraces: "Trazas con error",
  },
  pt: {
    outcomes: {
      escalate: "Passou para um especialista",
      confirm: "Aguardando confirmação",
      clarify: "Pediu mais dados",
      resolve: "Resolvido ou explicado",
      abstain: "Fora do escopo ou bloqueado",
    },
    assistant: "Assistente",
    baseline: "Baseline (tudo para uma pessoa)",
    priority: { high: "Prioridade alta", medium: "Prioridade média" },
    funnel: {
      understood: "Entendeu a mensagem",
      found: "Encontrou a movimentação",
      proposed: "Propôs uma ação",
      confirmed: "O cliente confirmou",
      verified: "Ação verificada",
    } as Record<string, string>,
    ranges: { "24h": "24 horas", "7d": "7 dias", "30d": "30 dias", all: "Tudo" },
    period: "Período",
    prometheus: "Ver no Prometheus",
    jaegerMonitor: "Jaeger: desempenho por operação",
    conversations: "Conversas com o assistente",
    replies: (n: string) => `${n} respostas`,
    solvedAlone: "Resolvidas sem uma pessoa",
    solvedHint: (opened: string, explained: string) => `${opened} contestações abertas · ${explained} cobranças explicadas`,
    escalated: "Passaram para um especialista",
    conversationsN: (n: string) => `${n} conversas`,
    latency: "Tempo de resposta típico",
    slowest: (s: string) => `Os 5% mais lentos: ${s}`,
    waiting: "Casos aguardando agora",
    waitingHint: (claimed: string, closed: string) => `${claimed} em atendimento · ${closed} encerrados`,
    claimTime: "Tempo até um especialista assumir o caso",
    median: "Mediana do período",
    blocked: "Cartões bloqueados",
    blockedHint: "Sempre com código de verificação",
    emails: "E-mails ao cliente",
    emailsFailed: (n: string) => `${n} não puderam ser entregues`,
    emailsOk: "Todos entregues",
    injections: (n: string) => `${n} tentativas de manipulação bloqueadas`,
    techFailures: (n: string) => `${n} falhas técnicas (passaram para uma pessoa)`,
    specialists: (accepted: string, rejected: string) => `Especialistas: ${accepted} contestações aceitas · ${rejected} recusadas`,
    empty: 'Ainda não há conversas neste período. Tente "7 dias" ou "Tudo".',
    timelineTitle: "Respostas do assistente ao longo do tempo",
    timelineSubtitle: (hour: boolean) => `Quantas respostas deu por ${hour ? "hora" : "dia"} e como terminou cada uma.`,
    comparisonTitle: "Assistente vs. baseline",
    comparisonSubtitle: "Porcentagem de respostas de cada um segundo como terminaram. O baseline passa toda contestação para uma pessoa.",
    noBaseline: ["Não há respostas do baseline neste período. O harness de avaliação as gera com", "."],
    rulesTitle: "Qual regra decidiu cada resposta",
    rulesSubtitle: "As 10 regras da política mais aplicadas.",
    repliesSeries: "Respostas",
    funnelTitle: "Até onde as conversas chegam",
    funnelSubtitle: "Conversas que alcançaram cada etapa. Nenhuma ação é executada sem confirmação.",
    conversationsSeries: "Conversas",
    handoffsTitle: "Casos para especialistas por motivo",
    handoffsSubtitle: "Criados no período, segundo a prioridade com que chegaram à fila.",
    noHandoffs: "Nenhum caso passou para um especialista neste período.",
    stepsTitle: "Onde o tempo é gasto",
    stepsSubtitle: "Média por etapa do turno (milissegundos). O detalhe de cada caso está no Jaeger.",
    fullTurn: "Turno completo",
    average: "Média (ms)",
    langTitle: "Idioma das conversas",
    langSubtitle: "Espanhol e português são atendidos com as mesmas regras.",
    noLang: "Sem idioma",
    escalationTraces: "Traces de escalonamentos",
    errorTraces: "Traces com erro",
  },
} as const;

const PROMETHEUS_URL = `${TOOLS_URL}/prometheus`;

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

const pct = (n: number, d: number) => (d > 0 ? `${Math.round((n / d) * 100)}%` : "—");
function duration(s: number) {
  if (!s) return "—";
  if (s < 90) return `${Math.round(s)} s`;
  if (s < 5400) return `${Math.round(s / 60)} min`;
  return `${(s / 3600).toFixed(1)} h`;
}

/** Number formatters in the UI locale. */
function formatters(lang: Lang) {
  const nf = new Intl.NumberFormat(LOCALES[lang]);
  const one = new Intl.NumberFormat(LOCALES[lang], { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  return {
    nf,
    seconds: (ms: number) => `${one.format(ms / 1000)} s`,
    showValue: (v: number | null) => (v ? nf.format(v) : ""),
  };
}

/** Period selector and dashboard; `technical` adds Prometheus/Jaeger links and raw rule counts. */
export default function AnalyticsTab({ technical }: { technical: boolean }) {
  const { lang } = useLang();
  const tx = TEXT[lang];
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
          aria-label={tx.period}
          sx={{ bgcolor: "background.paper", "& .Mui-selected": { bgcolor: `${brand.burgundy} !important`, color: "#FFFFFF !important" } }}
        >
          {RANGES.map((r) => (
            <ToggleButton key={r} value={r} sx={{ px: 2, fontWeight: 700, textTransform: "none" }}>
              {tx.ranges[r]}
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
              {tx.prometheus} <ExternalLink size={14} />
            </Link>
            <Link href={`${JAEGER_URL}/monitor`} target="_blank" rel="noreferrer" sx={{ display: "inline-flex", gap: 0.5, alignItems: "center", fontWeight: 600 }}>
              {tx.jaegerMonitor} <ExternalLink size={14} />
            </Link>
          </Stack>
        )}
      </Stack>

      {error && <Alert severity="error">{error}</Alert>}
      {!a && !error && <LinearProgress />}
      {a && <Dashboard a={a} technical={technical} lang={lang} />}
    </Stack>
  );
}

function Dashboard({ a, technical, lang }: { a: Analytics; technical: boolean; lang: Lang }) {
  const tx = TEXT[lang];
  const { nf, seconds, showValue } = useMemo(() => formatters(lang), [lang]);
  const k = a.kpis;
  const solvedAlone = k.cases_opened + k.explained;

  const timeline = useMemo(() => {
    const fmt =
      a.bucket === "hour"
        ? new Intl.DateTimeFormat(LOCALES[lang], { hour: "2-digit", minute: "2-digit" })
        : new Intl.DateTimeFormat(LOCALES[lang], { day: "numeric", month: "short" });
    const buckets = [...new Set(a.series.filter((p) => p.mode === "system").map((p) => p.bucket))].sort();
    const count = (b: string, o: string) => a.series.find((p) => p.mode === "system" && p.bucket === b && p.outcome === o)?.count ?? 0;
    return {
      labels: buckets.map((b) => fmt.format(new Date(b))),
      series: OUTCOMES.map((o) => ({
        label: TEXT[lang].outcomes[o.key],
        color: o.color,
        stack: "turns",
        data: buckets.map((b) => count(b, o.key)),
        valueFormatter: showValue,
      })),
    };
  }, [a, lang, showValue]);

  const comparison = useMemo(() => {
    const total = (mode: string) => a.by_mode.filter((m) => m.mode === mode).reduce((s, m) => s + m.count, 0);
    const share = (mode: string, o: string) => {
      const t = total(mode);
      const n = a.by_mode.find((m) => m.mode === mode && m.outcome === o)?.count ?? 0;
      return t ? Math.round((n / t) * 100) : 0;
    };
    return {
      hasBaseline: total("baseline") > 0,
      labels: OUTCOMES.map((o) => TEXT[lang].outcomes[o.key]),
      series: [
        { label: TEXT[lang].assistant, color: ASSISTANT_COLOR, data: OUTCOMES.map((o) => share("system", o.key)) },
        { label: TEXT[lang].baseline, color: BASELINE_COLOR, data: OUTCOMES.map((o) => share("baseline", o.key)) },
      ].map((s) => ({ ...s, valueFormatter: (v: number | null) => (v == null ? "" : `${v}%`), barLabel: (it: { value: number | null }) => (it.value ? `${it.value}%` : "") })),
    };
  }, [a, lang]);

  const handoffs = useMemo(() => {
    const reasons = [...new Set(a.handoffs.map((h) => h.reason))];
    const n = (r: string, p: string) => a.handoffs.find((h) => h.reason === r && h.priority === p)?.count ?? 0;
    reasons.sort((x, y) => PRIORITY.reduce((s, p) => s + n(y, p.key) - n(x, p.key), 0));
    return {
      labels: reasons.map((r) => REASONS[lang][r] ?? r),
      series: PRIORITY.map((p) => ({
        label: TEXT[lang].priority[p.key],
        color: p.color,
        stack: "h",
        data: reasons.map((r) => n(r, p.key)),
        valueFormatter: showValue,
      })),
    };
  }, [a, lang, showValue]);

  const empty = k.turns === 0;
  return (
    <>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Stat hero icon={MessagesSquare} label={tx.conversations} value={nf.format(k.conversations)} hint={tx.replies(nf.format(k.turns))} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Stat icon={UserCheck} label={tx.solvedAlone} value={pct(solvedAlone, k.conversations)}
            hint={tx.solvedHint(nf.format(k.cases_opened), nf.format(k.explained))} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Stat icon={Headset} label={tx.escalated} value={pct(k.escalated, k.conversations)} hint={tx.conversationsN(nf.format(k.escalated))} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Stat icon={Timer} label={tx.latency} value={seconds(k.p50_latency_ms)} hint={tx.slowest(seconds(k.p95_latency_ms))} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Stat icon={Clock} label={tx.waiting} value={nf.format(k.handoffs_open)} hint={tx.waitingHint(nf.format(k.handoffs_claimed), nf.format(k.handoffs_closed))} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Stat icon={Gauge} label={tx.claimTime} value={duration(k.median_claim_seconds)} hint={tx.median} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Stat icon={Lock} label={tx.blocked} value={nf.format(k.cards_blocked)} hint={tx.blockedHint} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Stat icon={Mail} label={tx.emails} value={nf.format(k.emails_sent)}
            hint={k.emails_failed ? tx.emailsFailed(nf.format(k.emails_failed)) : tx.emailsOk} />
        </Grid>
      </Grid>

      <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", rowGap: 1 }}>
        <Chip icon={<ShieldAlert size={16} />} variant="outlined" color="primary" label={tx.injections(nf.format(k.injections_blocked))} />
        <Chip icon={<CircleAlert size={16} />} variant="outlined" color="primary" label={tx.techFailures(nf.format(k.tech_failures))} />
        <Chip icon={<Scale size={16} />} variant="outlined" color="primary"
          label={tx.specialists(nf.format(k.accepted), nf.format(k.rejected))} />
      </Stack>

      {empty ? (
        <Alert severity="info">{tx.empty}</Alert>
      ) : (
        <Grid container spacing={2}>
          <Grid size={12}>
            <Section icon={Activity} title={tx.timelineTitle} subtitle={tx.timelineSubtitle(a.bucket === "hour")}>
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
            <Section icon={Scale} title={tx.comparisonTitle} subtitle={tx.comparisonSubtitle}>
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
                  {tx.noBaseline[0]} <code>?mode=baseline</code>
                  {tx.noBaseline[1]}
                </Typography>
              )}
            </Section>
          </Grid>

          <Grid size={{ xs: 12, md: 6 }}>
            <Section icon={ListChecks} title={tx.rulesTitle} subtitle={tx.rulesSubtitle}>
              <BarChart
                height={320}
                layout="horizontal"
                xAxis={[{ valueFormatter: (v: number) => nf.format(v) }]}
                yAxis={[{ scaleType: "band", data: a.top_rules.map((r) => RULE_NAMES[lang][r.label] ?? r.label), width: 190 }]}
                series={[{ data: a.top_rules.map((r) => r.count), color: SINGLE, label: tx.repliesSeries, valueFormatter: showValue, barLabel: "value", barLabelPlacement: "outside" }]}
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
            <Section icon={Waypoints} title={tx.funnelTitle} subtitle={tx.funnelSubtitle}>
              <BarChart
                height={260}
                layout="horizontal"
                xAxis={[{ valueFormatter: (v: number) => nf.format(v) }]}
                yAxis={[{ scaleType: "band", data: a.funnel.map((f) => tx.funnel[f.step] ?? f.step), width: 170 }]}
                series={[{ data: a.funnel.map((f) => f.sessions), color: SINGLE, label: tx.conversationsSeries, valueFormatter: showValue, barLabel: "value", barLabelPlacement: "outside" }]}
                borderRadius={4}
                hideLegend
                grid={{ vertical: true }}
              />
            </Section>
          </Grid>

          <Grid size={{ xs: 12, md: 6 }}>
            <Section icon={Headset} title={tx.handoffsTitle} subtitle={tx.handoffsSubtitle}>
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
                  {tx.noHandoffs}
                </Typography>
              )}
            </Section>
          </Grid>

          <Grid size={{ xs: 12, md: 6 }}>
            <Section icon={FileSearch} title={tx.stepsTitle} subtitle={tx.stepsSubtitle}>
              <BarChart
                height={260}
                layout="horizontal"
                xAxis={[{ valueFormatter: (v: number) => nf.format(v) }]}
                yAxis={[{ scaleType: "band", data: a.step_latency.map((s) => (s.step === "respond" ? tx.fullTurn : STEPS[lang][s.step] ?? s.step)), width: 150 }]}
                series={[
                  {
                    data: a.step_latency.map((s) => Math.round(s.avg_ms)),
                    color: SINGLE,
                    label: tx.average,
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
            <Section icon={Languages} title={tx.langTitle} subtitle={tx.langSubtitle}>
              <Stack spacing={1.5} sx={{ pt: 1 }}>
                {a.by_lang.map((l) => {
                  const total = a.by_lang.reduce((s, x) => s + x.count, 0);
                  const share = total ? (l.count / total) * 100 : 0;
                  return (
                    <Box key={l.label}>
                      <Stack direction="row" sx={{ justifyContent: "space-between", mb: 0.5 }}>
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>
                          {LANGS[lang][l.label] ?? (l.label || tx.noLang)}
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
                    {tx.escalationTraces} <ExternalLink size={14} />
                  </Link>
                  <Link href={jaegerSearch({ error: "true" })} target="_blank" rel="noreferrer" sx={{ display: "inline-flex", gap: 0.5, alignItems: "center" }}>
                    {tx.errorTraces} <Ban size={14} />
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
