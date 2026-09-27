import type { ReactNode } from "react";
import { NavLink } from "react-router";
import { AppBar, Avatar, Box, Button, Container, MenuItem, Select, Stack, Toolbar, Typography } from "@mui/material";
import { Globe, LogOut } from "lucide-react";
import { brand } from "../app/theme";
import { useLang, type Lang } from "../app/i18n";
import { useAuth } from "../auth/AuthProvider";

export function BrandMark({ size = 32 }: { size?: number }) {
  return <Box component="img" src="/brand/nicebank-mark-512.png" alt="" sx={{ width: size, height: size, display: "block" }} />;
}

export default function AppShell({ children }: { children: ReactNode }) {
  const { lang, setLang, t } = useLang();
  const { user, claims, roles, logout } = useAuth();
  const nav = [
    { to: "/chat", label: t.navChat, show: roles.includes("customer") },
    { to: "/console", label: t.navConsole, show: roles.includes("agent") || roles.includes("supervisor") },
    { to: "/supervisor", label: t.navSupervisor, show: roles.includes("supervisor") },
  ].filter((n) => n.show);
  const name = claims?.preferred_username ?? "";

  return (
    <Box sx={{ minHeight: "100dvh", bgcolor: "background.default" }}>
      <AppBar position="sticky" elevation={0} sx={{ bgcolor: "#FFFFFF", color: "text.primary", borderBottom: 1, borderColor: "divider" }}>
        <Toolbar sx={{ gap: { xs: 1, sm: 2 } }}>
          <Stack direction="row" spacing={1.25} sx={{ alignItems: "center" }}>
            <BrandMark />
            <Box>
              <Typography sx={{ fontWeight: 800, lineHeight: 1, color: brand.burgundy, fontSize: 18 }}>NiceBank</Typography>
              <Typography variant="caption" color="text.secondary" sx={{ display: { xs: "none", md: "block" }, lineHeight: 1.2 }}>
                {t.brandTagline}
              </Typography>
            </Box>
          </Stack>
          <Stack direction="row" spacing={0.5} sx={{ flex: 1, ml: { sm: 2 } }}>
            {nav.length > 1 &&
              nav.map((n) => (
                <Button
                  key={n.to}
                  component={NavLink}
                  to={n.to}
                  size="small"
                  sx={{ color: "text.secondary", "&.active": { bgcolor: brand.blush, color: brand.burgundy } }}
                >
                  {n.label}
                </Button>
              ))}
          </Stack>
          <Select
            size="small"
            value={lang}
            onChange={(e) => setLang(e.target.value as Lang)}
            aria-label="Language"
            variant="standard"
            disableUnderline
            renderValue={(v) => (
              <Stack direction="row" spacing={0.75} sx={{ alignItems: "center" }}>
                <Globe size={16} />
                <span>{v.toUpperCase()}</span>
              </Stack>
            )}
            sx={{ fontWeight: 700, color: brand.burgundy, "& .MuiSelect-icon": { color: brand.burgundy } }}
          >
            <MenuItem value="es">Español</MenuItem>
            <MenuItem value="pt">Português</MenuItem>
          </Select>
          {user && (
            <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
              <Avatar sx={{ width: 32, height: 32, bgcolor: brand.burgundy, fontSize: 14, fontWeight: 700 }}>
                {name.slice(0, 1).toUpperCase()}
              </Avatar>
              <Typography variant="body2" sx={{ display: { xs: "none", sm: "block" }, fontWeight: 600 }}>
                {name}
              </Typography>
              <Button size="small" color="primary" startIcon={<LogOut size={16} />} onClick={() => void logout()} aria-label={t.logout}>
                <Box component="span" sx={{ display: { xs: "none", sm: "inline" } }}>
                  {t.logout}
                </Box>
              </Button>
            </Stack>
          )}
        </Toolbar>
      </AppBar>
      <Container maxWidth="lg" sx={{ py: { xs: 2, sm: 3 } }}>
        {children}
      </Container>
    </Box>
  );
}
