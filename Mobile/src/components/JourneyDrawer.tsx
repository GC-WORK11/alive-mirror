import React, { useEffect, useState } from "react";
import { Animated, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { T, F, doseColor } from "../theme";
import type { CommunityTotals } from "../community";
import type { weekStats, Trip } from "../store/ledger";

type Props = {
  week: ReturnType<typeof weekStats>;
  today: Trip[];
  community: CommunityTotals | null;
  onClose: () => void;
};

/** Journey drawer — your week on the left, the city's on the bottom. */
export function JourneyDrawer({ week, today, community, onClose }: Props) {
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
          ALive-108 shows how much pollution you actually breathe on every trip —
          and turns your journeys into a shared air map for Delhi.
        </Text>
        <Text style={s.sub}>
          this week: {week.totalTrips} trips · {week.weekUg} µg breathed
          (about {week.weekCigEq} cigarettes)
          {week.weekAvoided > 0 ? ` · you avoided ${week.weekAvoided} µg` : ""}
        </Text>

        <View style={s.weekRow}>
          {week.days.map((d, i) => (
            <View key={i} style={s.dayCol}>
              <View style={s.dayBarWrap}>
                <View style={[s.dayBar, {
                  height: Math.max(2, (d.ug / maxUg) * 72),
                  backgroundColor: doseColor(d.ug > 0 ? 90 : undefined),
                  opacity: d.ug === 0 ? 0.15 : 1,
                }]} />
              </View>
              <Text style={s.dayLabel}>{d.label}</Text>
            </View>
          ))}
        </View>

        <Text style={s.section}>today</Text>
        <ScrollView style={s.trips} showsVerticalScrollIndicator={false}>
          {today.length === 0 && <Text style={s.sub}>no journeys yet — pick a route on the map</Text>}
          {today.map((t, i) => (
            <View key={i} style={s.trip}>
              <Text style={s.tripTxt} numberOfLines={1}>{t.label} · {t.from} → {t.to}</Text>
              <Text style={s.tripDose}>{t.dose_ug} µg</Text>
            </View>
          ))}
        </ScrollView>

        {community && (
          <View style={s.city}>
            <Text style={s.section}>what you gave delhi</Text>
            <Text style={s.sub}>
              every trip you take joins a shared air map built by people like you —
              {community.contributors} contributors logged {community.km_24h} km today,
              avoiding {community.avoided_ug_24h} µg of pollution together.
            </Text>
            <Text style={s.sub}>
              {community.active_reports > 0
                ? `${community.active_reports} air reports live on the map`
                : "spot dust, smoke or clean air? flag it with the ◍ button"}
            </Text>
          </View>
        )}

        <Pressable onPress={onClose}><Text style={s.close}>close</Text></Pressable>
      </Animated.View>
    </>
  );
}

const s = StyleSheet.create({
  scrim: { position: "absolute", top: 0, bottom: 0, left: 0, right: 0, backgroundColor: "rgba(28,25,23,0.25)" },
  drawer: {
    position: "absolute", top: 0, bottom: 0, left: 0, width: 300,
    backgroundColor: "rgba(255,255,255,0.97)",
    paddingTop: 64, paddingHorizontal: 18,
    borderRightWidth: 1, borderColor: T.glassBorder,
  },
  title: { fontFamily: F.semi, fontSize: 22, color: T.ink },
  sub: { fontFamily: F.reg, fontSize: 12, color: T.ink2, marginTop: 4, lineHeight: 17 },
  section: { fontFamily: F.semi, fontSize: 12, color: T.ink3, marginTop: 18, letterSpacing: 1 },
  weekRow: { flexDirection: "row", marginTop: 14, alignItems: "flex-end" },
  dayCol: { flex: 1, alignItems: "center" },
  dayBarWrap: { height: 72, justifyContent: "flex-end" },
  dayBar: { width: 18, borderRadius: 4, backgroundColor: T.doseLow },
  dayLabel: { fontFamily: F.reg, fontSize: 10, color: T.ink3, marginTop: 5 },
  trips: { maxHeight: 220, marginTop: 6 },
  trip: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: 8, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: T.glassBorder },
  tripTxt: { fontFamily: F.reg, fontSize: 12.5, color: T.ink, flex: 1, marginRight: 8 },
  tripDose: { fontFamily: F.semi, fontSize: 12.5, color: T.ink },
  city: { marginTop: 4 },
  close: { fontFamily: F.med, fontSize: 13, color: T.ink2, textAlign: "center", marginTop: 16, marginBottom: 30 },
});
