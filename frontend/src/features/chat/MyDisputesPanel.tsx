import { Chip, Paper, Skeleton, Stack, Typography } from "@mui/material";
import type { MyDispute } from "../../api/types";
import { formatDateTime, formatMoney, useLang } from "../../app/i18n";
import { brand } from "../../app/theme";

// Dispute type names in the customer's language (the policy's display names).
const TYPE_NAMES: Record<string, { es: string; pt: string }> = {
  unrecognized_charge: { es: "Cargo no reconocido", pt: "Cobrança não reconhecida" },
  duplicate_charge: { es: "Cargo duplicado", pt: "Cobrança duplicada" },
  wrong_amount: { es: "Monto incorrecto", pt: "Valor incorreto" },
  not_received: { es: "Compra no recibida", pt: "Compra não recebida" },
  atm_cash_not_dispensed: { es: "Cajero no entregó el efectivo", pt: "Caixa eletrônico não liberou o dinheiro" },
  card_lost_stolen: { es: "Tarjeta perdida o robada", pt: "Cartão perdido ou roubado" },
};

/** "Mis disputas": the customer's cases opened by the assistant and handoffs to a specialist, with their status. */
export default function MyDisputesPanel({ items }: { items: MyDispute[] | null }) {
  const { lang, t } = useLang();
  const statusLabel = (d: MyDispute) => {
    if (d.resolution) return d.resolution.outcome === "accepted" ? t.outcomeAccepted : t.outcomeRejected;
    if (d.status === "claimed") return t.statusClaimed;
    if (d.status === "closed") return t.statusClosed;
    return t.statusOpen;
  };

  return (
    <Paper sx={{ px: 3, py: 2.5, mt: 3 }}>
      <Typography variant="subtitle2" sx={{ fontWeight: 800, color: brand.burgundy, mb: 1 }}>
        {t.myDisputes}
      </Typography>
      {!items && [0, 1].map((i) => <Skeleton key={i} height={48} />)}
      {items && items.length === 0 && (
        <Typography variant="body2" color="text.secondary">
          {t.noDisputes}
        </Typography>
      )}
      <Stack spacing={1.25}>
        {items?.map((d) => (
          <Stack key={d.id} direction="row" spacing={1} sx={{ alignItems: "flex-start" }}>
            <Stack sx={{ flex: 1, minWidth: 0 }}>
              <Typography variant="body2" sx={{ fontWeight: 700 }}>
                {TYPE_NAMES[d.dispute_type]?.[lang] ?? (d.kind === "case" ? t.disputeCase : t.disputeHandoff)}
                {d.kind === "case" ? ` · ${d.id}` : ""}
              </Typography>
              <Typography variant="caption" color="text.secondary" noWrap>
                {d.merchant ? `${d.merchant} · ` : ""}
                {d.amount != null && d.currency ? `${formatMoney(d.amount, d.currency, lang)} · ` : ""}
                {formatDateTime(d.created_at, lang)}
              </Typography>
              {d.resolution?.note && (
                <Typography variant="caption" sx={{ mt: 0.5 }}>
                  {d.resolution.note}
                </Typography>
              )}
            </Stack>
            <Chip
              size="small"
              label={statusLabel(d)}
              sx={{ bgcolor: d.status === "closed" ? brand.blush : "rgba(122, 31, 61, 0.08)", color: brand.burgundyDeep, maxWidth: 190 }}
            />
          </Stack>
        ))}
      </Stack>
    </Paper>
  );
}
