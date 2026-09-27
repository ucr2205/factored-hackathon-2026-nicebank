import { Box, ButtonBase, Chip, Paper, Skeleton, Stack, Typography } from "@mui/material";
import { ChevronRight } from "lucide-react";
import type { Candidate, Overview } from "../../api/types";
import { formatMoney, useLang } from "../../app/i18n";
import { brand } from "../../app/theme";
import Aurora from "../../components/Aurora";

const CARD_TYPES: Record<string, { es: string; pt: string }> = {
  "Tarjeta Crédito": { es: "Tarjeta de crédito", pt: "Cartão de crédito" },
  "Tarjeta Débito": { es: "Tarjeta de débito", pt: "Cartão de débito" },
};

function dayLabel(iso: string, lang: "es" | "pt") {
  try {
    return new Intl.DateTimeFormat(lang === "pt" ? "pt-BR" : "es-MX", { day: "numeric", month: "long", timeZone: "UTC" })
      .format(new Date(iso))
      .toUpperCase();
  } catch {
    return iso;
  }
}

/** Mockup-style account card: burgundy header with the customer's cards, then recent movements. */
export default function AccountPanel({ overview, onDispute }: { overview: Overview | null; onDispute: (m: Candidate) => void }) {
  const { lang, t } = useLang();
  const groups: Record<string, Candidate[]> = {};
  for (const m of overview?.recent ?? []) (groups[m.date.slice(0, 10)] ??= []).push(m);

  return (
    <Paper sx={{ overflow: "hidden", border: "none", boxShadow: "0 12px 32px rgba(74, 16, 38, 0.10)" }}>
      <Box
        sx={{
          background: `linear-gradient(145deg, ${brand.burgundy} 0%, ${brand.burgundyDark} 100%)`,
          color: "#fff",
          px: 3,
          pt: 3,
          pb: 4,
          borderBottomLeftRadius: 32,
          borderBottomRightRadius: 32,
          position: "relative",
          overflow: "hidden",
        }}
      >
        <Aurora />
        <Typography variant="overline" sx={{ opacity: 0.8, position: "relative" }}>
          {t.myCards}
        </Typography>
        <Typography variant="h5" sx={{ mb: 2, position: "relative" }}>
          {overview ? `${t.hello}, ${overview.first_name}` : <Skeleton sx={{ bgcolor: "rgba(255,255,255,0.2)" }} width={160} />}
        </Typography>
        <Stack spacing={1.25} sx={{ position: "relative" }}>
          {overview?.cards.map((c) => (
            <Stack key={c.last4} direction="row" sx={{ alignItems: "center", justifyContent: "space-between" }}>
              <Box>
                <Typography variant="caption" sx={{ opacity: 0.75 }}>
                  {CARD_TYPES[c.type]?.[lang] ?? c.type}
                </Typography>
                <Typography sx={{ fontWeight: 700, letterSpacing: "0.18em" }}>•••• {c.last4}</Typography>
              </Box>
              <Chip
                size="small"
                label={c.status === "Active" ? t.cardActive : c.status === "Blocked" ? t.cardBlocked : c.status}
                sx={{
                  bgcolor: c.status === "Active" ? "rgba(255,255,255,0.18)" : brand.rose,
                  color: c.status === "Active" ? "#fff" : brand.burgundyDeep,
                }}
              />
            </Stack>
          ))}
          {overview && overview.cards.length === 0 && <Typography variant="body2">{t.noCards}</Typography>}
        </Stack>
      </Box>

      <Box sx={{ px: 3, py: 2.5 }}>
        <Stack direction="row" sx={{ alignItems: "baseline", justifyContent: "space-between", mb: 1 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 800, color: brand.burgundy }}>
            {t.recentMovements}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {t.tapToDispute}
          </Typography>
        </Stack>
        {!overview && [0, 1, 2, 3].map((i) => <Skeleton key={i} height={40} />)}
        {Object.entries(groups).map(([day, items]) => (
          <Box key={day} sx={{ mb: 1.5 }}>
            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 700 }}>
              {dayLabel(day, lang)}
            </Typography>
            {items.map((m) => (
              <ButtonBase
                key={m.transaction_id}
                onClick={() => onDispute(m)}
                sx={{ width: "100%", borderRadius: 2, px: 1, mx: -1, py: 1, "&:hover": { bgcolor: brand.blush } }}
              >
                <Stack direction="row" spacing={1} sx={{ alignItems: "center", width: "100%", textAlign: "left" }}>
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography variant="body2" noWrap sx={{ fontWeight: 700, textTransform: "uppercase", fontSize: 13 }}>
                      {m.merchant || "—"}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      •••• {m.card_last4}
                      {m.country ? ` · ${m.country}` : ""}
                    </Typography>
                  </Box>
                  <Typography variant="body2" sx={{ fontWeight: 700, whiteSpace: "nowrap" }}>
                    − {formatMoney(m.amount, m.currency, lang)}
                  </Typography>
                  <ChevronRight size={16} color="#B9A6AE" />
                </Stack>
              </ButtonBase>
            ))}
          </Box>
        ))}
      </Box>
    </Paper>
  );
}
