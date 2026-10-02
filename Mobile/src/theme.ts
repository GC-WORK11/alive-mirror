// Light professional theme — clean light canvas, near-opaque cards,
// deep teal brand, rose semantic dose ramp (not traffic-light colors).
export const T = {
  ink: "#1c1917",
  ink2: "#57534e",
  ink3: "#a8a29e",
  paper: "#f7f6f3",
  glass: "rgba(255,255,255,0.93)",
  glassBorder: "rgba(28,25,23,0.08)",
  accent: "#0f766e",
  accentSoft: "rgba(15,118,110,0.10)",
  doseLow: "#64748b",
  doseMid: "#e11d48",
  doseHigh: "#9f1239",
  ambient: "#06070a",
};

export const F = {
  light: "Outfit_300Light",
  reg: "Outfit_400Regular",
  med: "Outfit_500Medium",
  semi: "Outfit_600SemiBold",
  bold: "Outfit_700Bold",
};

export const doseColor = (avg: number | null | undefined) =>
  avg == null || avg < 60 ? T.doseLow : avg < 130 ? T.doseMid : T.doseHigh;
