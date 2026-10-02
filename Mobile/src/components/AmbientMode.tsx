import React, { useEffect, useState } from "react";
import { Animated, Pressable, StyleSheet, Text } from "react-native";
import { F, T } from "../theme";

type Props = {
  pm25: number | null;
  bestHourLabel: string | null;
  savedPct: number | null;
  locationName: string | null;
  onExit: () => void;
};

/** In-app ambient mode — the closest honest approximation of an
 * always-on display (true AOD is OS-rendered; docs/14 explains). */
export function AmbientMode({ pm25, bestHourLabel, savedPct, locationName, onExit }: Props) {
  const [now, setNow] = useState(new Date());
  const [pulse] = useState(() => new Animated.Value(0.35));

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 2000, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0.35, duration: 2000, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => {
      clearInterval(t);
      loop.stop();
    };
  }, [pulse]);

  const hh = String(now.getHours()).padStart(2, "0");
  const mm = String(now.getMinutes()).padStart(2, "0");

  return (
    <Pressable style={s.wrap} onPress={onExit}>
      <Text style={s.clock}>{hh}:{mm}</Text>
      <Text style={s.pm}>{pm25 != null ? Math.round(pm25) : "—"}</Text>
      <Text style={s.pmLabel}>µg/m³ PM2.5</Text>
      {bestHourLabel && savedPct != null ? (
        <Text style={s.best}>
          breathe least at {bestHourLabel} · −{savedPct}%
        </Text>
      ) : null}
      {locationName ? <Text style={s.loc}>{locationName}</Text> : null}
      <Animated.View style={[s.dot, { opacity: pulse }]} />
    </Pressable>
  );
}

const s = StyleSheet.create({
  wrap: {
    position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: T.ambient,
    alignItems: "center",
    justifyContent: "center",
    zIndex: 50,
  },
  clock: { fontFamily: F.light, fontSize: 84, color: "#e7e5e4", letterSpacing: 2 },
  pm: { fontFamily: F.semi, fontSize: 96, color: "#d6d3d1", marginTop: 24 },
  pmLabel: { fontFamily: F.reg, fontSize: 13, color: "#57534e", letterSpacing: 3, textTransform: "uppercase" },
  best: { fontFamily: F.med, fontSize: 15, color: T.accent, marginTop: 28 },
  loc: { fontFamily: F.reg, fontSize: 12, color: "#57534e", marginTop: 8, letterSpacing: 1 },
  dot: {
    width: 6, height: 6, borderRadius: 3, backgroundColor: T.accent,
    position: "absolute", bottom: 48,
  },
});
