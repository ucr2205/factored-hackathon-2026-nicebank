// Customer /chat page: GET /api/me/overview (cards, recent movements) and GET /api/me/disputes (polled every 30 s),
// both reloaded when the chat verifies an action or creates a case; chat calls go through useChat.
import { useEffect } from "react";
import { Box } from "@mui/material";
import type { MyDispute, Overview } from "../../api/types";
import { useResource } from "../../api/useResource";
import { disputeMessage, useLang } from "../../app/i18n";
import AccountPanel from "./AccountPanel";
import ChatPanel from "./ChatPanel";
import MyDisputesPanel from "./MyDisputesPanel";
import { useChat } from "./useChat";

/** Customer home: account card (cards + recent movements) and "Mis disputas" beside the dispute assistant. */
export default function CustomerHome() {
  const { lang } = useLang();
  const chat = useChat();
  const overview = useResource<Overview>("/api/me/overview");
  const disputes = useResource<MyDispute[]>("/api/me/disputes", 30_000);
  const { reload } = overview;
  const reloadDisputes = disputes.reload;

  // A verified action (e.g. a card block) changes what the account card shows.
  const verifiedCount = chat.entries.reduce((n, e) => n + (e.turn?.actions_verified.length ?? 0), 0);
  useEffect(() => {
    if (verifiedCount > 0) void reload();
  }, [verifiedCount, reload]);

  // A new case or handoff in the conversation appears in "Mis disputas" right away.
  const created = chat.entries.filter((e) => e.turn?.case_id || e.turn?.handoff_id).length;
  useEffect(() => {
    if (created > 0) void reloadDisputes();
  }, [created, reloadDisputes]);

  return (
    <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "1fr", md: "minmax(300px, 380px) 1fr" }, alignItems: "start" }}>
      <Box sx={{ order: { xs: 2, md: 1 } }}>
        <AccountPanel overview={overview.data} onDispute={(m) => void chat.send(disputeMessage(m, lang))} />
        <MyDisputesPanel items={disputes.data} />
      </Box>
      <Box sx={{ order: { xs: 1, md: 2 } }}>
        <ChatPanel chat={chat} />
      </Box>
    </Box>
  );
}
