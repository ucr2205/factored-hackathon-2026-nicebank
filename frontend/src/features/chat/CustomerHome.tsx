import { useEffect } from "react";
import { Box } from "@mui/material";
import type { Overview } from "../../api/types";
import { useResource } from "../../api/useResource";
import { disputeMessage, useLang } from "../../app/i18n";
import AccountPanel from "./AccountPanel";
import ChatPanel from "./ChatPanel";
import { useChat } from "./useChat";

/** Customer home: account card (cards + recent movements) beside the dispute assistant. */
export default function CustomerHome() {
  const { lang } = useLang();
  const chat = useChat();
  const overview = useResource<Overview>("/api/me/overview");
  const { reload } = overview;

  // A verified action (e.g. a card block) changes what the account card shows.
  const verifiedCount = chat.entries.reduce((n, e) => n + (e.turn?.actions_verified.length ?? 0), 0);
  useEffect(() => {
    if (verifiedCount > 0) void reload();
  }, [verifiedCount, reload]);

  return (
    <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "1fr", md: "minmax(300px, 380px) 1fr" }, alignItems: "start" }}>
      <Box sx={{ order: { xs: 2, md: 1 } }}>
        <AccountPanel overview={overview.data} onDispute={(m) => void chat.send(disputeMessage(m, lang))} />
      </Box>
      <Box sx={{ order: { xs: 1, md: 2 } }}>
        <ChatPanel chat={chat} />
      </Box>
    </Box>
  );
}
