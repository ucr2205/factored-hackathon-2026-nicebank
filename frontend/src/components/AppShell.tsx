import { useState, type ReactNode } from "react";
import { NavLink } from "react-router";
import {
  AppBar,
  Avatar,
  Box,
  ButtonBase,
  Container,
  Divider,
  ListItemIcon,
  Menu,
  MenuItem,
  Select,
  Stack,
  Toolbar,
  Typography,
} from "@mui/material";
import { ChevronDown, Globe, Headset, LayoutDashboard, LogOut, MessageSquare, type LucideIcon } from "lucide-react";
import { brand } from "../app/theme";
import { useLang, type Lang } from "../app/i18n";
import { useAuth } from "../auth/AuthProvider";

const LOGO_ROSE = "#E5769A"; // the "Bank" color of the logo

export function BrandMark({ size = 32 }: { size?: number }) {
  return <Box component="img" src="/brand/nicebank-mark-512.png" alt="" sx={{ width: size, height: size, display: "block" }} />;
}

function NavTab({ to, label, icon: Icon }: { to: string; label: string; icon: LucideIcon }) {
  return (
    <ButtonBase
      component={NavLink}
      to={to}
      aria-label={label}
      sx={{
        height: 64,
        px: { xs: 1.25, sm: 1.75 },
        gap: 1,
        color: "text.secondary",
        fontWeight: 600,
        fontSize: 14,
        borderBottom: "3px solid transparent",
        borderTop: "3px solid transparent",
        transition: "color .15s, border-color .15s",
        "&:hover": { color: brand.burgundy },
        "&.active": { color: brand.burgundy, borderBottomColor: brand.burgundy },
      }}
    >
      <Icon size={18} />
      <Box component="span" sx={{ display: { xs: "none", sm: "inline" } }}>
        {label}
      </Box>
    </ButtonBase>
  );
}

export default function AppShell({ children }: { children: ReactNode }) {
  const { lang, setLang, t } = useLang();
  const { user, claims, roles, logout } = useAuth();
  const [menu, setMenu] = useState<HTMLElement | null>(null);

  const isStaff = roles.includes("agent") || roles.includes("supervisor");
  const nav = [
    { to: "/chat", label: t.navChat, icon: MessageSquare, show: roles.includes("customer") },
    { to: "/console", label: t.navConsole, icon: Headset, show: isStaff },
    { to: "/supervisor", label: t.navSupervisor, icon: LayoutDashboard, show: roles.includes("supervisor") },
  ].filter((n) => n.show);
  const name = claims?.preferred_username ?? "";
  const role = roles.includes("supervisor") ? t.roleSupervisor : roles.includes("agent") ? t.roleAgent : t.roleCustomer;

  return (
    <Box sx={{ minHeight: "100dvh", bgcolor: "background.default" }}>
      <AppBar
        position="sticky"
        elevation={0}
        sx={{ bgcolor: "#FFFFFF", color: "text.primary", borderTop: `3px solid ${brand.burgundy}`, borderBottom: 1, borderColor: "divider" }}
      >
        <Toolbar sx={{ gap: { xs: 1, sm: 2 }, minHeight: { xs: 64 }, px: { xs: 1.5, sm: 3 } }}>
          <Stack direction="row" spacing={1.25} sx={{ alignItems: "center", flexShrink: 0 }}>
            <BrandMark size={34} />
            <Box sx={{ display: { xs: nav.length > 1 ? "none" : "block", sm: "block" } }}>
              <Typography sx={{ fontWeight: 800, lineHeight: 1, fontSize: 19, letterSpacing: 0.2 }}>
                <Box component="span" sx={{ color: brand.burgundy }}>Nice</Box>
                <Box component="span" sx={{ color: LOGO_ROSE }}>Bank</Box>
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ display: { xs: "none", md: "block" }, lineHeight: 1.3 }}>
                {isStaff ? t.staffTagline : t.brandTagline}
              </Typography>
            </Box>
          </Stack>

          <Stack component="nav" direction="row" sx={{ flex: 1, ml: { sm: 2 }, alignSelf: "stretch" }}>
            {nav.length > 1 && nav.map((n) => <NavTab key={n.to} {...n} />)}
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
            <>
              <ButtonBase
                onClick={(e) => setMenu(e.currentTarget)}
                aria-label={t.accountMenu}
                aria-haspopup="menu"
                sx={{ borderRadius: 99, pl: 0.5, pr: { xs: 0.5, sm: 1 }, py: 0.5, gap: 1, "&:hover": { bgcolor: brand.blush } }}
              >
                <Avatar sx={{ width: 34, height: 34, bgcolor: brand.burgundy, fontSize: 14, fontWeight: 700 }}>
                  {name.slice(0, 1).toUpperCase()}
                </Avatar>
                <Box sx={{ display: { xs: "none", sm: "block" }, textAlign: "left" }}>
                  <Typography variant="body2" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
                    {name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ lineHeight: 1.2 }}>
                    {role}
                  </Typography>
                </Box>
                <Box sx={{ display: { xs: "none", sm: "flex" }, color: "text.secondary" }}>
                  <ChevronDown size={16} />
                </Box>
              </ButtonBase>
              <Menu
                anchorEl={menu}
                open={!!menu}
                onClose={() => setMenu(null)}
                anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
                transformOrigin={{ vertical: "top", horizontal: "right" }}
                slotProps={{ paper: { sx: { mt: 1, minWidth: 220 } } }}
              >
                <Box sx={{ px: 2, py: 1 }}>
                  <Typography variant="body2" sx={{ fontWeight: 700 }}>
                    {name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {role}
                  </Typography>
                </Box>
                <Divider />
                <MenuItem
                  onClick={() => {
                    setMenu(null);
                    void logout();
                  }}
                >
                  <ListItemIcon>
                    <LogOut size={16} />
                  </ListItemIcon>
                  {t.logout}
                </MenuItem>
              </Menu>
            </>
          )}
        </Toolbar>
      </AppBar>
      <Container maxWidth="lg" sx={{ py: { xs: 2, sm: 3 } }}>
        {children}
      </Container>
    </Box>
  );
}
