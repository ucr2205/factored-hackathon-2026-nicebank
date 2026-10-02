// Mounted once in App. No API calls: the iframe talks to Keycloak and the result returns through modalNavigator.ts.
import { useEffect, useState, useSyncExternalStore } from "react";
import { Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, Stack, Typography, useMediaQuery } from "@mui/material";
import { ShieldCheck } from "lucide-react";
import { useLang } from "../app/i18n";
import { brand } from "../app/theme";
import { STEP_UP_FULL_PAGE, stepUpNavigator } from "./modalNavigator";

/** Keycloak's code page in a dialog over the blurred app while a step-up runs (see modalNavigator.ts). */
export function StepUpDialog() {
  const url = useSyncExternalStore(stepUpNavigator.subscribe, stepUpNavigator.current);
  const { t } = useLang();
  const fullScreen = useMediaQuery("(max-width:600px)");
  const [loaded, setLoaded] = useState(false);
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    setLoaded(false);
    setSlow(false);
    if (!url) return;
    const timer = setTimeout(() => setSlow(true), 8000);
    return () => clearTimeout(timer);
  }, [url]);

  return (
    <Dialog
      open={!!url}
      onClose={() => stepUpNavigator.cancel()}
      fullScreen={fullScreen}
      maxWidth="xs"
      fullWidth
      aria-labelledby="stepup-title"
      slotProps={{
        backdrop: { sx: { backdropFilter: "blur(6px)", backgroundColor: "rgba(46, 10, 24, 0.45)" } },
        paper: { sx: { overflow: "hidden", borderTop: `4px solid ${brand.burgundy}` } },
      }}
    >
      <Stack direction="row" spacing={1.5} sx={{ alignItems: "center", px: 3, pt: 2.5, pb: 1 }}>
        <Box sx={{ display: "grid", placeItems: "center", width: 36, height: 36, borderRadius: "50%", bgcolor: brand.blush }}>
          <ShieldCheck size={20} color={brand.burgundy} />
        </Box>
        <Box>
          <Typography id="stepup-title" variant="h6" sx={{ lineHeight: 1.2 }}>
            {t.stepUpTitle}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {t.stepUpHint}
          </Typography>
        </Box>
      </Stack>
      <DialogContent sx={{ p: 0, position: "relative", height: fullScreen ? "100%" : 430 }}>
        {!loaded && (
          <Box sx={{ position: "absolute", inset: 0, display: "grid", placeItems: "center" }}>
            <CircularProgress />
          </Box>
        )}
        {url && (
          <Box
            component="iframe"
            title={t.stepUpTitle}
            src={url}
            onLoad={() => setLoaded(true)}
            sx={{ border: 0, width: "100%", height: "100%", display: "block", visibility: loaded ? "visible" : "hidden" }}
          />
        )}
      </DialogContent>
      <DialogActions sx={{ justifyContent: "space-between", px: 3, pb: 2 }}>
        <Box>
          {slow && !loaded && (
            <Button size="small" onClick={() => stepUpNavigator.cancel(STEP_UP_FULL_PAGE)}>
              {t.stepUpFullPage}
            </Button>
          )}
        </Box>
        <Button onClick={() => stepUpNavigator.cancel()}>{t.stepUpCancel}</Button>
      </DialogActions>
    </Dialog>
  );
}
