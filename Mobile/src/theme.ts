// Night-operations theme — deep ink canvas, lit glass, dose ramp that
// glows instead of tinting. Coherent with AmbientMode (#06070a).
export const T = {
  ink: "#e7e5e4",
  ink2: "#a8a29e",
  ink3: "#78716c",
  paper: "#0b0e11",
  glass: "rgba(17,22,28,0.68)",
  glassBorder: "rgba(255,255,255,0.10)",
  accent: "#2dd4bf",
  doseLow: "#94a3b8",
  doseMid: "#fb7185",
  doseHigh: "#e11d48",
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
