import { createTheme } from "@mui/material/styles";

// NiceBank (fictitious brand): burgundy and white, large rounded cards and bold amounts.
export const brand = {
  burgundy: "#7A1F3D",
  burgundyDark: "#4A1026",
  burgundyDeep: "#2E0A18",
  rose: "#E8B4C3",
  blush: "#F8EEF1",
  ink: "#23161B",
};

export const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: brand.burgundy, dark: brand.burgundyDark, contrastText: "#FFFFFF" },
    secondary: { main: brand.burgundyDark, contrastText: "#FFFFFF" },
    background: { default: "#FAF7F8", paper: "#FFFFFF" },
    text: { primary: brand.ink, secondary: "#6E5A62" },
    divider: "#EFE3E7",
  },
  shape: { borderRadius: 14 },
  typography: {
    fontFamily: "'Montserrat', 'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
    h4: { fontWeight: 700, letterSpacing: "-0.01em" },
    h5: { fontWeight: 700 },
    h6: { fontWeight: 700 },
    overline: { fontWeight: 700, letterSpacing: "0.12em" },
    button: { textTransform: "none", fontWeight: 700 },
  },
  components: {
    MuiPaper: {
      defaultProps: { elevation: 0 },
      styleOverrides: { root: { border: "1px solid #EFE3E7" } },
    },
    MuiAppBar: { styleOverrides: { root: { border: "none" } } },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: { root: { borderRadius: 999, paddingInline: 18 } },
    },
    MuiChip: { styleOverrides: { root: { fontWeight: 600 } } },
    MuiTableCell: { styleOverrides: { head: { fontWeight: 700, color: "#6E5A62", fontSize: 12, textTransform: "uppercase", letterSpacing: "0.06em" } } },
  },
});
