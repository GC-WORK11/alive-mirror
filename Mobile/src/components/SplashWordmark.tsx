/* The launch wordmark (splash lane). 'a' lands alone, 'live' sweeps out
   of it letter by letter, the word holds a beat, then a 300 ms crossfade
   hands off to whatever the consent gate resolved to. App mounts it on
   the introSeen===false path only — a returning user never sees it
   replay. One calm motion, springs not tweens; OS reduce-motion collapses
   it to a static mark that leaves immediately.
   Paper is the native splash's own #FAFAF7 (app.json + V2T.bg), so the
   storyboard → JS handoff can't flash. */
import React, { useEffect, useState } from "react";
import { Animated, StyleSheet } from "react-native";
import { DYNAMIC_TYPE, useReduceMotion } from "../a11y";
import { FSERIF, V2T, V2Type } from "../theme";

/* 'alive' is a proper noun — verbatim in every language, same rule the
   onboarding wordmark follows (not a t() key). */
const LIVE = ["l", "i", "v", "e"] as const;
/* each glyph sweeps in from inside the 'a' — further letters travel
   further, so the word reads as growing out of the seed letter */
const SWEEP = [-12, -22, -32, -42] as const;
const HOLD_MS = 360;
const OUT_MS = 300;
/* the stagger beat between glyphs — keeps the whole assembly inside the
   ~700-900 ms window */
const STEP_MS = 75;
const START_MS = 220;

export function SplashWordmark({ onDone }: { onDone: () => void }) {
  const reduce = useReduceMotion();
  const [fade] = useState(() => new Animated.Value(1));
  const [aIn] = useState(() => new Animated.Value(0));
  const [live] = useState(() => LIVE.map(() => new Animated.Value(0)));

  useEffect(() => {
    if (reduce) {
      /* static 'alive', a beat, out — no motion at all */
      aIn.setValue(1);
      live.forEach((v) => v.setValue(1));
      const id = setTimeout(onDone, 240);
      return () => clearTimeout(id);
    }
    let holdId: ReturnType<typeof setTimeout> | undefined;
    let out: Animated.CompositeAnimation | undefined;
    const enter = Animated.parallel([
      Animated.spring(aIn, {
        toValue: 1, damping: 18, stiffness: 150, mass: 0.9,
        useNativeDriver: true,
      }),
      ...LIVE.map((_, i) => Animated.spring(live[i], {
        /* delay lives INSIDE the spring config — a sequence-wrapped
           Animated.delay runs a JS-driver timing that never hands the
           native spring across (letters stayed invisible though the
           composite reported finished) */
        toValue: 1, delay: START_MS + i * STEP_MS,
        damping: 15, stiffness: 165, mass: 0.85,
        useNativeDriver: true,
      })),
    ]);
    enter.start(({ finished }) => {
      if (!finished) return;
      holdId = setTimeout(() => {
        out = Animated.timing(fade, {
          toValue: 0, duration: OUT_MS, useNativeDriver: true,
        });
        out.start((r) => { if (r.finished) onDone(); });
      }, HOLD_MS);
    });
    return () => {
      enter.stop();
      out?.stop();
      if (holdId !== undefined) clearTimeout(holdId);
    };
  }, [reduce, aIn, live, fade, onDone]);

  return (
    <Animated.View
      style={[ss.root, { opacity: fade }]}
      accessible
      accessibilityLabel="Alive"
    >
      <Animated.Text
        {...DYNAMIC_TYPE}
        style={[ss.glyph, {
          fontFamily: FSERIF.med,
          opacity: aIn,
          transform: [
            { translateY: aIn.interpolate({ inputRange: [0, 1], outputRange: [12, 0] }) },
            { scale: aIn.interpolate({ inputRange: [0, 1], outputRange: [0.94, 1] }) },
          ],
        }]}
      >
        a
      </Animated.Text>
      {LIVE.map((ch, i) => (
        <Animated.Text
          key={ch}
          {...DYNAMIC_TYPE}
          style={[ss.glyph, {
            fontFamily: FSERIF.med,
            opacity: live[i],
            transform: [{
              translateX: live[i].interpolate({
                inputRange: [0, 1], outputRange: [SWEEP[i], 0],
              }),
            }],
          }]}
        >
          {ch}
        </Animated.Text>
      ))}
    </Animated.View>
  );
}

const ss = StyleSheet.create({
  root: {
    position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: V2T.bg,   // the native splash's own paper — no flash
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
  },
  glyph: {
    color: V2T.text,
    fontSize: V2Type.heroXL,
    letterSpacing: -0.5,
    lineHeight: V2Type.heroXL * 1.15,
  },
});
