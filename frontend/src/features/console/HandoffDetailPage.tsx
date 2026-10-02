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
import { formatDateTime } from "../../app/i18n";
import { useAuth } from "../../auth/AuthProvider";
import { describeAudit, resultLabel, RULE_NAMES } from "./auditText";
import { ACTION_NAMES, ACTION_STATUS, DISPUTE_TYPES, LANGS, queueLabel, REASONS, SOURCES, STEPS } from "./labels";
import { PriorityBadge } from "./priority";
import { Section as PanelSection } from "../../components/Panels";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <PanelSection compact title={title}>
      {children}
    </PanelSection>
  );
}

export default function HandoffDetailPage() {
  const { id } = useParams();
  const { user, roles } = useAuth();
  const handoff = useResource<Handoff>(id ? `/api/handoffs/${id}` : null);
  const h = handoff.data;
  const audit = useResource<AuditEvent[]>(h ? `/api/sessions/${h.session_id}/audit` : null);
  const [claiming, setClaiming] = useState(false);
  const [technical, setTechnical] = useState(false);
  const [identity, setIdentity] = useState<CustomerIdentity | null>(null);
  const [revealError, setRevealError] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [closing, setClosing] = useState(false);
  const [closeError, setCloseError] = useState<string | null>(null);
  const mine = h?.status === "claimed" && h.claimed_by === user?.profile.preferred_username;

  const close = async (outcome: "accepted" | "rejected") => {
    if (!user || !id) return;
    setClosing(true);
    setCloseError(null);
    try {
      await api<Handoff>(`/api/handoffs/${id}/close`, user.access_token, { method: "POST", body: { outcome, note: note.trim() } });
      await Promise.all([handoff.reload(), audit.reload()]);
    } catch {
      setCloseError("No se pudo cerrar el caso. Solo quien lo tomó puede cerrarlo, y la nota es obligatoria.");
    } finally {
      setClosing(false);
    }
  };

  const reveal = async () => {
    if (!user || !id) return;
    setRevealError(null);
    try {
      setIdentity(await api<CustomerIdentity>(`/api/handoffs/${id}/identity`, user.access_token, { method: "POST" }));
      await audit.reload();
    } catch {
      setRevealError("No se pudo mostrar la identidad. Solo quien tomó el caso puede verla.");
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

  if (handoff.error) return <Alert severity="error">No se pudo cargar el caso: {handoff.error}</Alert>;
  if (!h) return <LinearProgress />;

  return (
    <Stack spacing={2}>
      <Button component={RouterLink} to="/console" startIcon={<ArrowLeft size={16} />} sx={{ alignSelf: "flex-start" }}>
        Volver a la cola
      </Button>

      <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ alignItems: { sm: "center" } }}>
        <Box sx={{ flex: 1 }}>
          <Typography variant="h5">{REASONS[h.reason] ?? h.reason}</Typography>
          <Stack direction="row" spacing={1} sx={{ mt: 1, flexWrap: "wrap", rowGap: 1 }}>
            <PriorityBadge priority={h.priority} />
            <Chip size="small" label={DISPUTE_TYPES[h.dispute_type] ?? h.dispute_type} />
            <Chip size="small" label={LANGS[h.language]} />
            <Chip size="small" variant="outlined" label={`Cola: ${queueLabel(h.suggested_queue)}`} />
            <Chip
              size="small"
              variant="outlined"
              label={h.status === "open" ? "Abierto" : h.status === "closed" ? `Cerrado por ${h.resolution?.closed_by ?? h.claimed_by}` : `Tomado por ${h.claimed_by}`}
            />
          </Stack>
        </Box>
        {h.status === "open" && roles.includes("agent") && (
          <Button variant="contained" onClick={claim} disabled={claiming}>
            Tomar caso
          </Button>
        )}
      </Stack>

      <Section title="Cliente">
        {identity ? (
          <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
            <UserRound size={20} />
            <Box sx={{ flex: 1 }}>
              <Typography variant="body1" sx={{ fontWeight: 600 }}>
                {identity.first_name} {identity.last_name}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Referencia {identity.customer_ref} · esta consulta quedó registrada en la auditoría
              </Typography>
            </Box>
            <Button size="small" startIcon={<EyeOff size={16} />} onClick={() => setIdentity(null)}>
              Ocultar
            </Button>
          </Stack>
        ) : (
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} sx={{ alignItems: { sm: "center" } }}>
            <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
              {mine
                ? "La identidad está protegida. Muéstrala solo si necesitas contactar al cliente; queda registrado."
                : "La identidad está protegida. Se puede ver después de tomar el caso."}
            </Typography>
            {mine && (
              <Button variant="outlined" size="small" startIcon={<Eye size={16} />} onClick={reveal}>
                Mostrar identidad
              </Button>
            )}
          </Stack>
        )}
        {revealError && (
          <Alert severity="warning" sx={{ mt: 1 }}>
            {revealError}
          </Alert>
        )}
      </Section>

      <Section title="Lo que pidió el cliente (enmascarado)">
        <Typography variant="body1">“{h.customer_request}”</Typography>
      </Section>

      <Stack direction={{ xs: "column", md: "row" }} spacing={2} sx={{ alignItems: "stretch" }}>
        <Box sx={{ flex: 1 }}>
          <Section title="Hechos verificados">
            <List dense disablePadding>
              {h.verified_facts.map((f) => (
                <ListItem key={f.fact} disableGutters>
                  <ListItemIcon sx={{ minWidth: 32 }}>
                    <ShieldCheck size={18} color="#2E7D32" />
                  </ListItemIcon>
                  <ListItemText primary={f.fact} secondary={`Fuente: ${SOURCES[f.source] ?? f.source}`} />
                </ListItem>
              ))}
              {h.verified_facts.length === 0 && <Typography variant="body2">Sin hechos verificados.</Typography>}
            </List>
          </Section>
        </Box>
        <Box sx={{ flex: 1 }}>
          <Section title="Acciones tomadas">
            <List dense disablePadding>
              {h.actions_taken.map((a) => (
                <ListItem key={a.reference} disableGutters>
                  <ListItemIcon sx={{ minWidth: 32 }}>
                    <CircleCheck size={18} color="#2E7D32" />
                  </ListItemIcon>
                  <ListItemText primary={`${ACTION_NAMES[a.action] ?? a.action} · ${a.reference}`} secondary={`${ACTION_STATUS[a.status] ?? a.status} · ${formatDateTime(a.at, "es")}`} />
                </ListItem>
              ))}
              {h.actions_taken.length === 0 && <Typography variant="body2">Ninguna acción automática.</Typography>}
            </List>
          </Section>
        </Box>
      </Stack>

      <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
        <Box sx={{ flex: 1 }}>
          <Section title="Preguntas abiertas">
            <List dense disablePadding>
              {h.open_questions?.map((q) => (
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
          <Section title="Evidencia y agentes sugeridos">
            <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", rowGap: 1, mb: 1.5 }}>
              {h.evidence?.map((e) => (
                <Tooltip key={e.id} title={`Regla ${e.id}`}>
                  <Chip size="small" icon={<Scale size={14} />} label={RULE_NAMES[e.id] ?? e.id} variant="outlined" />
                </Tooltip>
              ))}
            </Stack>
            {h.suggested_agents?.map((a) => (
              <Typography key={a.agent_id} variant="body2">
                {a.name} · {a.specialty || "general"} · {a.languages}
              </Typography>
            ))}
          </Section>
        </Box>
      </Stack>

      {mine && (
        <Section title="Cerrar el caso">
          <Stack spacing={1.5}>
            <TextField
              label="Nota para el cliente (la verá en «Mis disputas»)"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              multiline
              minRows={2}
              slotProps={{ htmlInput: { maxLength: 1000 } }}
              helperText="Explica la decisión sin datos personales. Queda registrado quién cerró el caso y con qué resultado."
            />
            <Stack direction="row" spacing={1}>
              <Button variant="contained" disabled={closing || !note.trim()} onClick={() => close("accepted")}>
                Resolver a favor del cliente
              </Button>
              <Button variant="outlined" color="error" disabled={closing || !note.trim()} onClick={() => close("rejected")}>
                No procede
              </Button>
            </Stack>
            {closeError && <Alert severity="warning">{closeError}</Alert>}
          </Stack>
        </Section>
      )}
      {h.resolution && (
        <Section title="Resolución">
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            {h.resolution.outcome === "accepted" ? "Resuelto a favor del cliente" : "No procede"} · {h.resolution.closed_by} ·{" "}
            {formatDateTime(h.resolution.closed_at, "es")}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            {h.resolution.note}
          </Typography>
        </Section>
      )}

      <Section title="Auditoría de la conversación">
        <Stack direction="row" spacing={2} sx={{ justifyContent: "flex-end", alignItems: "center", mb: 1, flexWrap: "wrap" }}>
          <FormControlLabel
            control={<Switch size="small" checked={technical} onChange={(ev) => setTechnical(ev.target.checked)} />}
            label={<Typography variant="body2">Ver detalle técnico</Typography>}
          />
          {technical && (
            <Link href={`${JAEGER_URL}/trace/${encodeURIComponent(h.trace_id)}`} target="_blank" rel="noreferrer" variant="body2">
              Ver traza en Jaeger <ExternalLink size={14} style={{ verticalAlign: "middle" }} />
            </Link>
          )}
        </Stack>
        {audit.loading && !audit.data && <LinearProgress />}
        <Stack divider={<Divider flexItem />}>
          {audit.data?.map((e, i) => {
            const result = resultLabel(e.result);
            return (
              <Stack key={i} direction={{ xs: "column", sm: "row" }} spacing={{ xs: 0.5, sm: 2 }} sx={{ py: 1 }}>
                <Typography variant="caption" color="text.secondary" sx={{ width: 150, flexShrink: 0 }}>
                  {formatDateTime(e.ts, "es")}
                </Typography>
                <Box sx={{ width: 170, flexShrink: 0 }}>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {STEPS[e.step] ?? e.step}
                  </Typography>
                  {technical && e.tool && (
                    <Typography variant="caption" color="text.secondary">
                      {e.tool}
                    </Typography>
                  )}
                </Box>
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography variant="body2" sx={{ wordBreak: "break-word" }}>
                    {describeAudit(e)}
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
                    <Tooltip title={`Regla ${e.rule_id}`}>
                      <Chip size="small" variant="outlined" icon={<Scale size={14} />}
                        label={technical ? e.rule_id : RULE_NAMES[e.rule_id] ?? e.rule_id} />
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
