/**
 * ALive-108 glyph set — flat single-ink pictographs on a 24×24 grid,
 * 2px stroke, round caps/joins. Vehicles drawn from the arrival angle
 * (side profile). Outline = inactive, filled = selected/emphasis.
 * No emoji, no icon-font mixing — every glyph names exactly one thing.
 */
import React from "react";
import Svg, { Circle, Line, Path, Rect } from "react-native-svg";

export type Glyph =
  | "walk" | "cycle" | "bike" | "auto" | "erick" | "car" | "cab" | "bus" | "metro"
  | "cigarette" | "lungs" | "dust" | "smoke" | "flame" | "leaf" | "wind"
  | "locate" | "flag" | "clock" | "bell" | "close" | "avatar" | "swap" | "pin";

export function Icon({
  name, color = "#1c1917", size = 24, filled = false,
}: {
  name: Glyph; color?: string; size?: number; filled?: boolean;
}) {
  const sw = 2;
  const fill = filled ? color : "none";
  const props = { stroke: color, strokeWidth: sw, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, fill };
  let body: React.ReactNode = null;
  switch (name) {
    case "walk":
      body = <>
        <Circle cx={12} cy={4.5} r={2.2} fill={fill} stroke={color} strokeWidth={sw} />
        <Path d="M12 8v6l-3.5 6M12 8l3 4M12 14l3.5 6" {...props} />
      </>;
      break;
    case "cycle":
      body = <>
        <Circle cx={5.5} cy={16.5} r={3.5} fill="none" stroke={color} strokeWidth={sw} />
        <Circle cx={18.5} cy={16.5} r={3.5} fill="none" stroke={color} strokeWidth={sw} />
        <Path d="M5.5 16.5 10 8h4l4.5 8.5M10 8l2.5 8.5" {...props} />
      </>;
      break;
    case "bike":
      body = <>
        <Circle cx={5} cy={17} r={3} fill="none" stroke={color} strokeWidth={sw} />
        <Circle cx={19} cy={17} r={3} fill="none" stroke={color} strokeWidth={sw} />
        <Path d="M8 17 12 8h3l4 9M8 17h8" {...props} />
      </>;
      break;
    case "auto": // auto-rickshaw, arrival angle — canopy + body + 3 wheels
      body = <>
        <Path d="M6 13a6 5 0 0 1 12 0" {...props} />
        <Rect x={4} y={13} width={16} height={5} rx={1.5} fill={fill} stroke={color} strokeWidth={sw} />
        <Circle cx={7.5} cy={19.5} r={1.6} fill={color} />
        <Circle cx={16.5} cy={19.5} r={1.6} fill={color} />
      </>;
      break;
    case "erick": // e-rickshaw — squarer canopy
      body = <>
        <Path d="M6 13V9a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v4" {...props} />
        <Rect x={4} y={13} width={16} height={5} rx={1.5} fill={fill} stroke={color} strokeWidth={sw} />
        <Circle cx={7.5} cy={19.5} r={1.6} fill={color} />
        <Circle cx={16.5} cy={19.5} r={1.6} fill={color} />
      </>;
      break;
    case "car":
      body = <>
        <Path d="M7 12 9.5 7h5L17 12" {...props} />
        <Rect x={3.5} y={12} width={17} height={5.5} rx={2} fill={fill} stroke={color} strokeWidth={sw} />
        <Circle cx={8} cy={19} r={1.7} fill={color} />
        <Circle cx={16} cy={19} r={1.7} fill={color} />
      </>;
      break;
    case "cab": // car + taxi dome
      body = <>
        <Rect x={10.5} y={5.5} width={3} height={1.8} rx={0.5} fill={fill} stroke={color} strokeWidth={1.4} />
        <Path d="M7 12 9.5 8h5L17 12" {...props} />
        <Rect x={3.5} y={12} width={17} height={5.5} rx={2} fill={fill} stroke={color} strokeWidth={sw} />
        <Circle cx={8} cy={19} r={1.7} fill={color} />
        <Circle cx={16} cy={19} r={1.7} fill={color} />
      </>;
      break;
    case "bus":
      body = <>
        <Rect x={5} y={4.5} width={14} height={13} rx={2.5} fill={fill} stroke={color} strokeWidth={sw} />
        <Line x1={5} y1={11} x2={19} y2={11} {...props} />
        <Circle cx={8.5} cy={19} r={1.5} fill={color} />
        <Circle cx={15.5} cy={19} r={1.5} fill={color} />
        <Line x1={9.5} y1={14} x2={14.5} y2={14} {...props} />
      </>;
      break;
    case "metro": // front view — rounded car, door seam, headlight bar
      body = <>
        <Rect x={6} y={3.5} width={12} height={14} rx={3.5} fill={fill} stroke={color} strokeWidth={sw} />
        <Line x1={6} y1={8} x2={18} y2={8} {...props} />
        <Line x1={12} y1={8} x2={12} y2={17.5} {...props} />
        <Path d="M9 20.5 7.5 22M15 20.5 16.5 22" {...props} />
      </>;
      break;
    case "cigarette": // the dose unit — burning tip + filter
      body = <>
        <Rect x={4} y={10} width={13} height={4} rx={0.5} fill={fill} stroke={color} strokeWidth={sw} />
        <Rect x={17} y={10} width={3.5} height={4} fill={fill} stroke={color} strokeWidth={sw} />
        <Path d="M6 10c-1-2 1-3 0-5M9 10c-1-2 1-3 0-5" {...props} />
      </>;
      break;
    case "lungs":
      body = <>
        <Path d="M12 4v5" {...props} />
        <Path d="M11 9C9 8 7 9.5 6.5 12 6 14.5 5 18 6.5 19.5c1.5 1.5 4-.5 4.5-4V9z" {...props} />
        <Path d="M13 9c2-1 4 .5 4.5 3 .5 2.5 1.5 6 0 7.5-1.5 1.5-4-.5-4.5-4V9z" {...props} />
      </>;
      break;
    case "dust": // dust swirl — 3 curled gusts
      body = <>
        <Path d="M3 8h11a2.5 2.5 0 1 0-2.5-2.5" {...props} />
        <Path d="M3 12h14a2.5 2.5 0 1 1-2.5 2.5" {...props} />
        <Path d="M3 16h9a2.5 2.5 0 1 1-2.5 2.5" {...props} />
      </>;
      break;
    case "smoke": // smoke plume — rising column widening
      body = <>
        <Path d="M12 21c-3-2-4-4-2.5-6S8 11 10 9.5 9.5 6 12 3" {...props} />
        <Path d="M12 21c3-2 4-4 2.5-6" {...props} />
      </>;
      break;
    case "flame":
      body = <Path d="M12 3c1 3-1 4-1 7 0 0-3-1-3-4-3 2-4 5-4 8a8 8 0 0 0 16 0c0-4-4-9-8-11z" {...props} />;
      break;
    case "leaf":
      body = <><Path d="M5 19C5 9 11 4 20 4c0 9-5 15-15 15z" {...props} /><Path d="M5 19C9 15 13 11 17 7" {...props} /></>;
      break;
    case "wind":
      body = <>
        <Path d="M3 8h10a2.5 2.5 0 1 0-2.5-2.5" {...props} />
        <Path d="M3 12h14a2.5 2.5 0 1 1-2.5 2.5" {...props} />
        <Path d="M3 16h7" {...props} />
      </>;
      break;
    case "locate": // crosshair + dot
      body = <>
        <Circle cx={12} cy={12} r={3.2} fill={filled ? color : "none"} stroke={color} strokeWidth={sw} />
        <Circle cx={12} cy={12} r={8} fill="none" stroke={color} strokeWidth={sw} />
        <Path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3" {...props} />
      </>;
      break;
    case "flag":
      body = <>
        <Line x1={6} y1={3} x2={6} y2={21} {...props} />
        <Path d="M6 4h11l-2.5 3.5L17 11H6" {...props} />
      </>;
      break;
    case "clock":
      body = <>
        <Circle cx={12} cy={12} r={8.5} fill={fill} stroke={color} strokeWidth={sw} />
        <Path d="M12 7v5l3.5 2" {...props} stroke={filled ? "#fff" : color} />
      </>;
      break;
    case "bell":
      body = <>
        <Path d="M6 16v-5a6 6 0 0 1 12 0v5l1.5 2.5h-15z" {...props} />
        <Path d="M10 21a2.2 2.2 0 0 0 4 0" {...props} />
      </>;
      break;
    case "close":
      body = <Path d="M6 6l12 12M18 6 6 18" {...props} />;
      break;
    case "avatar":
      body = <>
        <Circle cx={12} cy={8} r={4} fill={fill} stroke={color} strokeWidth={sw} />
        <Path d="M4.5 20a7.5 7.5 0 0 1 15 0" {...props} />
      </>;
      break;
    case "swap":
      body = <Path d="M7 4v12M7 16l-3-3M7 16l3-3M17 20V8M17 8l-3 3M17 8l3 3" {...props} />;
      break;
    case "pin":
      body = <><Path d="M12 21s-7-6.6-7-11a7 7 0 0 1 14 0c0 4.4-7 11-7 11z" fill={fill} stroke={color} strokeWidth={sw} /><Circle cx={12} cy={10} r={2.6} fill={filled ? "#fff" : color} /></>;
      break;
  }
  return <Svg width={size} height={size} viewBox="0 0 24 24">{body}</Svg>;
}

/** Vehicle key → glyph (exposure vehicle strings like driving_two_wheeler). */
export function vehicleGlyph(vehicle: string): Glyph {
  const k = (vehicle || "").toLowerCase();
  if (k.includes("walk")) return "walk";
  if (k.includes("cycle") || k.includes("bicycle")) return "cycle";
  if (k.includes("two_wheeler") || k.includes("bike") || k.includes("scooter") || k.includes("moto")) return "bike";
  if (k.includes("e_rickshaw") || k.includes("erick")) return "erick";
  if (k.includes("auto") || k.includes("rickshaw")) return "auto";
  if (k.includes("bus")) return "bus";
  if (k.includes("metro")) return "metro";
  if (k.includes("cab") || k.includes("taxi")) return "cab";
  return "car";
}

/** Report kind → glyph (ReportsLayer + picker share this mapping). */
export function reportGlyph(kind: string): Glyph {
  switch (kind) {
    case "dust": return "dust";
    case "smoke": return "smoke";
    case "burning": return "flame";
    case "clean": return "leaf";
    default: return "flag";
  }
}
