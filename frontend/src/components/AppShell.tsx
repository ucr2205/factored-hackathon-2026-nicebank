// Frame of every signed-in screen: gradient navbar with role-based tabs (Chat, Casos, Supervisión), the es/pt
// language switch and the account menu with logout. No API calls.
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


/** NiceBank logo mark (static image from public/brand); decorative, so it has an empty alt. */
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
        color: "rgba(255, 255, 255, 0.72)",
        fontWeight: 600,
        fontSize: 14,
        borderBottom: "3px solid transparent",
        borderTop: "3px solid transparent",
        transition: "color .15s, border-color .15s, background-color .15s",
        "&:hover": { color: "#FFFFFF", bgcolor: "rgba(255, 255, 255, 0.06)" },
        "&.active": { color: "#FFFFFF", borderBottomColor: brand.logoRose },
      }}
    >
      <Icon size={18} />
      <Box component="span" sx={{ display: { xs: "none", sm: "inline" } }}>
        {label}
      </Box>
    </ButtonBase>
  );
}

/** Navbar plus a centered container for the routed page; tabs show only when the user has more than one. */
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
        sx={{ background: brand.gradient, color: "#FFFFFF", boxShadow: "0 6px 20px rgba(46, 10, 24, 0.18)" }}
      >
        <Toolbar sx={{ gap: { xs: 1, sm: 2 }, minHeight: { xs: 64 }, px: { xs: 1.5, sm: 3 } }}>
          <Stack direction="row" spacing={1.25} sx={{ alignItems: "center", flexShrink: 0 }}>
            <BrandMark size={34} />
            <Box sx={{ display: { xs: nav.length > 1 ? "none" : "block", sm: "block" } }}>
              <Typography sx={{ fontWeight: 800, lineHeight: 1, fontSize: 19, letterSpacing: 0.2 }}>
                <Box component="span" sx={{ color: "#FFFFFF" }}>Nice</Box>
                <Box component="span" sx={{ color: brand.logoRose }}>Bank</Box>
              </Typography>
              <Typography variant="caption" sx={{ display: { xs: "none", md: "block" }, lineHeight: 1.3, color: "rgba(255, 255, 255, 0.65)" }}>
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
            aria-label="Idioma"
            variant="standard"
            disableUnderline
            renderValue={(v) => (
              <Stack direction="row" spacing={0.75} sx={{ alignItems: "center" }}>
                <Globe size={16} />
                <span>{v.toUpperCase()}</span>
              </Stack>
            )}
            sx={{ fontWeight: 700, color: "#FFFFFF", "& .MuiSelect-icon": { color: "#FFFFFF" } }}
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
                sx={{ borderRadius: 99, pl: 0.5, pr: { xs: 0.5, sm: 1 }, py: 0.5, gap: 1, "&:hover": { bgcolor: "rgba(255, 255, 255, 0.08)" } }}
              >
                <Avatar sx={{ width: 34, height: 34, bgcolor: brand.logoRose, color: brand.burgundyDeep, fontSize: 14, fontWeight: 800 }}>
                  {name.slice(0, 1).toUpperCase()}
                </Avatar>
                <Box sx={{ display: { xs: "none", sm: "block" }, textAlign: "left" }}>
                  <Typography variant="body2" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
                    {name}
                  </Typography>
                  <Typography variant="caption" sx={{ lineHeight: 1.2, color: "rgba(255, 255, 255, 0.65)" }}>
                    {role}
                  </Typography>
                </Box>
                <Box sx={{ display: { xs: "none", sm: "flex" }, color: "rgba(255, 255, 255, 0.65)" }}>
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
