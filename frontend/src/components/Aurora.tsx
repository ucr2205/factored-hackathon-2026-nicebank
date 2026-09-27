import { Box } from "@mui/material";
import { keyframes } from "@emotion/react";

const drift = keyframes`
  0%   { transform: translate3d(0, 0, 0) scale(1); }
  50%  { transform: translate3d(12%, -10%, 0) scale(1.12); }
  100% { transform: translate3d(-8%, 8%, 0) scale(0.94); }
`;

const pulse = keyframes`
  0%, 100% { opacity: 0.55; }
  50%      { opacity: 0.95; }
`;

const orb = (size: number, pos: object, color: string, duration: number, delay = 0) => ({
  position: "absolute" as const,
  width: size,
  height: size,
  borderRadius: "50%",
  background: `radial-gradient(circle at 35% 35%, ${color}, transparent 70%)`,
  filter: "blur(18px)",
  animation: `${drift} ${duration}s ease-in-out ${delay}s infinite alternate, ${pulse} ${duration / 2}s ease-in-out infinite`,
  pointerEvents: "none" as const,
  ...pos,
});

/** Floating glow orbs for burgundy surfaces; static when the user prefers reduced motion. */
export default function Aurora() {
  return (
    <Box
      aria-hidden
      sx={{
        position: "absolute",
        inset: 0,
        overflow: "hidden",
        pointerEvents: "none",
        "@media (prefers-reduced-motion: reduce)": { "& > *": { animation: "none !important" } },
      }}
    >
      <Box sx={orb(220, { top: -80, right: -60 }, "rgba(255, 255, 255, 0.34)", 16)} />
      <Box sx={orb(160, { bottom: -70, left: -40 }, "rgba(232, 180, 195, 0.45)", 20, 2)} />
      <Box sx={orb(90, { top: "40%", right: "30%" }, "rgba(255, 255, 255, 0.22)", 12, 1)} />
    </Box>
  );
}
