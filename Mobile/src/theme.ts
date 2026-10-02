export const T = {
  ink: "#101828",
  ink2: "#475467",
  ink3: "#98A2B3",
  paper: "#F6F4EF",
  glass: "rgba(255,255,255,0.72)",
  glassBorder: "rgba(255,255,255,0.55)",
  accent: "#0E7C6B",
  doseLow: "#64748b",
  doseMid: "#c2415c",
  doseHigh: "#7f1d1d",
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
