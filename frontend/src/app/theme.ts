import { createTheme } from "@mui/material/styles";

// NiceBank (fictitious brand): burgundy and white, large rounded cards and bold amounts.
export const brand = {
  burgundy: "#7A1F3D",
  burgundyDark: "#4A1026",
  burgundyDeep: "#2E0A18",
  rose: "#E8B4C3",
  blush: "#F8EEF1",
  logoRose: "#E5769A", // the "Bank" half of the logo
  line: "#E9D3DB", // card borders and dividers
  canvas: "#F6EEF1", // page background: a blush tint instead of plain white
  ink: "#23161B",
  /** The navbar and hero surfaces (same gradient as the login screen). */
  gradient: "linear-gradient(120deg, #7A1F3D 0%, #4A1026 55%, #2E0A18 100%)",
};

/** MUI theme on the brand palette: flat bordered cards, pill buttons, burgundy table headers. */
export const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: brand.burgundy, dark: brand.burgundyDark, contrastText: "#FFFFFF" },
    secondary: { main: brand.burgundyDark, contrastText: "#FFFFFF" },
    background: { default: brand.canvas, paper: "#FFFFFF" },
    text: { primary: brand.ink, secondary: "#6E5A62" },
    divider: brand.line,
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
      styleOverrides: { root: { border: `1px solid ${brand.line}` } },
    },
    MuiAppBar: { styleOverrides: { root: { border: "none" } } },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: { root: { borderRadius: 999, paddingInline: 18 } },
    },
    MuiChip: { styleOverrides: { root: { fontWeight: 600 } } },
    MuiTableCell: {
      styleOverrides: {
        head: { fontWeight: 700, color: brand.burgundyDark, fontSize: 12, textTransform: "uppercase", letterSpacing: "0.06em", backgroundColor: brand.blush },
        root: { borderColor: brand.line },
      },
    },
    MuiTableRow: { styleOverrides: { root: { "&.MuiTableRow-hover:hover": { backgroundColor: "rgba(122, 31, 61, 0.04)" } } } },
    MuiTabs: { styleOverrides: { indicator: { height: 3, borderRadius: 3 } } },
    MuiTab: { styleOverrides: { root: { fontWeight: 700, textTransform: "none" } } },
    MuiDialog: { styleOverrides: { paper: { borderTop: `4px solid ${brand.burgundy}` } } },
    MuiLinearProgress: { styleOverrides: { root: { backgroundColor: brand.blush } } },
  },
});
