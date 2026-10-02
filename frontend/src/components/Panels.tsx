// Shared layout primitives (IconBadge, Section, Stat) used by the chat, agent console and supervisor screens.
import type { ReactNode } from "react";
import { Box, Paper, Stack, Typography } from "@mui/material";
import type { LucideIcon } from "lucide-react";
import { brand } from "../app/theme";

/** An icon in a blush circle: the accent used by section headers and KPI tiles. */
export function IconBadge({ icon: Icon, size = 32, inverted = false }: { icon: LucideIcon; size?: number; inverted?: boolean }) {
  return (
    <Box
      sx={{
        display: "grid",
        placeItems: "center",
        flexShrink: 0,
        width: size,
        height: size,
        borderRadius: "50%",
        bgcolor: inverted ? "rgba(255, 255, 255, 0.16)" : brand.blush,
        color: inverted ? "#FFFFFF" : brand.burgundy,
      }}
    >
      <Icon size={Math.round(size * 0.55)} />
    </Box>
  );
}

/** A card with a burgundy accent bar on the left of its title. `compact` is the console's smaller variant. */
export function Section({
  title,
  subtitle,
  icon,
  actions,
  compact = false,
  children,
}: {
  title: string;
  subtitle?: string;
  icon?: LucideIcon;
  actions?: ReactNode;
  compact?: boolean;
  children: ReactNode;
}) {
  return (
    <Paper sx={{ p: compact ? 2 : { xs: 2, sm: 2.5 }, position: "relative", overflow: "hidden" }}>
      <Stack direction="row" spacing={1.25} sx={{ alignItems: "center", mb: subtitle ? 0.5 : 1.25 }}>
        <Box sx={{ width: 4, alignSelf: "stretch", minHeight: 20, borderRadius: 2, bgcolor: brand.burgundy }} />
        {icon && <IconBadge icon={icon} size={compact ? 26 : 30} />}
        <Typography variant={compact ? "subtitle2" : "h6"} sx={{ flex: 1, color: compact ? brand.burgundyDark : "text.primary" }}>
          {title}
        </Typography>
        {actions}
      </Stack>
      {subtitle && (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2, pl: 2.25 }}>
          {subtitle}
        </Typography>
      )}
      {children}
    </Paper>
  );
}

/** A KPI tile. `hero` uses the brand gradient for the headline number of a row. */
export function Stat({
  icon,
  label,
  value,
  hint,
  hero = false,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  hint?: string;
  hero?: boolean;
}) {
  return (
    <Paper
      sx={{
        p: 2,
        height: "100%",
        borderTop: `3px solid ${hero ? brand.logoRose : brand.burgundy}`,
        ...(hero && { background: brand.gradient, color: "#FFFFFF", border: "none" }),
      }}
    >
      <Stack direction="row" spacing={1} sx={{ alignItems: "center", mb: 1 }}>
        <IconBadge icon={icon} size={28} inverted={hero} />
        <Typography variant="caption" sx={{ fontWeight: 600, color: hero ? "rgba(255, 255, 255, 0.8)" : "text.secondary", lineHeight: 1.25 }}>
          {label}
        </Typography>
      </Stack>
      <Typography variant="h4" sx={{ fontWeight: 800, lineHeight: 1.1 }}>
        {value}
      </Typography>
      {hint && (
        <Typography variant="caption" sx={{ display: "block", mt: 0.5, color: hero ? "rgba(255, 255, 255, 0.72)" : "text.secondary" }}>
          {hint}
        </Typography>
      )}
    </Paper>
  );
}
