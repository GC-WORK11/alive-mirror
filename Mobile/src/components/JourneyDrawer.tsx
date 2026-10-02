import React, { useEffect, useState } from "react";
import { Animated, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { T, F, doseColor } from "../theme";
import type { CommunityTotals } from "../community";
import type { weekStats, stats as ledgerStats } from "../store/ledger";

type EscapeSpot = { name?: string; pm25: number; pct_less_than_here?: number };

type Props = {
  week: ReturnType<typeof weekStats>;
  stats: ReturnType<typeof ledgerStats>;
  community: CommunityTotals | null;
  shiftCig: number | null;
  escape?: EscapeSpot | null;
  onClose: () => void;
};

const timeAgo = (ts: number) => {
  const m = Math.max(0, Math.round((Date.now() - ts) / 60000));
  if (m < 1) return "now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
};

/** Journey drawer — your week, your trips, and what they gave Delhi. */
export function JourneyDrawer({ week, stats, community, shiftCig, escape, onClose }: Props) {
  const [slide] = useState(() => new Animated.Value(-340));
  useEffect(() => {
    Animated.spring(slide, { toValue: 0, useNativeDriver: true, damping: 24, stiffness: 220 }).start();
  }, [slide]);

  const maxUg = Math.max(...week.days.map((d) => d.ug), 1);
  return (
    <>
      <Pressable style={s.scrim} onPress={onClose} />
      <Animated.View style={[s.drawer, { transform: [{ translateX: slide }] }]}>
        <Text style={s.title}>your journeys</Text>
        <Text style={s.sub}>
          ALive-108 shows how much pollution you actually breathe on
          every trip — and turns your journeys into a shared air map
          for Delhi.
        </Text>

        <View style={s.cards}>
          <View style={s.card}>
            <Text style={s.cardNum}>{stats.todayUg}</Text>
            <Text style={s.cardLbl}>µg breathed{"\n"}today</Text>
          </View>
          <View style={s.card}>
            <Text style={s.cardNum}>{stats.cigEq}</Text>
            <Text style={s.cardLbl}>≈ cigarettes{"\n"}today</Text>
          </View>
          <View style={s.card}>
            <Text style={[s.cardNum, { color: T.accent }]}>{stats.avoidedUg}</Text>
            <Text style={s.cardLbl}>µg you{"\n"}avoided</Text>
          </View>
        </View>
        {stats.streak > 0 && (
          <Text style={s.streak}>{stats.streak}-day streak under the daily budget</Text>
        )}

        <Text style={s.section}>this week</Text>
        <View style={s.weekRow}>
          {week.days.map((d, i) => (
            <View key={i} style={s.dayCol}>
              {d.ug > 0 && <Text style={s.dayVal}>{Math.round(d.ug)}</Text>}
              <View style={s.dayBarWrap}>
                <View style={[s.dayBar, {
                  height: Math.max(2, (d.ug / maxUg) * 64),
                  backgroundColor: doseColor(d.ug > 0 ? 90 : undefined),
                  opacity: d.ug === 0 ? 0.15 : 1,
                }]} />
              </View>
              <Text style={s.dayLabel}>{d.label}</Text>
            </View>
          ))}
        </View>

        <Text style={s.section}>{"today's trips"}</Text>
        <ScrollView style={s.trips} showsVerticalScrollIndicator={false}>
          {stats.today.length === 0 && (
            <Text style={s.sub}>no journeys yet — pick a route on the map</Text>
          )}
          {stats.today.map((t, i) => (
            <View key={i} style={s.trip}>
              <View style={{ flex: 1, marginRight: 8 }}>
                <Text style={s.tripTxt} numberOfLines={1}>
                  {t.label} · {t.from} → {t.to}
                </Text>
                <Text style={s.tripMeta}>{timeAgo(t.ts)}</Text>
              </View>
              <Text style={[s.tripDose, { color: doseColor(t.dose_ug > 25 ? 130 : 40) }]}>
                {t.dose_ug} µg
              </Text>
            </View>
          ))}
        </ScrollView>

        {shiftCig != null && (
          <View style={s.city}>
            <Text style={s.section}>{"delhi's working lungs"}</Text>
            <Text style={s.cityText}>
              {"an 8-hr shift on a two-wheeler in this air ≈ "}{shiftCig}{" cigarettes —\n"}
              {"the daily price delhi's delivery and cab drivers pay\n"}
              {"to keep the city moving."}
            </Text>
          </View>
        )}

        {escape && (
          <View style={s.city}>
            <Text style={s.section}>{"breathe easiest right now"}</Text>
            <Text style={s.cityText}>
              {escape.name ?? "nearby"}{" — "}{Math.round(escape.pm25)}{" µg/m³"}
              {escape.pct_less_than_here != null && escape.pct_less_than_here > 0
                ? `\n${escape.pct_less_than_here}% less than here`
                : ""}
            </Text>
          </View>
        )}

        {community && (
          <View style={s.city}>
            <Text style={s.section}>what you gave delhi</Text>
            <Text style={s.sub}>
              every trip joins a shared air map built by people like you —
              {community.contributors} contributors logged {community.km_24h} km
              today, avoiding {community.avoided_ug_24h} µg of pollution together.
            </Text>
            <Text style={s.sub}>
              {community.active_reports > 0
                ? `${community.active_reports} air reports live on the map`
                : "spot dust, smoke or clean air? flag it with the ◍ button"}
            </Text>
          </View>
        )}

        <Pressable onPress={onClose} style={({ pressed }) => pressed && { opacity: 0.5 }}>
          <Text style={s.close}>close</Text>
        </Pressable>
      </Animated.View>
    </>
  );
}

const s = StyleSheet.create({
  scrim: { position: "absolute", top: 0, bottom: 0, left: 0, right: 0, backgroundColor: "rgba(28,25,23,0.28)" },
  drawer: {
    position: "absolute", top: 0, bottom: 0, left: 0, width: 310,
    backgroundColor: "rgba(255,255,255,0.98)",
    paddingTop: 60, paddingHorizontal: 18,
    borderRightWidth: 1, borderColor: T.glassBorder,
    shadowColor: "#000", shadowOpacity: 0.14, shadowRadius: 24, shadowOffset: { width: 4, height: 0 },
  },
  title: { fontFamily: F.semi, fontSize: 22, color: T.ink },
  sub: { fontFamily: F.reg, fontSize: 12, color: T.ink2, marginTop: 6, lineHeight: 17 },
  section: { fontFamily: F.semi, fontSize: 11, color: T.ink3, marginTop: 20, letterSpacing: 1.2, textTransform: "uppercase" },
  cards: { flexDirection: "row", gap: 8, marginTop: 16 },
  card: {
    flex: 1, backgroundColor: "#fff", borderRadius: 14, paddingVertical: 10, paddingHorizontal: 8,
    borderWidth: 1, borderColor: T.glassBorder, alignItems: "center",
    shadowColor: "#000", shadowOpacity: 0.05, shadowRadius: 6, shadowOffset: { width: 0, height: 2 },
  },
  cardNum: { fontFamily: F.semi, fontSize: 19, color: T.ink, fontVariant: ["tabular-nums"] },
  cardLbl: { fontFamily: F.reg, fontSize: 10, color: T.ink3, marginTop: 3, textAlign: "center", lineHeight: 13 },
  streak: { fontFamily: F.med, fontSize: 11.5, color: T.accent, marginTop: 10 },
  weekRow: { flexDirection: "row", marginTop: 10, alignItems: "flex-end" },
  dayCol: { flex: 1, alignItems: "center" },
  dayVal: { fontFamily: F.med, fontSize: 9, color: T.ink2, marginBottom: 2 },
  dayBarWrap: { height: 64, justifyContent: "flex-end" },
  dayBar: { width: 16, borderRadius: 5, backgroundColor: T.doseLow },
  dayLabel: { fontFamily: F.reg, fontSize: 10, color: T.ink3, marginTop: 5 },
  trips: { maxHeight: 230, marginTop: 4 },
  trip: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    paddingVertical: 9, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: T.glassBorder,
  },
  tripTxt: { fontFamily: F.reg, fontSize: 12.5, color: T.ink },
  tripMeta: { fontFamily: F.reg, fontSize: 10, color: T.ink3, marginTop: 2 },
  tripDose: { fontFamily: F.semi, fontSize: 12.5, fontVariant: ["tabular-nums"] },
  city: { marginTop: 2 },
  cityText: { fontFamily: "Outfit_400Regular", fontSize: 13.5, lineHeight: 19, color: T.ink2 },
  close: { fontFamily: F.med, fontSize: 13, color: T.ink2, textAlign: "center", marginTop: 16, marginBottom: 30 },
});
