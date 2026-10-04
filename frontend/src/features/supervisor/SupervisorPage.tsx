// Supervisor view (/supervisor): the summary tab (AnalyticsTab, lazy) and the configuration-and-rules tab, a
// plain-language (es/pt) reading of GET /api/admin/config (policy version, LLM, classifier and rules).
import { lazy, Suspense, useState } from "react";
import {
  Alert,
  Box,
  Chip,
  FormControlLabel,
  LinearProgress,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Paper,
  Stack,
  Switch,
  Tab,
  Tabs,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from "@mui/material";
import {
  BrainCircuit,
  CalendarDays,
  CircleCheck,
  FileText,
  ListChecks,
  ReceiptText,
  Settings2,
  ShieldCheck,
  Tags,
  type LucideIcon,
} from "lucide-react";
import type { AdminConfig } from "../../api/types";
import { useResource } from "../../api/useResource";
import { LOCALES, useLang, type Lang } from "../../app/i18n";
import { brand } from "../../app/theme";
import { Section } from "../../components/Panels";
import {
  autoActionText,
  classifierLabel,
  conditionText,
  escalationLines,
  escalationRuleIds,
  globalRuleText,
  guarantees,
  modelLabel,
  originLabel,
  statusRuleText,
} from "./policyText";

function Setting({ icon: Icon, label, name, detail }: { icon: LucideIcon; label: string; name: string; detail: string }) {
  return (
    <Paper variant="outlined" sx={{ p: 1.75, flex: 1, minWidth: 220, borderLeft: `3px solid ${brand.burgundy}` }}>
      <Stack direction="row" spacing={1.25}>
        <Box sx={{ color: brand.burgundy, pt: 0.25 }}>
          <Icon size={20} />
        </Box>
        <Box>
          <Typography variant="caption" color="text.secondary">
            {label}
          </Typography>
          <Typography variant="body1" sx={{ fontWeight: 600 }}>
            {name}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {detail}
          </Typography>
        </Box>
      </Stack>
    </Paper>
  );
}

// The charts library loads only when the summary tab is shown.
const AnalyticsTab = lazy(() => import("./AnalyticsTab"));

const longDate = (iso: string, lang: Lang) =>
  new Intl.DateTimeFormat(LOCALES[lang], { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(iso));

const TEXT = {
  es: {
    title: "Supervisión",
    subtitle: "Cómo está atendiendo el asistente y qué reglas sigue.",
    technical: "Ver detalle técnico",
    tabSummary: "Resumen",
    tabConfig: "Configuración y reglas",
    configured: "Cómo está configurado",
    policy: "Política de disputas",
    version: (v: string) => `Versión ${v}`,
    policyDetail: "Reglas de montos, plazos y escalamiento",
    ai: "Inteligencia artificial",
    classifier: "Clasificador de casos",
    demoDate: "Fecha del demo",
    demoDetail: "Los datos son sintéticos y terminan ese día",
    typesTitle: "Qué resuelve solo y qué pasa a una persona",
    typesSubtitle: "Para cada tipo de caso: la acción del asistente, cuándo puede hacerla por su cuenta y a quién pasa el caso si no.",
    colType: "Tipo de caso",
    colAction: "Qué hace el asistente",
    colAlone: "Lo resuelve solo si…",
    colElse: "Si no…",
    explainTitle: "Antes de abrir una disputa",
    explainSubtitle:
      "Si el cobro no es definitivo, el asistente lo explica con el movimiento real del cliente en vez de abrir un caso o pasarlo a una persona.",
    rule: (id: string) => `Regla ${id}`,
    globalTitle: "Reglas en toda conversación",
    globalSubtitle: "Lo que el asistente hace siempre, sin importar el tipo de caso.",
  },
  pt: {
    title: "Supervisão",
    subtitle: "Como o assistente está atendendo e quais regras segue.",
    technical: "Ver detalhe técnico",
    tabSummary: "Resumo",
    tabConfig: "Configuração e regras",
    configured: "Como está configurado",
    policy: "Política de contestações",
    version: (v: string) => `Versão ${v}`,
    policyDetail: "Regras de valores, prazos e escalonamento",
    ai: "Inteligência artificial",
    classifier: "Classificador de casos",
    demoDate: "Data da demo",
    demoDetail: "Os dados são sintéticos e terminam nesse dia",
    typesTitle: "O que resolve sozinho e o que passa para uma pessoa",
    typesSubtitle: "Para cada tipo de caso: a ação do assistente, quando pode realizá-la por conta própria e para quem passa o caso se não puder.",
    colType: "Tipo de caso",
    colAction: "O que o assistente faz",
    colAlone: "Resolve sozinho se…",
    colElse: "Se não…",
    explainTitle: "Antes de abrir uma contestação",
    explainSubtitle:
      "Se a cobrança não é definitiva, o assistente a explica com a movimentação real do cliente em vez de abrir um caso ou passá-lo para uma pessoa.",
    rule: (id: string) => `Regra ${id}`,
    globalTitle: "Regras em toda conversa",
    globalSubtitle: "O que o assistente faz sempre, independentemente do tipo de caso.",
  },
} as const;

/** Both tabs plus the technical-detail switch, which adds rule ids and raw configuration values. */
export default function SupervisorPage() {
  const { lang } = useLang();
  const tx = TEXT[lang];
  const config = useResource<AdminConfig>("/api/admin/config");
  const [technical, setTechnical] = useState(false);
  const [tab, setTab] = useState<"summary" | "config">("summary");
  const c = config.data;

  return (
    <Stack spacing={3}>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1} sx={{ alignItems: { sm: "flex-end" }, justifyContent: "space-between" }}>
        <Box>
          <Typography variant="h5">{tx.title}</Typography>
          <Typography variant="body2" color="text.secondary">
            {tx.subtitle}
          </Typography>
        </Box>
        <FormControlLabel
          control={<Switch size="small" checked={technical} onChange={(e) => setTechnical(e.target.checked)} />}
          label={<Typography variant="body2">{tx.technical}</Typography>}
        />
      </Stack>
      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ borderBottom: 1, borderColor: "divider", mt: "8px !important" }}>
        <Tab value="summary" label={tx.tabSummary} icon={<ReceiptText size={18} />} iconPosition="start" sx={{ minHeight: 48 }} />
        <Tab value="config" label={tx.tabConfig} icon={<Settings2 size={18} />} iconPosition="start" sx={{ minHeight: 48 }} />
      </Tabs>

      {tab === "summary" && (
        <Suspense fallback={<LinearProgress />}>
          <AnalyticsTab technical={technical} />
        </Suspense>
      )}

      {tab === "config" && config.error && <Alert severity="error">{config.error}</Alert>}
      {tab === "config" && !c && !config.error && <LinearProgress />}
      {tab === "config" && c && (
        <>
          <Section icon={Settings2} title={tx.configured} subtitle={originLabel(c.policy_origin, lang)}>
            <Stack direction="row" spacing={2} sx={{ flexWrap: "wrap", rowGap: 2 }}>
              <Setting icon={FileText} label={tx.policy} name={tx.version(c.policy_version)} detail={tx.policyDetail} />
              <Setting icon={BrainCircuit} label={tx.ai} {...modelLabel(c.llm_provider, c.prompt_version, lang)} />
              <Setting icon={Tags} label={tx.classifier} {...classifierLabel(c.classifier_model, lang)} />
              <Setting icon={CalendarDays} label={tx.demoDate} name={longDate(c.demo_today, lang)} detail={tx.demoDetail} />
            </Stack>
            {technical && (
              <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1.5, fontFamily: "monospace" }}>
                policy={c.policy_version} · llm={c.llm_provider} ({c.prompt_version}) · classifier={c.classifier_model} · demo_today={c.demo_today}
              </Typography>
            )}
          </Section>

          <Section
            icon={ListChecks}
            title={tx.typesTitle}
            subtitle={tx.typesSubtitle}
          >
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>{tx.colType}</TableCell>
                    <TableCell>{tx.colAction}</TableCell>
                    <TableCell>{tx.colAlone}</TableCell>
                    <TableCell>{tx.colElse}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {c.policy.dispute_types.map((d) => (
                    <TableRow key={d.id} sx={{ verticalAlign: "top" }}>
                      <TableCell sx={{ fontWeight: 600 }}>{d.display_name[lang] ?? d.display_name.es}</TableCell>
                      <TableCell>{autoActionText(d, c, lang)}</TableCell>
                      <TableCell>{conditionText(d, lang)}</TableCell>
                      <TableCell>
                        {escalationLines(d, lang).map((line) => (
                          <Typography key={line} variant="body2">
                            {line}
                          </Typography>
                        ))}
                        {technical && (
                          <Stack direction="row" spacing={0.5} sx={{ mt: 0.75, flexWrap: "wrap", rowGap: 0.5 }}>
                            {escalationRuleIds(d).map((id) => (
                              <Chip key={id} size="small" variant="outlined" label={id} />
                            ))}
                          </Stack>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Section>

          {!!c.policy.globals.explain_status?.length && (
            <Section
              icon={FileText}
              title={tx.explainTitle}
              subtitle={tx.explainSubtitle}
            >
              <List dense disablePadding>
                {c.policy.globals.explain_status.map((r) => (
                  <ListItem key={r.rule_id} disableGutters>
                    <ListItemIcon sx={{ minWidth: 32 }}>
                      <FileText size={18} color={brand.burgundy} />
                    </ListItemIcon>
                    <ListItemText
                      primary={statusRuleText(r, lang)}
                      secondary={technical ? `${r.rule_id} · status=${r.status}${r.types?.length ? ` · ${r.types.join(", ")}` : ""}` : undefined}
                    />
                    {!technical && (
                      <Tooltip title={tx.rule(r.rule_id)}>
                        <Box component="span" sx={{ color: "text.disabled", fontSize: 12, ml: 1, whiteSpace: "nowrap" }}>
                          {r.rule_id}
                        </Box>
                      </Tooltip>
                    )}
                  </ListItem>
                ))}
              </List>
            </Section>
          )}

          <Section icon={ShieldCheck} title={tx.globalTitle} subtitle={tx.globalSubtitle}>
            <List dense disablePadding>
              {guarantees(c, lang).map((g) => (
                <ListItem key={g} disableGutters>
                  <ListItemIcon sx={{ minWidth: 32 }}>
                    <ShieldCheck size={18} color={brand.burgundy} />
                  </ListItemIcon>
                  <ListItemText primary={g} />
                </ListItem>
              ))}
              {c.policy.globals.rules.map((r) => (
                <ListItem key={r.rule_id} disableGutters>
                  <ListItemIcon sx={{ minWidth: 32 }}>
                    <CircleCheck size={18} color="#2E7D32" />
                  </ListItemIcon>
                  <ListItemText
                    primary={globalRuleText(r, c, lang)}
                    secondary={technical ? `${r.rule_id} · ${r.when} → ${r.outcome}` : undefined}
                  />
                  {!technical && (
                    <Tooltip title={tx.rule(r.rule_id)}>
                      <Box component="span" sx={{ color: "text.disabled", fontSize: 12, ml: 1, whiteSpace: "nowrap" }}>
                        {r.rule_id}
                      </Box>
                    </Tooltip>
                  )}
                </ListItem>
              ))}
            </List>
          </Section>
        </>
      )}
    </Stack>
  );
}
