// The first-breath moment (docs/lanes/welcome-loading.md) — a one-time
// cinematic that plays on the first launch, once, then `welcome_seen_v1`
// is on disk forever. Register: the projector-room half of the product's
// own register — near-black canvas (the ONE place dark is allowed),
// mono digits doing the work, colour only where it means air (the band).
//
// Beats (≤4.4s, tap anywhere to skip, never repeats):
//   1. a field of faint mono digits flipping like a film strip while the
//      app is already fetching the real number — "reading delhi's air…"
//   2. the digits resolve into the city's live PM2.5 field mean
//   3. the same number takes its CPCB band colour + the band's own word,
//      with the honest provenance line under it
//   out → onboarding (first install) or home (everyone else)
//
// Honesty contract: the number is real or absent — /v2/city's live field
// mean, else the app's own ambient /aqi read (already fetched at boot),
// else the type-only frame ("no live air reading right now"). Never a
// fake figure. Reduce-motion → one static frame, no flipping, same words.
//
// Mount only while `visible` — the parent drops it after onDone.

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Animated, BackHandler, Pressable, StyleSheet, Text, View,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import {
  bandColorIdx, bandIdx, famMono, famMonoText, famSerif,
  NUM, V2Type,
} from "../theme";
import { t, type Lang } from "../i18n/strings";
import { DYNAMIC_TYPE, useReduceMotion } from "../a11y";
import { API, fetchJson } from "../components/shell/net";
import { tick } from "../haptics";

/* the projector canvas — near-black, not the app's ink; one warm step off
   true black so the band hue still reads as muted, never neon */
const ROOM = "#0E1013";
const PAPER = "#F2F0E9";                    // type ink on the dark canvas
const DIM = "rgba(242,240,233,0.42)";       // eyebrow / provenance ink
const FAINT = "rgba(242,240,233,0.10)";     // the digit field
const HAIR = "rgba(242,240,233,0.16)";      // corner frame marks

/* the digit field — deterministic per (frame,row) so a flip reads as the
   next frame of the same instrument, not random snow */
const DIGITS = "0123456789";
function digitRow(len: number, seed: number): string {
  let s = "";
  for (let i = 0; i < len; i++) {
    s += DIGITS[(seed * 31 + i * 17 + i * i) % 10];
  }
  return s;
}

const BAND_WORD = [
  "band_good", "band_satisfactory", "band_moderate",
  "band_poor", "band_veryPoor", "band_severe",
] as const;

type FieldNum = { v: number; src: "city" | "ambient" } | null;

function WelcomeFilm({
  lang, ambientUg, onDone,
}: {
  lang: Lang;
  ambientUg: number | null;
  onDone: () => void;
}) {
  const insets = useSafeAreaInsets();
  const reduceMotion = useReduceMotion();
  const done = useRef(false);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  /* ambientUg can land mid-film (the boot /aqi poll) — read the latest,
     not the mount-time capture; same for onDone (the parent passes a
     fresh closure every render). Refs update inside an effect —
     render-time ref writes are a react-hooks/refs error on this stack */
  const ambRef = useRef(ambientUg);
  const onDoneRef = useRef(onDone);
  useEffect(() => {
    ambRef.current = ambientUg;
    onDoneRef.current = onDone;
  }, [ambientUg, onDone]);

  /* lazy useState for Animated values — useRef(new …).current is a
     react-hooks/refs error on this stack */
  const [fade] = useState(() => new Animated.Value(0));   // whole overlay in
  const [num] = useState(() => new Animated.Value(0));    // the numeral beat
  const [meta] = useState(() => new Animated.Value(0));   // word + provenance
  const [out] = useState(() => new Animated.Value(1));    // exit dissolve
  const [cur] = useState(() => new Animated.Value(1));    // block cursor

  /* live number: undefined = still reading, null = honestly nothing to
     show, {v,src} = a real read landed */
  const [field, setField] = useState<FieldNum | undefined>(undefined);
  const [frame, setFrame] = useState(0);           // digit-strip counter
  const [pastMin, setPastMin] = useState(false);   // the search beat held
  const [resolved, setResolved] = useState(false); // digits → numeral
  const [banded, setBanded] = useState(false);     // the colour beat

  const later = (ms: number, f: () => void) =>
    timers.current.push(setTimeout(f, ms));

  /* one stable finish — reads only refs and mount-stable Animated
     values, so timers and the back handler can hold it without going
     stale when the parent re-renders */
  const finish = useCallback(() => {
    if (done.current) return;
    done.current = true;
    timers.current.forEach(clearTimeout);
    Animated.timing(out, { toValue: 0, duration: 220, useNativeDriver: true })
      .start(() => onDoneRef.current());
  }, [out]);

  /* hardware BACK skips like a tap — the welcome never traps */
  useEffect(() => {
    const sub = BackHandler.addEventListener("hardwareBackPress", () => {
      finish();
      return true;
    });
    return () => sub.remove();
  }, [finish]);

  /* the fetch: /v2/city's field mean is the city number; the app's own
     ambient /aqi read (already in flight from boot) is the honest
     fallback. A miss either way is a designed frame, not an error. */
  useEffect(() => {
    let live = true;
    const settle = (v: number | null, src: "city" | "ambient") =>
      v != null ? { v, src } : null;
    fetchJson(`${API}/v2/city`, 2400)
      .then((j) => {
        if (!live) return;
        const mean = j?.pm25_stats?.mean;
        setField(typeof mean === "number"
          ? { v: mean, src: "city" }
          : settle(ambRef.current, "ambient"));
      })
      .catch(() => {
        if (live) setField(settle(ambRef.current, "ambient"));
      });
    return () => { live = false; };
  }, []);

  /* the timeline — every beat cancellable via timers[]. The search phase
     resolves on data + a minimum hold (the film needs its beat), or at
     the 2100 ms deadline with whatever honesty allows. */
  useEffect(() => {
    const ts = timers.current;   /* cleanup closes over the array, not
                                    the ref (exhaustive-deps) */
    if (reduceMotion) {
      fade.setValue(1); num.setValue(1); meta.setValue(1);
      later(1400, () => setField((f) => f === undefined
        ? (ambRef.current != null ? { v: ambRef.current!, src: "ambient" } : null) : f));
      later(2600, finish);
      return () => ts.forEach(clearTimeout);
    }
    Animated.timing(fade, { toValue: 1, duration: 320, useNativeDriver: true }).start();
    /* the strip flip — 2 digit frames alternating ~5.5 fps (projector
       cadence, not a slot machine) */
    const flip = setInterval(() => setFrame((f) => f + 1), 180);
    later(900, () => setPastMin(true));
    later(2100, () => setField((f) => f === undefined
      ? (ambRef.current != null ? { v: ambRef.current!, src: "ambient" } : null) : f));
    later(3900, finish);
    return () => { clearInterval(flip); ts.forEach(clearTimeout); };
  }, [reduceMotion, fade, num, meta, finish]);

  /* resolve once the beat held AND the field answered — under
     reduce-motion the settle alone resolves (static frame, no hold) */
  useEffect(() => {
    if (resolved) return;
    if (field === undefined || (!pastMin && !reduceMotion)) return;
    const t = setTimeout(() => setResolved(true), 0);
    return () => clearTimeout(t);
  }, [field, pastMin, reduceMotion, resolved]);

  /* resolved → the numeral rises, the colour beat + provenance follow */
  useEffect(() => {
    if (!resolved) return;
    if (reduceMotion) {
      const t = setTimeout(() => setBanded(true), 0);
      return () => clearTimeout(t);
    }
    Animated.timing(num, { toValue: 1, duration: 300, useNativeDriver: true }).start();
    const t = setTimeout(() => {
      setBanded(true);   /* hard cut to band colour — snappy, not a tween */
      Animated.timing(meta, { toValue: 1, duration: 260, useNativeDriver: true }).start();
    }, 750);
    return () => clearTimeout(t);
  }, [resolved, reduceMotion, num, meta]);

  /* the blinking block cursor — the one ambient motion, ASCII-Magic
     grammar; reduce-motion holds it solid */
  useEffect(() => {
    if (reduceMotion) return;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(cur, { toValue: 0, duration: 60, useNativeDriver: true }),
        Animated.timing(cur, { toValue: 1, duration: 60, useNativeDriver: true }),
        Animated.delay(430),
      ]));
    loop.start();
    return () => loop.stop();
  }, [reduceMotion, cur]);

  const rise = useMemo(
    () => num.interpolate({ inputRange: [0, 1], outputRange: [8, 0] }),
    [num]);

  /* the number — real or nothing. bandIdx/bandColorIdx are the app's own
     CPCB ramp; the word is the product's own vocabulary (band_* keys) */
  const v = field?.v ?? null;
  const bi = bandIdx(v);
  const bandHex = bandColorIdx(bi);
  const word = bi != null ? t(BAND_WORD[bi], lang) : null;
  const prov = field?.src === "ambient"
    ? t("wel_provAmbient", lang)
    : t("wel_provCity", lang);
  const numeral = v != null
    ? (v >= 100 ? `${Math.round(v)}` : v.toFixed(1))
    : null;

  /* two alternating digit blocks — the strip flip; fixed at mount so a
     flip reads as the next frame, not a reshuffle mid-frame */
  const blocks = useMemo(
    () => [0, 1].map((k) =>
      Array.from({ length: 7 }, (_, r) => digitRow(30, r * 7 + k)).join("\n")),
    []);
  const fieldTxt = blocks[frame % blocks.length];

  return (
    <Animated.View style={[ss.root, { opacity: Animated.multiply(fade, out) }]}>
      <StatusBar style="light" />
      <Pressable
        style={StyleSheet.absoluteFill}
        onPress={() => { tick(); finish(); }}
        accessibilityRole="button"
        accessibilityLabel={`${t("onb_skip", lang)} — welcome`}
      >
        {/* hairline frame marks — the editor's corners, nothing else */}
        <View style={[ss.corner, ss.cTL, { top: insets.top + 18, left: 20 }]} />
        <View style={[ss.corner, ss.cTR, { top: insets.top + 18, right: 20 }]} />
        <View style={[ss.corner, ss.cBL, { bottom: insets.bottom + 18, left: 20 }]} />
        <View style={[ss.corner, ss.cBR, { bottom: insets.bottom + 18, right: 20 }]} />

        <View style={[ss.topRow, { top: insets.top + 30 }]}>
          <Text {...DYNAMIC_TYPE} style={[ss.dim, { fontFamily: famMono(lang, "med") }]}>
            ALIVE·108 — DELHI NCR
          </Text>
          <Text {...DYNAMIC_TYPE} style={[ss.dim, { fontFamily: famMonoText(lang, "reg") }]}>
            {t("onb_skip", lang)}
          </Text>
        </View>

        <View style={ss.stage}>
          {/* the digit field behind the numeral — dims once resolved */}
          <View style={StyleSheet.absoluteFill} pointerEvents="none">
            <View style={ss.digitsWrap}>
              <Text
                {...DYNAMIC_TYPE}
                style={[ss.digits, {
                  fontFamily: famMono(lang, "reg"),
                  opacity: resolved ? 0.4 : 1,
                }]}
              >
                {fieldTxt}
              </Text>
            </View>
          </View>

          <Animated.View style={{ opacity: num, transform: [{ translateY: rise }] }}>
            {numeral != null ? (
              <>
                <Text
                  {...DYNAMIC_TYPE}
                  style={[ss.num, NUM, {
                    fontFamily: famSerif(lang, "light"),
                    color: banded && bandHex ? bandHex : PAPER,
                  }]}
                >
                  {numeral}
                  <Text style={{ fontFamily: famMono(lang, "reg"), fontSize: V2Type.label, letterSpacing: 1 }}>
                    {"  µg/m³"}
                  </Text>
                </Text>
                <Animated.Text
                  {...DYNAMIC_TYPE}
                  style={[ss.bandWord, {
                    fontFamily: famMonoText(lang, "med"),
                    opacity: meta,
                    color: banded && bandHex ? bandHex : PAPER,
                  }]}
                >
                  {`pm2.5 · ${word}`}
                </Animated.Text>
              </>
            ) : resolved ? (
              /* honest degrade — the type-only frame, no fake figure */
              <Text {...DYNAMIC_TYPE} style={[ss.noField, { fontFamily: famMonoText(lang, "reg") }]}>
                {t("cityNoField", lang)}
              </Text>
            ) : null}
          </Animated.View>

          <View style={ss.readRow}>
            <Text {...DYNAMIC_TYPE} style={[ss.dim, { fontFamily: famMonoText(lang, "reg") }]}>
              {resolved
                ? numeral != null ? prov : t("wel_neverFaked", lang)
                : t("cityLoading", lang)}
            </Text>
            <Animated.Text
              style={[ss.dim, { fontFamily: famMono(lang, "reg"), opacity: cur }]}
            >
              ▌
            </Animated.Text>
          </View>
        </View>

        <View style={[ss.footRow, { bottom: insets.bottom + 30 }]}>
          <Text {...DYNAMIC_TYPE} style={[ss.foot, { fontFamily: famMonoText(lang, "reg") }]}>
            {banded && numeral != null ? t("wel_thenBreathe", lang) : t("wel_delhiBreathes", lang)}
          </Text>
        </View>
      </Pressable>
    </Animated.View>
  );
}

function WelcomeScreenInner({
  visible, lang = "en", ambientUg = null, onDone,
}: {
  visible: boolean;
  lang?: Lang;
  ambientUg?: number | null;
  onDone: () => void;
}) {
  /* overlay, not Modal — same RN 0.86 native present/dismiss SIGSEGV
     guard as OnboardingScreen */
  if (!visible) return null;
  return (
    <View style={ss.backdrop}>
      <WelcomeFilm lang={lang} ambientUg={ambientUg} onDone={onDone} />
    </View>
  );
}

export const WelcomeScreen = React.memo(WelcomeScreenInner);
export default WelcomeScreen;

const ss = StyleSheet.create({
  /* elevation must beat every sheet's — Android dispatches sibling
     touches by z before mount order (the onboarding fix); iOS takes
     mount order. 40 clears HomeScreen's 24 and onboarding's 30. */
  backdrop: { ...StyleSheet.absoluteFill, elevation: 40, zIndex: 40 },
  root: { flex: 1, backgroundColor: ROOM },
  corner: { position: "absolute", width: 14, height: 14 },
  cTL: { borderTopWidth: 1, borderLeftWidth: 1, borderColor: HAIR },
  cTR: { borderTopWidth: 1, borderRightWidth: 1, borderColor: HAIR },
  cBL: { borderBottomWidth: 1, borderLeftWidth: 1, borderColor: HAIR },
  cBR: { borderBottomWidth: 1, borderRightWidth: 1, borderColor: HAIR },
  topRow: {
    position: "absolute", left: 30, right: 30,
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
  },
  dim: { fontSize: V2Type.micro, letterSpacing: 2.2, color: DIM },
  stage: { flex: 1, alignItems: "center", justifyContent: "center", paddingHorizontal: 30 },
  digitsWrap: { flex: 1, alignItems: "center", justifyContent: "center" },
  digits: {
    fontSize: V2Type.micro, lineHeight: 18, letterSpacing: 3.4,
    color: FAINT, textAlign: "center",
  },
  num: { fontSize: 96, color: PAPER, letterSpacing: -2, textAlign: "center" },
  bandWord: {
    marginTop: 14, fontSize: V2Type.label, letterSpacing: 2.6,
    textAlign: "center", textTransform: "uppercase",
  },
  noField: {
    fontSize: V2Type.body, letterSpacing: 0.6, color: PAPER,
    textAlign: "center",
  },
  readRow: {
    marginTop: 34, flexDirection: "row", alignItems: "center", gap: 6,
  },
  footRow: { position: "absolute", left: 30, right: 30, alignItems: "center" },
  foot: { fontSize: V2Type.micro - 1, letterSpacing: 2, color: DIM },
});
