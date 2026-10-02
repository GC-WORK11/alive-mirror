import React, { useEffect, useState } from "react";
import {
  Animated, Pressable, ScrollView, StyleSheet, Text, View,
} from "react-native";
import { F, T, doseColor } from "../theme";
import type { Trip } from "../store/ledger";

type Stats = {
  todayUg: number; avoidedUg: number; allAvoidedUg: number;
  cigEq: number; budgetUg: number; budgetPct: number;
  streak: number; today: Trip[];
};

type Props = {
  stats: Stats;
  curve: number[] | null;
  hourNow: number | null;
  onClose: () => void;
};

function Sparkline({ curve, hourNow }: { curve: number[]; hourNow: number | null }) {
  const max = Math.max(...curve, 1);
  return (
    <View style={s.spark}>
      {curve.map((v, h) => (
        <View key={h} style={[s.bar, {
          height: Math.max(3, (v / max) * 56),
          backgroundColor: h === hourNow ? T.accent : "rgba(255,255,255,0.22)",
        }]} />
      ))}
    </View>
  );
}

/** The Lung Ledger — today's inhaled PM2.5 against a WHO-derived
 * daily budget, plus what you avoided and the decade curve. */
export function LedgerSheet({ stats, curve, hourNow, onClose }: Props) {
  const [rise] = useState(() => new Animated.Value(320));
  useEffect(() => {
    Animated.spring(rise, { toValue: 0, useNativeDriver: true, damping: 22, stiffness: 200 }).start();
  }, [rise]);

  const pct = Math.min(100, stats.budgetPct);
  return (
    <Animated.View style={[s.sheet, { transform: [{ translateY: rise }] }]}>
      <View style={s.grab} />
      <View style={s.row}>
        <Text style={s.big}>
          {stats.todayUg}
          <Text style={s.unit}> µg</Text>
        </Text>
        <View style={{ alignItems: "flex-end" }}>
          <Text style={s.sub}>inhaled today</Text>
          <Text style={s.sub}>{stats.cigEq} cig-equiv</Text>
        </View>
      </View>

      <View style={s.budgetWrap}>
        <View style={[s.budgetFill, { width: `${pct}%`,
          backgroundColor: stats.budgetPct > 100 ? T.doseHigh : T.accent }]} />
      </View>
      <Text style={s.sub}>
        {stats.budgetPct}% of the ~{stats.budgetUg} µg daily budget
        {stats.streak > 0 ? `  ·  ${stats.streak}d under` : ""}
      </Text>

      <View style={s.row2}>
        <Text style={s.sub}>avoided today {stats.avoidedUg} µg</Text>
        <Text style={s.sub}>all time {stats.allAvoidedUg} µg</Text>
      </View>

      {curve ? (
        <View>
          <Sparkline curve={curve} hourNow={hourNow} />
          <Text style={s.sparkLabel}>typical this month · IST hours · decade of stations</Text>
        </View>
      ) : null}

      <ScrollView style={{ maxHeight: 120 }}>
        {stats.today.map((t, i) => (
          <View key={i} style={s.trip}>
            <Text style={s.tripTxt} numberOfLines={1}>
              {t.label} · {t.from} → {t.to}
            </Text>
            <Text style={[s.tripDose, { color: doseColor(t.dose_ug) }]}>{t.dose_ug} µg</Text>
          </View>
        ))}
        {stats.today.length === 0 && (
          <Text style={s.sub}>pick a route — it lands here</Text>
        )}
      </ScrollView>

      <Pressable onPress={onClose}><Text style={s.close}>close</Text></Pressable>
    </Animated.View>
  );
}

const s = StyleSheet.create({
  sheet: {
    position: "absolute", left: 10, right: 10, bottom: 10,
    backgroundColor: "rgba(11,14,17,1.0)",
    borderRadius: 20, padding: 16,
    borderWidth: 1, borderColor: T.glassBorder,
    shadowColor: "#000", shadowOpacity: 0.12, shadowRadius: 18, shadowOffset: { width: 0, height: 6 },
  },
  grab: { width: 36, height: 4, borderRadius: 2, backgroundColor: "#d6d3d1", alignSelf: "center", marginBottom: 10 },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-end" },
  row2: { flexDirection: "row", justifyContent: "space-between", marginTop: 8 },
  big: { fontFamily: F.semi, fontSize: 44, color: T.ink, lineHeight: 48 },
  unit: { fontFamily: F.reg, fontSize: 18, color: T.ink3 },
  sub: { fontFamily: F.reg, fontSize: 12, color: T.ink2, marginTop: 4 },
  budgetWrap: { height: 6, borderRadius: 3, backgroundColor: "rgba(255,255,255,0.12)", marginTop: 12, overflow: "hidden" },
  budgetFill: { height: 6, borderRadius: 3 },
  spark: { flexDirection: "row", alignItems: "flex-end", height: 56, marginTop: 14, gap: 2 },
  bar: { flex: 1, borderRadius: 1 },
  sparkLabel: { fontFamily: F.reg, fontSize: 10, color: T.ink3, marginTop: 4 },
  trip: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 6 },
  tripTxt: { fontFamily: F.reg, fontSize: 13, color: T.ink, flex: 1, marginRight: 8 },
  tripDose: { fontFamily: F.semi, fontSize: 13 },
  close: { fontFamily: F.med, fontSize: 13, color: T.ink3, textAlign: "center", marginTop: 10 },
});
