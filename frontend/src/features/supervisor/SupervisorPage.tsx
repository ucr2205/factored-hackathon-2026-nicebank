// Supervisor view (/supervisor): the "Resumen" tab (AnalyticsTab, lazy) and "Configuración y reglas", a
// plain-Spanish reading of GET /api/admin/config (policy version, LLM, classifier and rules).
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

// The charts library loads only when the "Resumen" tab is shown.
const AnalyticsTab = lazy(() => import("./AnalyticsTab"));

const longDate = (iso: string) =>
  new Intl.DateTimeFormat("es", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(iso));

/** Both tabs plus the "Ver detalle técnico" switch, which adds rule ids and raw configuration values. */
export default function SupervisorPage() {
  const config = useResource<AdminConfig>("/api/admin/config");
  const [technical, setTechnical] = useState(false);
  const [tab, setTab] = useState<"summary" | "config">("summary");
  const c = config.data;

  return (
    <Stack spacing={3}>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1} sx={{ alignItems: { sm: "flex-end" }, justifyContent: "space-between" }}>
        <Box>
          <Typography variant="h5">Supervisión</Typography>
          <Typography variant="body2" color="text.secondary">
            Cómo está atendiendo el asistente y qué reglas sigue.
          </Typography>
        </Box>
        <FormControlLabel
          control={<Switch size="small" checked={technical} onChange={(e) => setTechnical(e.target.checked)} />}
          label={<Typography variant="body2">Ver detalle técnico</Typography>}
        />
      </Stack>
      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ borderBottom: 1, borderColor: "divider", mt: "8px !important" }}>
        <Tab value="summary" label="Resumen" icon={<ReceiptText size={18} />} iconPosition="start" sx={{ minHeight: 48 }} />
        <Tab value="config" label="Configuración y reglas" icon={<Settings2 size={18} />} iconPosition="start" sx={{ minHeight: 48 }} />
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
          <Section icon={Settings2} title="Cómo está configurado" subtitle={originLabel(c.policy_origin)}>
            <Stack direction="row" spacing={2} sx={{ flexWrap: "wrap", rowGap: 2 }}>
              <Setting icon={FileText} label="Política de disputas" name={`Versión ${c.policy_version}`} detail="Reglas de montos, plazos y escalamiento" />
              <Setting icon={BrainCircuit} label="Inteligencia artificial" {...modelLabel(c.llm_provider, c.prompt_version)} />
              <Setting icon={Tags} label="Clasificador de casos" {...classifierLabel(c.classifier_model)} />
              <Setting icon={CalendarDays} label="Fecha del demo" name={longDate(c.demo_today)} detail="Los datos son sintéticos y terminan ese día" />
            </Stack>
            {technical && (
              <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1.5, fontFamily: "monospace" }}>
                policy={c.policy_version} · llm={c.llm_provider} ({c.prompt_version}) · classifier={c.classifier_model} · demo_today={c.demo_today}
              </Typography>
            )}
          </Section>

          <Section
            icon={ListChecks}
            title="Qué resuelve solo y qué pasa a una persona"
            subtitle="Para cada tipo de caso: la acción del asistente, cuándo puede hacerla por su cuenta y a quién pasa el caso si no."
          >
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Tipo de caso</TableCell>
                    <TableCell>Qué hace el asistente</TableCell>
                    <TableCell>Lo resuelve solo si…</TableCell>
                    <TableCell>Si no…</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {c.policy.dispute_types.map((d) => (
                    <TableRow key={d.id} sx={{ verticalAlign: "top" }}>
                      <TableCell sx={{ fontWeight: 600 }}>{d.display_name.es}</TableCell>
                      <TableCell>{autoActionText(d, c)}</TableCell>
                      <TableCell>{conditionText(d)}</TableCell>
                      <TableCell>
                        {escalationLines(d).map((line) => (
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
              title="Antes de abrir una disputa"
              subtitle="Si el cobro no es definitivo, el asistente lo explica con el movimiento real del cliente en vez de abrir un caso o pasarlo a una persona."
            >
              <List dense disablePadding>
                {c.policy.globals.explain_status.map((r) => (
                  <ListItem key={r.rule_id} disableGutters>
                    <ListItemIcon sx={{ minWidth: 32 }}>
                      <FileText size={18} color={brand.burgundy} />
                    </ListItemIcon>
                    <ListItemText
                      primary={statusRuleText(r)}
                      secondary={technical ? `${r.rule_id} · status=${r.status}${r.types?.length ? ` · ${r.types.join(", ")}` : ""}` : undefined}
                    />
                    {!technical && (
                      <Tooltip title={`Regla ${r.rule_id}`}>
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

          <Section icon={ShieldCheck} title="Reglas en toda conversación" subtitle="Lo que el asistente hace siempre, sin importar el tipo de caso.">
            <List dense disablePadding>
              {guarantees(c).map((g) => (
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
                    primary={globalRuleText(r, c)}
                    secondary={technical ? `${r.rule_id} · ${r.when} → ${r.outcome}` : undefined}
                  />
                  {!technical && (
                    <Tooltip title={`Regla ${r.rule_id}`}>
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
