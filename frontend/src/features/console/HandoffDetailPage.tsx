// Agent case detail (/console/:id): GET /api/handoffs/{id} and GET /api/sessions/{id}/audit, plus the agent actions
// POST /api/handoffs/{id}/claim, POST /api/handoffs/{id}/identity (audited reveal) and POST /api/handoffs/{id}/close.
import { useState, type ReactNode } from "react";
import { Link as RouterLink, useParams } from "react-router";
import {
  Alert,
  Box,
  Button,
  Chip,
  Divider,
  FormControlLabel,
  LinearProgress,
  Link,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Stack,
  Switch,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { ArrowLeft, CircleCheck, CircleHelp, ExternalLink, Eye, EyeOff, Scale, ShieldCheck, UserRound } from "lucide-react";
import { api, JAEGER_URL } from "../../api/client";
import type { AuditEvent, CustomerIdentity, Handoff } from "../../api/types";
import { useResource } from "../../api/useResource";
import { formatDateTime, useLang } from "../../app/i18n";
import { useAuth } from "../../auth/AuthProvider";
import { describeAudit, resultLabel, RULE_NAMES } from "./auditText";
import { factText, openQuestions } from "./handoffText";
import { ACTION_NAMES, ACTION_STATUS, DISPUTE_TYPES, LANGS, queueLabel, REASONS, SOURCES, STEPS } from "./labels";
import { PriorityBadge } from "./priority";
import { Section as PanelSection } from "../../components/Panels";

const TEXT = {
  es: {
    closeError: "No se pudo cerrar el caso. Solo quien lo tomó puede cerrarlo, y la nota es obligatoria.",
    revealError: "No se pudo mostrar la identidad. Solo quien tomó el caso puede verla.",
    loadError: "No se pudo cargar el caso:",
    back: "Volver a la cola",
    queue: (q: string) => `Cola: ${q}`,
    statusOpen: "Abierto",
    closedBy: (who: string) => `Cerrado por ${who}`,
    claimedBy: (who: string) => `Tomado por ${who}`,
    claim: "Tomar caso",
    customer: "Cliente",
    reference: (ref: string) => `Referencia ${ref} · esta consulta quedó registrada en la auditoría`,
    hide: "Ocultar",
    protectedMine: "La identidad está protegida. Muéstrala solo si necesitas contactar al cliente; queda registrado.",
    protectedOther: "La identidad está protegida. Se puede ver después de tomar el caso.",
    reveal: "Mostrar identidad",
    request: "Lo que pidió el cliente (enmascarado)",
    noDescription: "(sin descripción)",
    facts: "Hechos verificados",
    source: (s: string) => `Fuente: ${s}`,
    noFacts: "Sin hechos verificados.",
    actions: "Acciones tomadas",
    noActions: "Ninguna acción automática.",
    questions: "Preguntas abiertas",
    evidence: "Evidencia y agentes sugeridos",
    rule: (id: string) => `Regla ${id}`,
    general: "general",
    closeTitle: "Cerrar el caso",
    noteLabel: "Nota para el cliente (la verá en «Mis disputas»)",
    noteHelp: "Explica la decisión sin datos personales. Queda registrado quién cerró el caso y con qué resultado.",
    accept: "Resolver a favor del cliente",
    reject: "No procede",
    resolution: "Resolución",
    accepted: "Resuelto a favor del cliente",
    rejected: "No procede",
    audit: "Auditoría de la conversación",
    technical: "Ver detalle técnico",
    jaeger: "Ver traza en Jaeger",
  },
  pt: {
    closeError: "Não foi possível encerrar o caso. Só quem o assumiu pode encerrá-lo, e a nota é obrigatória.",
    revealError: "Não foi possível mostrar a identidade. Só quem assumiu o caso pode vê-la.",
    loadError: "Não foi possível carregar o caso:",
    back: "Voltar para a fila",
    queue: (q: string) => `Fila: ${q}`,
    statusOpen: "Aberto",
    closedBy: (who: string) => `Encerrado por ${who}`,
    claimedBy: (who: string) => `Assumido por ${who}`,
    claim: "Assumir caso",
    customer: "Cliente",
    reference: (ref: string) => `Referência ${ref} · esta consulta ficou registrada na auditoria`,
    hide: "Ocultar",
    protectedMine: "A identidade está protegida. Mostre-a só se precisar entrar em contato com o cliente; fica registrado.",
    protectedOther: "A identidade está protegida. Pode ser vista depois de assumir o caso.",
    reveal: "Mostrar identidade",
    request: "O que o cliente pediu (mascarado)",
    noDescription: "(sem descrição)",
    facts: "Fatos verificados",
    source: (s: string) => `Fonte: ${s}`,
    noFacts: "Sem fatos verificados.",
    actions: "Ações realizadas",
    noActions: "Nenhuma ação automática.",
    questions: "Perguntas em aberto",
    evidence: "Evidências e agentes sugeridos",
    rule: (id: string) => `Regra ${id}`,
    general: "geral",
    closeTitle: "Encerrar o caso",
    noteLabel: "Nota para o cliente (ele a verá em «Minhas contestações»)",
    noteHelp: "Explique a decisão sem dados pessoais. Fica registrado quem encerrou o caso e com qual resultado.",
    accept: "Resolver a favor do cliente",
    reject: "Não procede",
    resolution: "Resolução",
    accepted: "Resolvido a favor do cliente",
    rejected: "Não procede",
    audit: "Auditoria da conversa",
    technical: "Ver detalhe técnico",
    jaeger: "Ver trace no Jaeger",
  },
} as const;

// The backend's placeholder when the first message was empty (handoff.go); never the customer's own words.
const NO_DESCRIPTION = "(sin descripción)";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <PanelSection compact title={title}>
      {children}
    </PanelSection>
  );
}

/** Structured handoff, identity reveal and closing form for the claiming agent, and the readable audit trail. */
export default function HandoffDetailPage() {
  const { lang } = useLang();
  const tx = TEXT[lang];
  const { id } = useParams();
  const { user, roles } = useAuth();
  const handoff = useResource<Handoff>(id ? `/api/handoffs/${id}` : null);
  const h = handoff.data;
  const audit = useResource<AuditEvent[]>(h ? `/api/sessions/${h.session_id}/audit` : null);
  const [claiming, setClaiming] = useState(false);
  const [technical, setTechnical] = useState(false);
  const [identity, setIdentity] = useState<CustomerIdentity | null>(null);
  const [revealError, setRevealError] = useState(false);
  const [note, setNote] = useState("");
  const [closing, setClosing] = useState(false);
  const [closeError, setCloseError] = useState(false);
  const mine = h?.status === "claimed" && h.claimed_by === user?.profile.preferred_username;

  const close = async (outcome: "accepted" | "rejected") => {
    if (!user || !id) return;
    setClosing(true);
    setCloseError(false);
    try {
      await api<Handoff>(`/api/handoffs/${id}/close`, user.access_token, { method: "POST", body: { outcome, note: note.trim() } });
      await Promise.all([handoff.reload(), audit.reload()]);
    } catch {
      setCloseError(true);
    } finally {
      setClosing(false);
    }
  };

  const reveal = async () => {
    if (!user || !id) return;
    setRevealError(false);
    try {
      setIdentity(await api<CustomerIdentity>(`/api/handoffs/${id}/identity`, user.access_token, { method: "POST" }));
      await audit.reload();
    } catch {
      setRevealError(true);
    }
  };

  const claim = async () => {
    if (!user || !id) return;
    setClaiming(true);
    try {
      await api<Handoff>(`/api/handoffs/${id}/claim`, user.access_token, { method: "POST" });
      await handoff.reload();
    } finally {
      setClaiming(false);
    }
  };

  if (handoff.error) return <Alert severity="error">{tx.loadError} {handoff.error}</Alert>;
  if (!h) return <LinearProgress />;

  return (
    <Stack spacing={2}>
      <Button component={RouterLink} to="/console" startIcon={<ArrowLeft size={16} />} sx={{ alignSelf: "flex-start" }}>
        {tx.back}
      </Button>

      <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ alignItems: { sm: "center" } }}>
        <Box sx={{ flex: 1 }}>
          <Typography variant="h5">{REASONS[lang][h.reason] ?? h.reason}</Typography>
          <Stack direction="row" spacing={1} sx={{ mt: 1, flexWrap: "wrap", rowGap: 1 }}>
            <PriorityBadge priority={h.priority} />
            <Chip size="small" label={DISPUTE_TYPES[lang][h.dispute_type] ?? h.dispute_type} />
            <Chip size="small" label={LANGS[lang][h.language] ?? h.language} />
            <Chip size="small" variant="outlined" label={tx.queue(queueLabel(h.suggested_queue, lang))} />
            <Chip
              size="small"
              variant="outlined"
              label={h.status === "open" ? tx.statusOpen : h.status === "closed" ? tx.closedBy(h.resolution?.closed_by ?? h.claimed_by ?? "") : tx.claimedBy(h.claimed_by ?? "")}
            />
          </Stack>
        </Box>
        {h.status === "open" && roles.includes("agent") && (
          <Button variant="contained" onClick={claim} disabled={claiming}>
            {tx.claim}
          </Button>
        )}
      </Stack>

      <Section title={tx.customer}>
        {identity ? (
          <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
            <UserRound size={20} />
            <Box sx={{ flex: 1 }}>
              <Typography variant="body1" sx={{ fontWeight: 600 }}>
                {identity.first_name} {identity.last_name}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {tx.reference(identity.customer_ref)}
              </Typography>
            </Box>
            <Button size="small" startIcon={<EyeOff size={16} />} onClick={() => setIdentity(null)}>
              {tx.hide}
            </Button>
          </Stack>
        ) : (
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} sx={{ alignItems: { sm: "center" } }}>
            <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
              {mine ? tx.protectedMine : tx.protectedOther}
            </Typography>
            {mine && (
              <Button variant="outlined" size="small" startIcon={<Eye size={16} />} onClick={reveal}>
                {tx.reveal}
              </Button>
            )}
          </Stack>
        )}
        {revealError && (
          <Alert severity="warning" sx={{ mt: 1 }}>
            {tx.revealError}
          </Alert>
        )}
      </Section>

      <Section title={tx.request}>
        <Typography variant="body1">“{h.customer_request === NO_DESCRIPTION ? tx.noDescription : h.customer_request}”</Typography>
      </Section>

      <Stack direction={{ xs: "column", md: "row" }} spacing={2} sx={{ alignItems: "stretch" }}>
        <Box sx={{ flex: 1 }}>
          <Section title={tx.facts}>
            <List dense disablePadding>
              {h.verified_facts.map((f) => (
                <ListItem key={f.fact} disableGutters>
                  <ListItemIcon sx={{ minWidth: 32 }}>
                    <ShieldCheck size={18} color="#2E7D32" />
                  </ListItemIcon>
                  <ListItemText primary={factText(f.fact, lang)} secondary={tx.source(SOURCES[lang][f.source] ?? f.source)} />
                </ListItem>
              ))}
              {h.verified_facts.length === 0 && <Typography variant="body2">{tx.noFacts}</Typography>}
            </List>
          </Section>
        </Box>
        <Box sx={{ flex: 1 }}>
          <Section title={tx.actions}>
            <List dense disablePadding>
              {h.actions_taken.map((a) => (
                <ListItem key={a.reference} disableGutters>
                  <ListItemIcon sx={{ minWidth: 32 }}>
                    <CircleCheck size={18} color="#2E7D32" />
                  </ListItemIcon>
                  <ListItemText
                    primary={`${ACTION_NAMES[lang][a.action] ?? a.action} · ${a.reference}`}
                    secondary={`${ACTION_STATUS[lang][a.status] ?? a.status} · ${formatDateTime(a.at, lang)}`}
                  />
                </ListItem>
              ))}
              {h.actions_taken.length === 0 && <Typography variant="body2">{tx.noActions}</Typography>}
            </List>
          </Section>
        </Box>
      </Stack>

      <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
        <Box sx={{ flex: 1 }}>
          <Section title={tx.questions}>
            <List dense disablePadding>
              {openQuestions(h, lang).map((q) => (
                <ListItem key={q} disableGutters>
                  <ListItemIcon sx={{ minWidth: 32 }}>
                    <CircleHelp size={18} color="#D98A00" />
                  </ListItemIcon>
                  <ListItemText primary={q} />
                </ListItem>
              ))}
            </List>
          </Section>
        </Box>
        <Box sx={{ flex: 1 }}>
          <Section title={tx.evidence}>
            <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", rowGap: 1, mb: 1.5 }}>
              {h.evidence?.map((e) => (
                <Tooltip key={e.id} title={tx.rule(e.id)}>
                  <Chip size="small" icon={<Scale size={14} />} label={RULE_NAMES[lang][e.id] ?? e.id} variant="outlined" />
                </Tooltip>
              ))}
            </Stack>
            {h.suggested_agents?.map((a) => (
              <Typography key={a.agent_id} variant="body2">
                {a.name} · {a.specialty || tx.general} · {a.languages}
              </Typography>
            ))}
          </Section>
        </Box>
      </Stack>

      {mine && (
        <Section title={tx.closeTitle}>
          <Stack spacing={1.5}>
            <TextField
              label={tx.noteLabel}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              multiline
              minRows={2}
              slotProps={{ htmlInput: { maxLength: 1000 } }}
              helperText={tx.noteHelp}
            />
            <Stack direction="row" spacing={1}>
              <Button variant="contained" disabled={closing || !note.trim()} onClick={() => close("accepted")}>
                {tx.accept}
              </Button>
              <Button variant="outlined" color="error" disabled={closing || !note.trim()} onClick={() => close("rejected")}>
                {tx.reject}
              </Button>
            </Stack>
            {closeError && <Alert severity="warning">{tx.closeError}</Alert>}
          </Stack>
        </Section>
      )}
      {h.resolution && (
        <Section title={tx.resolution}>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            {h.resolution.outcome === "accepted" ? tx.accepted : tx.rejected} · {h.resolution.closed_by} ·{" "}
            {formatDateTime(h.resolution.closed_at, lang)}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            {h.resolution.note}
          </Typography>
        </Section>
      )}

      <Section title={tx.audit}>
        <Stack direction="row" spacing={2} sx={{ justifyContent: "flex-end", alignItems: "center", mb: 1, flexWrap: "wrap" }}>
          <FormControlLabel
            control={<Switch size="small" checked={technical} onChange={(ev) => setTechnical(ev.target.checked)} />}
            label={<Typography variant="body2">{tx.technical}</Typography>}
          />
          {technical && (
            <Link href={`${JAEGER_URL}/trace/${encodeURIComponent(h.trace_id)}`} target="_blank" rel="noreferrer" variant="body2">
              {tx.jaeger} <ExternalLink size={14} style={{ verticalAlign: "middle" }} />
            </Link>
          )}
        </Stack>
        {audit.loading && !audit.data && <LinearProgress />}
        <Stack divider={<Divider flexItem />}>
          {audit.data?.map((e, i) => {
            const result = resultLabel(e.result, lang);
            return (
              <Stack key={i} direction={{ xs: "column", sm: "row" }} spacing={{ xs: 0.5, sm: 2 }} sx={{ py: 1 }}>
                <Typography variant="caption" color="text.secondary" sx={{ width: 150, flexShrink: 0 }}>
                  {formatDateTime(e.ts, lang)}
                </Typography>
                <Box sx={{ width: 170, flexShrink: 0 }}>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {STEPS[lang][e.step] ?? e.step}
                  </Typography>
                  {technical && e.tool && (
                    <Typography variant="caption" color="text.secondary">
                      {e.tool}
                    </Typography>
                  )}
                </Box>
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography variant="body2" sx={{ wordBreak: "break-word" }}>
                    {describeAudit(e, lang)}
                  </Typography>
                  {technical && (
                    <Typography variant="caption" color="text.secondary" sx={{ display: "block", fontFamily: "monospace", wordBreak: "break-all" }}>
                      {e.summary}
                    </Typography>
                  )}
                </Box>
                <Stack direction="row" spacing={1} sx={{ flexShrink: 0, flexWrap: "wrap", rowGap: 0.5 }}>
                  {result && <Chip size="small" label={result} />}
                  {e.rule_id && (
                    <Tooltip title={tx.rule(e.rule_id)}>
                      <Chip size="small" variant="outlined" icon={<Scale size={14} />}
                        label={technical ? e.rule_id : RULE_NAMES[lang][e.rule_id] ?? e.rule_id} />
                    </Tooltip>
                  )}
                </Stack>
              </Stack>
            );
          })}
        </Stack>
      </Section>
    </Stack>
  );
}
