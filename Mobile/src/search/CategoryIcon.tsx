// Row glyph for a gazetteer/server category. Reuses the app glyph set
// (src/icons.tsx) where it already names the thing — metro, bus, leaf,
// flame, pin — and draws the rest on the same 24×24, 2 px-round-stroke
// grid so every search row shows a category glyph (docs/plan/02 S2).
import React from "react";
import Svg, { Circle, Path, Rect } from "react-native-svg";
import { Icon, type Glyph } from "../icons";

// categories that already have a first-class glyph in the app set
const EXISTING: [RegExp, Glyph][] = [
  [/metro/, "metro"],
  [/bus|transit/, "bus"],
  [/train|railway/, "metro"],
  [/park|garden/, "leaf"],
  [/fire/, "flame"],
  [/landmark|monument|historic|museum|attraction|memorial/, "flag"],
];

function stroke(color: string) {
  return { stroke: color, strokeWidth: 2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, fill: "none" as const };
}

function Custom({ kind, color, size }: { kind: string; color: string; size: number }) {
  const p = stroke(color);
  let body: React.ReactNode;
  if (/restaurant|cafe|food|eatery|dhaba|bakery|bar|pub/.test(kind))
    // cup + saucer
    body = <>
      <Path d="M5 5h11v5a5 5 0 0 1-10 0V5z" {...p} />
      <Path d="M16 6h1.5a2.5 2.5 0 0 1 0 5H16M6 19h11" {...p} />
    </>;
  else if (/hospital|clinic|doctor|pharmacy|health|vet/.test(kind))
    body = <>
      <Rect x={4.5} y={4.5} width={15} height={15} rx={3.5} {...p} />
      <Path d="M12 9v6M9 12h6" {...p} />
    </>;
  else if (/mall|shop|market|store|bazaar|retail/.test(kind))
    body = <>
      <Path d="M6.5 8h11l-1.2 12.5a1.5 1.5 0 0 1-1.5 1.3H9.2a1.5 1.5 0 0 1-1.5-1.3L6.5 8z" {...p} />
      <Path d="M9.3 10V6.5a2.7 2.7 0 0 1 5.4 0V10" {...p} />
    </>;
  else if (/school|college|university|education|institute/.test(kind))
    body = <>
      <Path d="M12 5 3.5 9 12 13l8.5-4L12 5z" {...p} />
      <Path d="M7.2 10.8V15c0 1.4 2.2 2.5 4.8 2.5s4.8-1.1 4.8-2.5v-4.2M20.5 9v5" {...p} />
    </>;
  else if (/airport|airfield|airstrip/.test(kind))
    body = <Path d="M12 3.5v7l-8 4.5v1.8l8-2v4.4l-1.6 1.4v1.4l1.6-.8 1.6.8v-1.4L12 19.2v-4.4l8 2V15l-8-4.5v-7z" {...p} />;
  else if (/worship|temple|mosque|gurudwara|gurdwara|church|shrine|mandir|masjid|dargah/.test(kind))
    body = <>
      <Path d="M12 2.5V5" {...p} />
      <Path d="M6.5 21v-6.5a5.5 5.5 0 0 1 11 0V21" {...p} />
      <Path d="M4 21h16" {...p} />
    </>;
  else if (/bank|atm|finance|credit/.test(kind))
    body = <>
      <Path d="M4 9.5 12 4.5l8 5" {...p} />
      <Path d="M5.5 10.5v7M10 10.5v7M14 10.5v7M18.5 10.5v7M3.5 20.5h17" {...p} />
    </>;
  else if (/hotel|lodge|guest|resort|hostel|inn|stay/.test(kind))
    body = <>
      <Path d="M4.5 19.5v-13M4.5 15.5h15v4" {...p} />
      <Path d="M4.5 12.5h7a4 4 0 0 1 4 3" {...p} />
      <Circle cx={7.6} cy={9.8} r={1.6} {...p} />
    </>;
  else if (/cinema|movie|theater|theatre|multiplex/.test(kind))
    body = <>
      <Rect x={4} y={5.5} width={16} height={13} rx={2.5} {...p} />
      <Path d="M10.3 9.5v5l4.5-2.5-4.5-2.5z" {...p} />
    </>;
  else if (/stadium|arena|sports|playground|ground/.test(kind))
    body = <>
      <Circle cx={12} cy={12} r={8.5} {...p} />
      <Path d="M4.5 9.5h15M4.5 14.5h15" {...p} />
    </>;
  else if (/fuel|petrol|gas_station|charging/.test(kind))
    body = <>
      <Rect x={5.5} y={4} width={8} height={16.5} rx={1} {...p} />
      <Path d="M8 7h3v3.5H8zM13.5 11.5h1.5a2 2 0 0 1 2 2v3.2a1.4 1.4 0 0 0 2.8 0V10l-2.5-2.5" {...p} />
    </>;
  else if (/police|security/.test(kind))
    body = <Path d="M12 3 19 6v5.5c0 4.3-2.9 7.6-7 9.5-4.1-1.9-7-5.2-7-9.5V6l7-3z" {...p} />;
  else if (/gym|fitness/.test(kind))
    body = <Path d="M4.5 9.5v5M8 7v10M16 7v10M19.5 9.5v5M8 12h8" {...p} />;
  else if (/office|business|cowork/.test(kind))
    body = <>
      <Rect x={6} y={4} width={12} height={17} rx={1} {...p} />
      <Path d="M9.5 8h1.6M12.9 8h1.6M9.5 11.5h1.6M12.9 11.5h1.6M9.5 15h1.6M12.9 15h1.6M10.5 21v-2.8h3V21" {...p} />
    </>;
  else if (/bridge|flyover|tunnel/.test(kind))
    body = <>
      <Path d="M3.5 18.5h17M5 18.5v-3a7 7 0 0 1 14 0v3" {...p} />
      <Path d="M3.5 9h17" {...p} />
    </>;
  else
    // generic locality/POI — same pin as the app glyph set
    return <Icon name="pin" color={color} size={size} />;
  return <Svg width={size} height={size} viewBox="0 0 24 24">{body}</Svg>;
}

export function categoryGlyph(kind: string | undefined, color: string, size = 22): React.ReactNode {
  const k = (kind ?? "").toLowerCase().replace(/_/g, " ");
  for (const [re, glyph] of EXISTING) if (re.test(k)) return <Icon name={glyph} color={color} size={size} />;
  return <Custom kind={k} color={color} size={size} />;
}
