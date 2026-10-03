/**
 * ALive-108 icon set — Material Symbols Rounded geometry (Apache-2.0) on a
 * 24px grid, rendered via react-native-svg. Outline at rest, filled when
 * selected (docs/plan/03 §icons). The auto-rickshaw is a custom glyph drawn
 * on the same grid. No emoji, no icon fonts — one glyph names one thing.
 */
import React from "react";
import Svg, { Circle, Line, Path, Rect } from "react-native-svg";
import { V2T } from "./theme";

export type Glyph =
  // modes
  | "walk" | "cycle" | "bike" | "auto" | "erick" | "car" | "cab" | "bus" | "metro"
  // chrome
  | "menu" | "locate" | "layers" | "search" | "pin" | "chevron" | "share" | "star"
  | "home" | "work" | "trash" | "info" | "warn" | "close" | "clock" | "bell" | "flag"
  // units + hazards
  | "cigarette" | "dust" | "smoke" | "flame" | "leaf" | "wind";

export function Icon({
  name, color = V2T.text, size = 24, filled = false,
}: {
  name: Glyph; color?: string; size?: number; filled?: boolean;
}) {
  const sw = 2;
  const st = { stroke: color, strokeWidth: sw, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, fill: "none" };
  let body: React.ReactNode;
  switch (name) {
    /* ------------------------------------------------ modes (side profile) */
    case "walk":
      body = filled ? (
        <Path fill={color} d="M13.5 5.5c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zM9.8 8.9 7 23h2.1l1.8-8 2.1 2v6h2v-7.5l-2.1-2 .6-3C14.8 12 16.8 13 19 13v-2c-1.9 0-3.5-1-4.3-2.4l-1-1.6c-.4-.6-1-1-1.7-1-.3 0-.5.1-.8.1L6 8.3V13h2V9.6l1.8-.7" />
      ) : (
        <>
          <Circle cx={13.5} cy={3.5} r={2} {...st} />
          <Path d="M13.5 7.5c-1 0-1.7.4-2.3 1L7 12.5M11.5 10l-2 3 2.5 2-1 6M11.5 15l-3.5-1M13 17l2 4" {...st} />
        </>
      );
      break;
    case "cycle":
      body = filled ? (
        <Path fill={color} d="M15.5 5.5c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zM5 12c-2.8 0-5 2.2-5 5s2.2 5 5 5 5-2.2 5-5-2.2-5-5-5zm0 8.5c-1.9 0-3.5-1.6-3.5-3.5s1.6-3.5 3.5-3.5 3.5 1.6 3.5 3.5-1.6 3.5-3.5 3.5zm5.8-10 2.4-2.4.8.8c1.3 1.3 3 2.1 5.1 2.1V9c-1.5 0-2.7-.6-3.6-1.5l-1.9-1.9c-.5-.4-1-.6-1.6-.6s-1.1.2-1.4.6L7.8 8.4c-.4.4-.6.9-.6 1.4 0 .6.2 1.1.6 1.4L11 14v5h2v-6.2l-2.2-2.3zM19 12c-2.8 0-5 2.2-5 5s2.2 5 5 5 5-2.2 5-5-2.2-5-5-5zm0 8.5c-1.9 0-3.5-1.6-3.5-3.5s1.6-3.5 3.5-3.5 3.5 1.6 3.5 3.5-1.6 3.5-3.5 3.5z" />
      ) : (
        <>
          <Circle cx={5.5} cy={17} r={3.5} {...st} />
          <Circle cx={18.5} cy={17} r={3.5} {...st} />
          <Circle cx={14.5} cy={4.5} r={1.6} fill={color} />
          <Path d="M5.5 17 10 9h4l4.5 8M10 9l2.5 8M12.5 6.5 14.5 9" {...st} />
        </>
      );
      break;
    case "bike": // scooter / two-wheeler
      body = filled ? (
        <Path fill={color} d="M19.44 9.03 15.41 5H11v2h3.59l2 2H5c-2.8 0-5 2.2-5 5s2.2 5 5 5c2.46 0 4.45-1.69 4.9-4h1.65l2.77-2.77c-.21.54-.32 1.14-.32 1.77 0 2.8 2.2 5 5 5s5-2.2 5-5c0-2.65-1.97-4.77-4.56-4.97zM7.82 15C7.4 16.15 6.28 17 5 17c-1.63 0-3-1.37-3-3s1.37-3 3-3c1.28 0 2.4.85 2.82 2H5v2h2.82zM19 17c-1.66 0-3-1.34-3-3s1.34-3 3-3 3 1.34 3 3-1.34 3-3 3z" />
      ) : (
        <>
          <Circle cx={5} cy={17} r={3} {...st} />
          <Circle cx={19} cy={17} r={3} {...st} />
          <Path d="M8 17h3.5l1.8-4.5L15 7h2.5l2 2.7M5.5 9.5H9l3.5 3.5M17 7l-1.2-2H13" {...st} />
        </>
      );
      break;
    case "auto": // auto-rickshaw — custom glyph on the same 24px grid (doc 03)
      body = (
        <>
          <Path d="M6 13a6 5 0 0 1 12 0" {...st} fill={filled ? color : "none"} />
          <Rect x={4} y={13} width={16} height={5} rx={1.5} {...st} fill={filled ? color : "none"} />
          <Circle cx={7.5} cy={19.5} r={1.6} fill={color} />
          <Circle cx={16.5} cy={19.5} r={1.6} fill={color} />
        </>
      );
      break;
    case "erick": // e-rickshaw — squarer canopy
      body = (
        <>
          <Path d="M6 13V9a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v4" {...st} fill={filled ? color : "none"} />
          <Rect x={4} y={13} width={16} height={5} rx={1.5} {...st} fill={filled ? color : "none"} />
          <Circle cx={7.5} cy={19.5} r={1.6} fill={color} />
          <Circle cx={16.5} cy={19.5} r={1.6} fill={color} />
        </>
      );
      break;
    case "car":
      body = filled ? (
        <Path fill={color} d="M18.92 6.01C18.72 5.42 18.16 5 17.5 5h-11c-.66 0-1.21.42-1.42 1.01L3 12v8c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1h12v1c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-8l-2.08-5.99zM6.5 16c-.83 0-1.5-.67-1.5-1.5S5.67 13 6.5 13s1.5.67 1.5 1.5S7.33 16 6.5 16zm11 0c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zM5 11l1.5-4.5h11L19 11H5z" />
      ) : (
        <>
          <Path d="M7 12 9.5 7h5L17 12" {...st} />
          <Rect x={3.5} y={12} width={17} height={5.5} rx={2} {...st} />
          <Circle cx={8} cy={19} r={1.7} {...st} />
          <Circle cx={16} cy={19} r={1.7} {...st} />
        </>
      );
      break;
    case "cab": // car + taxi dome
      body = filled ? (
        <Path fill={color} d="M18.92 6.01C18.72 5.42 18.16 5 17.5 5H15V3H9v2H6.5c-.66 0-1.21.42-1.42 1.01L3 12v8c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1h12v1c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-8l-2.08-5.99zM6.5 16c-.83 0-1.5-.67-1.5-1.5S5.67 13 6.5 13s1.5.67 1.5 1.5S7.33 16 6.5 16zm11 0c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zM5 11l1.5-4.5h11L19 11H5z" />
      ) : (
        <>
          <Rect x={10.5} y={5.5} width={3} height={1.8} rx={0.5} {...st} strokeWidth={1.5} />
          <Path d="M7 12 9.5 8h5L17 12" {...st} />
          <Rect x={3.5} y={12} width={17} height={5.5} rx={2} {...st} />
          <Circle cx={8} cy={19} r={1.7} {...st} />
          <Circle cx={16} cy={19} r={1.7} {...st} />
        </>
      );
      break;
    case "bus":
      body = filled ? (
        <Path fill={color} d="M4 16c0 .88.39 1.67 1 2.22V20c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1h8v1c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1.78c.61-.55 1-1.34 1-2.22V6c0-3.5-3.58-4-8-4s-8 .5-8 4v10zm3.5 1c-.83 0-1.5-.67-1.5-1.5S6.67 14 7.5 14s1.5.67 1.5 1.5S8.33 17 7.5 17zm9 0c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zm1.5-6H6V6h12v5z" />
      ) : (
        <>
          <Rect x={5} y={4.5} width={14} height={13} rx={2.5} {...st} />
          <Line x1={5} y1={11} x2={19} y2={11} {...st} />
          <Circle cx={8.5} cy={19} r={1.5} fill={color} />
          <Circle cx={15.5} cy={19} r={1.5} fill={color} />
        </>
      );
      break;
    case "metro": // front view — rounded car, window bar, underframe
      body = filled ? (
        <Path fill={color} d="M12 2c-4.42 0-8 .5-8 4v9.5C4 17.43 5.57 19 7.5 19L6 20.5v.5h12v-.5L16.5 19c1.93 0 3.5-1.57 3.5-3.5V6c0-3.5-3.58-4-8-4zM7.5 17c-.83 0-1.5-.67-1.5-1.5S6.67 14 7.5 14s1.5.67 1.5 1.5S8.33 17 7.5 17zM11 11H6V6h5v5zm5.5 6c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zM18 11h-5V6h5v5z" />
      ) : (
        <>
          <Rect x={6} y={3.5} width={12} height={14} rx={3.5} {...st} />
          <Line x1={6} y1={8} x2={18} y2={8} {...st} />
          <Line x1={12} y1={8} x2={12} y2={17.5} {...st} />
          <Path d="M9.5 17.5 7.5 22M14.5 17.5 16.5 22" {...st} />
        </>
      );
      break;

    /* ------------------------------------------------ chrome */
    case "menu":
      body = <Path d="M3.5 6.5h17M3.5 12h17M3.5 17.5h17" {...st} />;
      break;
    case "locate": // my_location
      body = filled ? (
        <Path fill={color} d="M12 8c-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4-1.79-4-4-4zm8.94 3c-.46-4.17-3.77-7.48-7.94-7.94V1h-2v2.06C6.83 3.52 3.52 6.83 3.06 11H1v2h2.06c.46 4.17 3.77 7.48 7.94 7.94V23h2v-2.06c4.17-.46 7.48-3.77 7.94-7.94H23v-2h-2.06zM12 19c-3.87 0-7-3.13-7-7s3.13-7 7-7 7 3.13 7 7-3.13 7-7 7z" />
      ) : (
        <>
          <Circle cx={12} cy={12} r={3.2} {...st} />
          <Circle cx={12} cy={12} r={8} {...st} />
          <Path d="M12 2.5v2.5M12 19v2.5M2.5 12h2.5M19 12h2.5" {...st} />
        </>
      );
      break;
    case "layers":
      body = filled ? (
        <Path fill={color} d="M11.99 18.54l-7.37-5.73L3 14.07l9 7 9-7-1.63-1.27-7.38 5.74zM12 16l7.36-5.73L21 9l-9-7-9 7 1.63 1.27L12 16z" />
      ) : (
        <>
          <Path d="M12 3.5 20.5 9 12 14.5 3.5 9 12 3.5z" {...st} />
          <Path d="M4.2 13.2 12 18.2l7.8-5" {...st} />
        </>
      );
      break;
    case "search":
      body = filled ? (
        <Path fill={color} d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z" />
      ) : (
        <>
          <Circle cx={10.5} cy={10.5} r={6.5} {...st} />
          <Path d="M15.3 15.3 20 20" {...st} />
        </>
      );
      break;
    case "pin": // place
      body = filled ? (
        <Path fill={color} d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z" />
      ) : (
        <>
          <Path d="M12 21.5s-6.8-6.4-6.8-11.3a6.8 6.8 0 0 1 13.6 0c0 4.9-6.8 11.3-6.8 11.3z" {...st} />
          <Circle cx={12} cy={10} r={2.4} {...st} />
        </>
      );
      break;
    case "chevron":
      body = <Path d="M9 5.5 15.5 12 9 18.5" {...st} />;
      break;
    case "share":
      body = filled ? (
        <Path fill={color} d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47-.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81 1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9c-1.66 0-3 1.34-3 3s1.34 3 3 3c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.61 1.31 2.92 2.92 2.92 1.61 0 2.92-1.31 2.92-2.92s-1.31-2.92-2.92-2.92z" />
      ) : (
        <>
          <Circle cx={18} cy={5.5} r={2.5} {...st} />
          <Circle cx={18} cy={18.5} r={2.5} {...st} />
          <Circle cx={6} cy={12} r={2.5} {...st} />
          <Path d="M8.2 10.8l7.6-4M8.2 13.2l7.6 4" {...st} />
        </>
      );
      break;
    case "star":
      body = filled ? (
        <Path fill={color} d="M12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z" />
      ) : (
        <Path d="M12 4l2.4 4.9 5.4.8-3.9 3.8.9 5.4-4.8-2.5-4.8 2.5.9-5.4L4.2 9.7l5.4-.8L12 4z" {...st} />
      );
      break;
    case "home":
      body = filled ? (
        <Path fill={color} d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z" />
      ) : (
        <Path d="M4.5 11.5 12 4.5l7.5 7M6.5 9.5V20h11V9.5M10 20v-5h4v5" {...st} />
      );
      break;
    case "work":
      body = filled ? (
        <Path fill={color} d="M20 6h-4V4c0-1.11-.89-2-2-2h-4c-1.11 0-2 .89-2 2v2H4c-1.11 0-1.99.89-1.99 2L2 19c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V8c0-1.11-.89-2-2-2zm-6 0h-4V4h4v2z" />
      ) : (
        <>
          <Rect x={3.5} y={7.5} width={17} height={12} rx={2} {...st} />
          <Path d="M9 7.5V6a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v1.5M3.5 12.5h17" {...st} />
        </>
      );
      break;
    case "trash":
      body = filled ? (
        <Path fill={color} d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" />
      ) : (
        <Path d="M5 6.5h14M9.5 6.5v-2h5v2M7 6.5l.9 13.5h8.2L17 6.5M10 10v6M14 10v6" {...st} />
      );
      break;
    case "info":
      body = filled ? (
        <Path fill={color} d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z" />
      ) : (
        <>
          <Circle cx={12} cy={12} r={9} {...st} />
          <Path d="M12 11v6" {...st} />
          <Circle cx={12} cy={7.6} r={1.1} fill={color} />
        </>
      );
      break;
    case "warn": // warning — rounded-corner triangle + exclamation
      body = filled ? (
        <Path fill={color} d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z" />
      ) : (
        <>
          <Path d="M12 4 20.5 19.5H3.5L12 4z" {...st} />
          <Path d="M12 9.8v4.4" {...st} />
          <Circle cx={12} cy={16.8} r={1.1} fill={color} />
        </>
      );
      break;
    case "close":
      body = <Path d="M6 6l12 12M18 6 6 18" {...st} />;
      break;
    case "clock":
      body = filled ? (
        <Path fill={color} d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67V7z" />
      ) : (
        <>
          <Circle cx={12} cy={12} r={8.5} {...st} />
          <Path d="M12 7v5l3.5 2" {...st} />
        </>
      );
      break;
    case "bell":
      body = filled ? (
        <Path fill={color} d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.89 2 2 2zm6-6v-5c0-3.07-1.64-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z" />
      ) : (
        <>
          <Path d="M6 16.5v-5a6 6 0 0 1 12 0v5l1.5 2.5h-15z" {...st} />
          <Path d="M10.3 20.5a1.9 1.9 0 0 0 3.4 0" {...st} />
        </>
      );
      break;
    case "flag":
      body = filled ? (
        <Path fill={color} d="M14.4 6 14 4H5v17h2v-7h5.6l.4 2h7V6z" />
      ) : (
        <>
          <Line x1={6} y1={3} x2={6} y2={21} {...st} />
          <Path d="M6 4.5h10.5l-2.5 3.5 2.5 3.5H6" {...st} />
        </>
      );
      break;

    /* ------------------------------------------------ units + hazards */
    case "cigarette": // the dose unit — burning tip + filter
      body = (
        <>
          <Rect x={4} y={10} width={13} height={4} rx={0.5} {...st} fill={filled ? color : "none"} />
          <Rect x={17} y={10} width={3.5} height={4} {...st} fill={filled ? color : "none"} />
          <Path d="M6 10c-1-2 1-3 0-5M9 10c-1-2 1-3 0-5" {...st} />
        </>
      );
      break;
    case "dust": // dust swirl — 3 curled gusts
      body = (
        <>
          <Path d="M3 8h11a2.5 2.5 0 1 0-2.5-2.5" {...st} />
          <Path d="M3 12h14a2.5 2.5 0 1 1-2.5 2.5" {...st} />
          <Path d="M3 16h9a2.5 2.5 0 1 1-2.5 2.5" {...st} />
        </>
      );
      break;
    case "smoke": // smoke plume
      body = (
        <>
          <Path d="M12 21c-3-2-4-4-2.5-6S8 11 10 9.5 9.5 6 12 3" {...st} />
          <Path d="M12 21c3-2 4-4 2.5-6" {...st} />
        </>
      );
      break;
    case "flame":
      body = filled ? (
        <Path fill={color} d="M13.5.67s.74 2.65.74 4.8c0 2.06-1.35 3.73-3.41 3.73-2.07 0-3.63-1.67-3.63-3.73l.03-.36C5.21 7.51 4 10.62 4 14c0 4.42 3.58 8 8 8s8-3.58 8-8C20 8.61 17.41 3.8 13.5.67zM11.71 19c-1.78 0-3.22-1.4-3.22-3.14 0-1.62 1.05-2.76 2.81-3.12 1.77-.36 3.6-1.21 4.62-2.58.39 1.29.59 2.65.59 4.04 0 2.65-2.15 4.8-4.8 4.8z" />
      ) : (
        <Path d="M12 3c1 3-1 4-1 7 0 0-3-1-3-4-3 2-4 5-4 8a8 8 0 0 0 16 0c0-4-4-9-8-11z" {...st} />
      );
      break;
    case "leaf":
      body = filled ? (
        <Path fill={color} d="M6.05 8.05c-2.73 2.73-2.73 7.15-.02 9.88 1.47-3.4 4.09-6.24 7.36-7.93-2.77 2.34-4.71 5.61-5.39 9.32 2.6 1.23 5.8.78 7.95-1.37C19.43 14.47 20 4 20 4S9.53 4.57 6.05 8.05z" />
      ) : (
        <>
          <Path d="M5 19C5 9 11 4 20 4c0 9-5 15-15 15z" {...st} />
          <Path d="M5 19C9 15 13 11 17 7" {...st} />
        </>
      );
      break;
    case "wind":
      body = (
        <>
          <Path d="M3 8h10a2.5 2.5 0 1 0-2.5-2.5" {...st} />
          <Path d="M3 12h14a2.5 2.5 0 1 1-2.5 2.5" {...st} />
          <Path d="M3 16h7" {...st} />
        </>
      );
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

/** Report kind → glyph (ReportsLayer reads community report markers). */
export function reportGlyph(kind: string): Glyph {
  switch (kind) {
    case "dust": return "dust";
    case "smoke": return "smoke";
    case "burning": return "flame";
    case "clean": return "leaf";
    default: return "flag";
  }
}
