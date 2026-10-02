// Handoff priority display for the agent console: badge, row accent color and wait time against demo targets.
import { Box, Stack, Tooltip, Typography } from "@mui/material";
import { ArrowDown, Flame, Timer } from "lucide-react";
import { brand } from "../../app/theme";

type Priority = "high" | "medium" | "low";

// Brand palette only: solid burgundy for high, rose tint for medium, neutral for low.
const STYLE: Record<Priority, { label: string; hint: string; bg: string; fg: string; border: string; bar: string; Icon: typeof Flame }> = {
  high: {
    label: "Alta",
    hint: "Posible fraude o tarjeta robada: atender primero",
    bg: brand.burgundy,
    fg: "#FFFFFF",
    border: brand.burgundy,
    bar: brand.burgundy,
    Icon: Flame,
  },
  medium: {
    label: "Media",
    hint: "Revisión de un especialista sin riesgo inmediato",
    bg: brand.blush,
    fg: brand.burgundy,
    border: "#E5769A",
    bar: "#E5769A",
    Icon: Timer,
  },
  low: {
    label: "Baja",
    hint: "Puede esperar",
    bg: "#F4F1F2",
    fg: "#5E4B52",
    border: "#D9CFD3",
    bar: "#D9CFD3",
    Icon: ArrowDown,
  },
};

/** Left-border color of a queue row for this priority. */
export const priorityBar = (p: Priority) => STYLE[p]?.bar ?? STYLE.low.bar;

/** Pill with icon and Spanish label; the tooltip says what the level means for the agent. */
export function PriorityBadge({ priority }: { priority: Priority }) {
  const s = STYLE[priority] ?? STYLE.low;
  return (
    <Tooltip title={s.hint}>
      <Box
        component="span"
        sx={{
          display: "inline-flex",
          alignItems: "center",
          gap: 0.6,
          px: 1.1,
          py: 0.35,
          borderRadius: 99,
          fontSize: 13,
          fontWeight: 700,
          lineHeight: 1.4,
          bgcolor: s.bg,
          color: s.fg,
          border: `1px solid ${s.border}`,
          whiteSpace: "nowrap",
        }}
      >
        <s.Icon size={14} />
        {s.label}
      </Box>
    </Tooltip>
  );
}

/** "3 min", "2 h 05 min", "1 d 4 h" */
export function elapsed(fromIso: string, now = Date.now()): string {
  const mins = Math.max(0, Math.floor((now - new Date(fromIso).getTime()) / 60_000));
  if (mins < 60) return `${mins} min`;
  const h = Math.floor(mins / 60);
  if (h < 24) return `${h} h ${String(mins % 60).padStart(2, "0")} min`;
  return `${Math.floor(h / 24)} d ${h % 24} h`;
}

// A case waiting longer than this is flagged in the queue (demo targets, not a real SLA).
const WAIT_TARGET_MIN: Record<Priority, number> = { high: 30, medium: 240, low: 1440 };

/** Time since `since`, highlighted past the priority's wait target; the tooltip shows the exact date. */
export function WaitTime({ since, priority, exact }: { since: string; priority: Priority; exact: string }) {
  const mins = (Date.now() - new Date(since).getTime()) / 60_000;
  const late = mins > (WAIT_TARGET_MIN[priority] ?? WAIT_TARGET_MIN.low);
  return (
    <Tooltip title={exact}>
      <Stack spacing={0}>
        <Typography variant="body2" sx={{ fontWeight: late ? 700 : 500, color: late ? brand.burgundy : "text.primary" }}>
          {elapsed(since)}
        </Typography>
        {late && (
          <Typography variant="caption" sx={{ color: brand.burgundy }}>
            Supera el tiempo objetivo
          </Typography>
        )}
      </Stack>
    </Tooltip>
  );
}
