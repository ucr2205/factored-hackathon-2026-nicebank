import { lazy, Suspense, useEffect, type ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { Box, CircularProgress, Stack, Typography } from "@mui/material";
import AppShell, { BrandMark } from "../components/AppShell";
import Aurora from "../components/Aurora";
import { brand } from "./theme";
import { useAuth, type Role } from "../auth/AuthProvider";
import CustomerHome from "../features/chat/CustomerHome";
import { useLang } from "./i18n";
import { StepUpDialog } from "../auth/StepUpDialog";

// Staff screens load on demand, so customers never download the console code.
const HandoffQueuePage = lazy(() => import("../features/console/HandoffQueuePage"));
const HandoffDetailPage = lazy(() => import("../features/console/HandoffDetailPage"));
const SupervisorPage = lazy(() => import("../features/supervisor/SupervisorPage"));

/** Signed-out visitors go straight to the NiceBank-themed Keycloak login (Authorization Code + PKCE). */
function RedirectToLogin() {
  const { t } = useLang();
  const { login } = useAuth();
  useEffect(() => {
    void login();
  }, [login]);
  return (
    <Stack
      spacing={2}
      sx={{
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100dvh",
        position: "relative",
        color: "#fff",
        background: `linear-gradient(150deg, ${brand.burgundy} 0%, ${brand.burgundyDark} 55%, ${brand.burgundyDeep} 100%)`,
      }}
    >
      <Aurora />
      <BrandMark size={56} />
      <CircularProgress size={24} sx={{ color: "#fff" }} />
      <Typography variant="body2" sx={{ opacity: 0.85, position: "relative" }}>
        {t.redirecting}
      </Typography>
    </Stack>
  );
}

function Home() {
  const { user, roles } = useAuth();
  if (!user) return <RedirectToLogin />;
  if (roles.includes("customer")) return <Navigate to="/chat" replace />;
  if (roles.includes("supervisor")) return <Navigate to="/supervisor" replace />;
  if (roles.includes("agent")) return <Navigate to="/console" replace />;
  return <Typography>No role assigned.</Typography>;
}

/** Client-side gating for navigation only; the backend enforces every permission. */
function RequireRole({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { user, roles: mine } = useAuth();
  if (!user || !roles.some((r) => mine.includes(r))) return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  const { ready, user } = useAuth();
  if (!ready) {
    return (
      <Box sx={{ display: "grid", placeItems: "center", height: "100dvh" }}>
        <CircularProgress />
      </Box>
    );
  }
  if (!user) return <RedirectToLogin />;
  return (
    <BrowserRouter>
      <AppShell>
        <Suspense fallback={<CircularProgress />}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/chat" element={<RequireRole roles={["customer"]}><CustomerHome /></RequireRole>} />
          <Route path="/console" element={<RequireRole roles={["agent", "supervisor"]}><HandoffQueuePage /></RequireRole>} />
          <Route path="/console/:id" element={<RequireRole roles={["agent", "supervisor"]}><HandoffDetailPage /></RequireRole>} />
          <Route path="/supervisor" element={<RequireRole roles={["supervisor"]}><SupervisorPage /></RequireRole>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </Suspense>
        <StepUpDialog />
      </AppShell>
    </BrowserRouter>
  );
}
