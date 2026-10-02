import React, { useEffect, useState } from "react";
import { Animated, Dimensions, Pressable, ScrollView, Share, StyleSheet, Text, View } from "react-native";
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
  onAmbient: () => void;
  onReminders: () => Promise<boolean>;
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

// ledger's rule of thumb: ~316 µg of PM2.5 inhaled ≈ one cigarette
const cigsOf = (ug: number) => ug / 316;
const fmtCig = (c: number) => {
  const r = Math.round(c * 10) / 10;
  return r >= 0.1 ? `${r}` : "<0.1";
};

const heroLine = (weekCigEq: number) => {
  if (weekCigEq <= 0) return "a nearly smoke-free week so far";
  if (weekCigEq < 0.1) return "barely a wisp of smoke this week — under a tenth of a cigarette";
  const n = Math.round(weekCigEq * 10) / 10;
  return `you breathed about ${n} ${n === 1 ? "cigarette" : "cigarettes"} of smoke this week`;
};

/* ------- tiny line-drawn icons (views only, no glyphs/emoji) ------- */

const ic = StyleSheet.create({
  routeDot: { width: 5, height: 5, borderRadius: 2.5, backgroundColor: T.accent, position: "absolute", top: 6 },
  routeLine: { width: 1.6, height: 6, backgroundColor: T.accent, position: "absolute", top: 11 },
  routeRing: {
    width: 6, height: 6, borderRadius: 3, borderWidth: 1.6, borderColor: T.accent,
    position: "absolute", bottom: 5,
  },
  head: {
    width: 4.5, height: 4.5, borderRadius: 2.25, borderWidth: 1.4, borderColor: T.accent,
    position: "absolute", top: 7,
  },
  shoulders: {
    width: 15, height: 6.5, borderWidth: 1.4, borderColor: T.accent, borderBottomWidth: 0,
    borderTopLeftRadius: 7.5, borderTopRightRadius: 7.5, position: "absolute", bottom: 6,
  },
  windBar: { height: 2, borderRadius: 1, backgroundColor: T.accent, marginVertical: 1.4, alignSelf: "flex-start", marginLeft: 8 },
  leaf: {
    width: 10.5, height: 10.5, borderWidth: 1.6, borderColor: T.accent,
    borderTopLeftRadius: 10.5, borderBottomRightRadius: 10.5,
    transform: [{ rotate: "45deg" }],
  },
  bellDome: {
    width: 11, height: 9, borderWidth: 1.6, borderColor: T.accent, borderBottomWidth: 0,
    borderTopLeftRadius: 6, borderTopRightRadius: 6, marginTop: -1,
  },
  bellDot: { width: 3.4, height: 3.4, borderRadius: 1.7, backgroundColor: T.accent, marginTop: 1.6 },
  moon: {
    width: 12, height: 12, borderRadius: 6, borderWidth: 1.6, borderColor: T.accent, overflow: "hidden",
  },
  moonHalf: { position: "absolute", right: 0, top: 0, bottom: 0, width: 6, backgroundColor: T.accent },
});

const Tile = ({ children }: { children: React.ReactNode }) => (
  <View style={s.tile}>{children}</View>
);

const RouteIcon = (
  <Tile>
    <View style={ic.routeDot} />
    <View style={ic.routeLine} />
    <View style={ic.routeRing} />
  </Tile>
);

const CommunityIcon = (
  <Tile>
    <View style={[ic.head, { left: 7.5 }]} />
    <View style={[ic.head, { right: 7.5 }]} />
    <View style={ic.shoulders} />
  </Tile>
);

const LungsIcon = (
  <Tile>
    <View style={[ic.windBar, { width: 13 }]} />
    <View style={[ic.windBar, { width: 9 }]} />
    <View style={[ic.windBar, { width: 5.5 }]} />
  </Tile>
);

const LeafIcon = (
  <Tile>
    <View style={ic.leaf} />
  </Tile>
);

const BellIcon = (
  <Tile>
    <View style={ic.bellDome} />
    <View style={ic.bellDot} />
  </Tile>
);

const MoonIcon = (
  <Tile>
    <View style={ic.moon}>
      <View style={ic.moonHalf} />
    </View>
  </Tile>
);

/** Per-mode mini glyph drawn with views — sits in the trip list. */
function ModeGlyph({ vehicle }: { vehicle: string }) {
  switch (vehicle) {
    case "car":
    case "car_open":
      return (
        <View style={mc.box}>
          <View style={[mc.body, { width: 13, height: 5.5, borderRadius: 1.8 }]} />
          <View style={mc.wheelRow}>
            <View style={mc.wheel} /><View style={mc.wheel} />
          </View>
        </View>
      );
    case "auto":
      return (
        <View style={mc.box}>
          <View style={[mc.body, { width: 10.5, height: 7, borderRadius: 2.5 }]} />
          <View style={[mc.wheelRow, { width: 11 }]}>
            <View style={mc.wheel} /><View style={mc.wheel} />
          </View>
        </View>
      );
    case "bus":
      return (
        <View style={mc.box}>
          <View style={[mc.body, { width: 13.5, height: 7.5, borderRadius: 2 }]}>
            <View style={mc.busWin} />
          </View>
          <View style={[mc.wheelRow, { width: 12 }]}>
            <View style={mc.wheel} /><View style={mc.wheel} />
          </View>
        </View>
      );
    case "metro":
      return (
        <View style={mc.box}>
          <View style={[mc.body, { width: 10, height: 10, borderRadius: 3 }]}>
            <View style={mc.busWin} />
          </View>
        </View>
      );
    case "bike":
    case "cycle":
      return (
        <View style={mc.box}>
          <View style={mc.bikeBar} />
          <View style={mc.bikeWheels}>
            <View style={mc.bikeWheel} /><View style={mc.bikeWheel} />
          </View>
        </View>
      );
    case "walk":
      return (
        <View style={mc.box}>
          <View style={mc.walkHead} />
          <View style={mc.walkBody} />
          <View style={mc.walkFeet} />
        </View>
      );
    default:
      return <View style={mc.box}><View style={ic.routeDot} /></View>;
  }
}

const mc = StyleSheet.create({
  box: { width: 26, height: 24, alignItems: "center", justifyContent: "center" },
  body: { backgroundColor: T.ink2, alignItems: "center", paddingTop: 1.5 },
  busWin: { width: "72%", height: 2.2, borderRadius: 1, backgroundColor: "rgba(255,255,255,0.9)" },
  wheelRow: { flexDirection: "row", justifyContent: "space-between", width: 10, marginTop: 1 },
  wheel: { width: 3, height: 3, borderRadius: 1.5, backgroundColor: T.ink2 },
  bikeBar: { width: 8, height: 1.8, borderRadius: 1, backgroundColor: T.ink2, marginBottom: 1 },
  bikeWheels: { flexDirection: "row", justifyContent: "space-between", width: 14 },
  bikeWheel: { width: 5, height: 5, borderRadius: 2.5, borderWidth: 1.4, borderColor: T.ink2 },
  walkHead: { width: 3.6, height: 3.6, borderRadius: 1.8, backgroundColor: T.ink2 },
  walkBody: { width: 2.4, height: 6, borderRadius: 1.2, backgroundColor: T.ink2, marginTop: 1 },
  walkFeet: { width: 7.5, height: 1.8, borderRadius: 1, backgroundColor: T.ink2, marginTop: 1 },
});

/* ------------------------- drawer ------------------------- */

type SectionKey = "trips" | "give" | "lungs" | "escape";

function Row({
  icon, label, trailing, open, onPress,
}: {
  icon: React.ReactNode; label: string; trailing?: React.ReactNode;
  open?: boolean; onPress?: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={!onPress}
      style={({ pressed }) => [s.row, pressed && !!onPress && { backgroundColor: T.accentSoft }]}
    >
      {icon}
      <Text style={s.rowLabel}>{label}</Text>
      {trailing}
      {onPress && (
        <Text style={[s.chev, open && { transform: [{ rotate: "90deg" }] }]}>›</Text>
      )}
    </Pressable>
  );
}

/** Navigation drawer — slides in from the left, google-maps style. */
export function JourneyDrawer({ week, stats, community, shiftCig, escape, onAmbient, onReminders, onClose }: Props) {
  const [remOn, setRemOn] = useState(false);

  const shareWeek = () => {
    const n = Math.round(week.weekCigEq * 10) / 10;
    const lines = [
      n > 0
        ? `this week i breathed ~${n} cigarette${n === 1 ? "" : "s"} of delhi's air.`
        : "this week my delhi air stayed nearly smoke-free.",
      stats.allAvoidedUg > 0
        ? `i skipped about ${fmtCig(cigsOf(stats.allAvoidedUg))} more by picking cleaner ways to go.`
        : "",
      "every trip i take helps map the city's pollution, street by street — ALive-108",
    ];
    Share.share({ message: lines.filter(Boolean).join("\n") }).catch(() => {});
  };
  const [slide] = useState(() => new Animated.Value(-Dimensions.get("window").width));
  useEffect(() => {
    Animated.spring(slide, { toValue: 0, useNativeDriver: true, damping: 24, stiffness: 220 }).start();
  }, [slide]);

  const [open, setOpen] = useState<SectionKey | null>("trips");
  const toggle = (k: SectionKey) => () => setOpen((o) => (o === k ? null : k));

  const maxUg = Math.max(...week.days.map((d) => d.ug), 1);
  const todayIdx = week.days.length - 1;
  const tripsThisWeek = week.days.reduce((n, d) => n + d.trips, 0);
  const escapePct = escape?.pct_less_than_here != null && escape.pct_less_than_here > 0
    ? escape.pct_less_than_here : null;

  return (
    <>
      <Pressable style={s.scrim} onPress={onClose} />
      <Animated.View style={[s.drawer, { transform: [{ translateX: slide }] }]}>
        <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={s.scroll}>

          {/* header: wordmark + this-week hero card */}
          <View style={s.brandRow}>
            <Text style={s.brand}>ALIVE-108</Text>
            <Text style={s.brandTag}>delhi ncr</Text>
          </View>

          <View style={s.hero}>
            <Text style={s.heroCap}>this week</Text>
            <Text style={s.heroLine}>{heroLine(week.weekCigEq)}</Text>
            <Text style={s.heroSub}>
              {tripsThisWeek > 0
                ? `${tripsThisWeek} ${tripsThisWeek === 1 ? "trip" : "trips"} logged`
                : "no trips logged yet"}
              {week.weekAvoided > 0
                ? ` · about ${fmtCig(cigsOf(week.weekAvoided))} cigarettes of smoke skipped`
                : ""}
            </Text>
            <View style={s.weekRow}>
              {week.days.map((d, i) => {
                const isToday = i === todayIdx;
                return (
                  <View key={i} style={s.dayCol}>
                    <View style={s.dayBarWrap}>
                      <View style={[s.dayBar, {
                        height: Math.max(3, (d.ug / maxUg) * 54),
                        backgroundColor: isToday ? T.accent : "rgba(15,118,110,0.28)",
                        opacity: d.ug === 0 ? 0.3 : 1,
                      }]} />
                    </View>
                    <Text style={[s.dayLabel, isToday && s.dayLabelToday]}>
                      {d.label.slice(0, 1)}
                    </Text>
                  </View>
                );
              })}
            </View>
            {stats.streak > 0 && (
              <Text style={s.streak}>
                {stats.streak}-day streak under the healthy daily limit
              </Text>
            )}
          </View>

          {/* menu rows */}
          <View style={s.menu}>
            <Row
              icon={RouteIcon}
              label="your trips today"
              open={open === "trips"}
              onPress={toggle("trips")}
              trailing={stats.today.length > 0
                ? <Text style={s.count}>{stats.today.length}</Text>
                : undefined}
            />
            {open === "trips" && (
              <View style={s.expBody}>
                {stats.today.length === 0 && (
                  <Text style={s.expLine}>no trips yet today — pick a route on the map</Text>
                )}
                {stats.today.map((t, i) => (
                  <View key={i} style={s.trip}>
                    <ModeGlyph vehicle={t.vehicle} />
                    <View style={s.tripMid}>
                      <Text style={s.tripTxt} numberOfLines={1}>{t.from} → {t.to}</Text>
                      <Text style={s.tripMeta}>{t.label} · {timeAgo(t.ts)}</Text>
                    </View>
                    <Text style={[s.pill, {
                      color: doseColor(t.dose_ug),
                      backgroundColor: `${doseColor(t.dose_ug)}1f`,
                    }]}>{Math.round(t.dose_ug)} µg</Text>
                  </View>
                ))}
                {stats.today.length > 0 && (
                  <Text style={s.unitNote}>
                    the pill is millionths of a gram of smoke breathed — lower is kinder
                  </Text>
                )}
              </View>
            )}

            {community && (
              <>
                <View style={s.div} />
                <Row
                  icon={CommunityIcon}
                  label="what you gave delhi"
                  open={open === "give"}
                  onPress={toggle("give")}
                />
                {open === "give" && (
                  <View style={s.expBody}>
                    <Text style={s.expLine}>
                      {community.km_24h} km of delhi streets measured together today
                    </Text>
                    {community.avoided_ug_24h > 0 && (
                      <Text style={s.expLine}>
                        about {fmtCig(cigsOf(community.avoided_ug_24h))} cigarettes of smoke
                        skipped together
                      </Text>
                    )}
                    <Text style={s.expLine}>
                      {community.active_reports > 0
                        ? `${community.active_reports} live air reports on the map`
                        : "no live air reports — see dust or smoke? flag it from the map"}
                    </Text>
                    <Text style={[s.expLine, s.expEm]}>
                      {"you're one of "}{community.contributors}{" contributors this week"}
                    </Text>
                    {stats.allAvoidedUg > 0 && (
                      <Text style={s.expLine}>
                        your own share so far: about {fmtCig(cigsOf(stats.allAvoidedUg))}
                        {" "}cigarettes of smoke skipped
                      </Text>
                    )}
                  </View>
                )}
              </>
            )}

            {shiftCig != null && (
              <>
                <View style={s.div} />
                <Row
                  icon={LungsIcon}
                  label="delhi's working lungs"
                  open={open === "lungs"}
                  onPress={toggle("lungs")}
                />
                {open === "lungs" && (
                  <View style={s.expBody}>
                    <Text style={s.expLine}>
                      {"a delivery rider's 8-hour shift today ≈ "}{shiftCig}
                      {" cigarettes of smoke — the price delhi's riders pay to keep the city moving."}
                    </Text>
                    <Text style={[s.expLine, s.expEm]}>you helped measure it.</Text>
                  </View>
                )}
              </>
            )}

            {escape && (
              <>
                <View style={s.div} />
                <Row
                  icon={LeafIcon}
                  label="cleanest air near you"
                  open={open === "escape"}
                  onPress={toggle("escape")}
                  trailing={escapePct != null
                    ? <Text style={s.trailVal}>{escapePct}% cleaner</Text>
                    : undefined}
                />
                {open === "escape" && (
                  <View style={s.expBody}>
                    <Text style={s.expLine}>
                      {escape.name ?? "a spot near you"} — the air there reads
                      {" "}{Math.round(escape.pm25)} µg/m³
                    </Text>
                    <Text style={s.expLine}>
                      {escapePct != null
                        ? `${escapePct}% cleaner than where you are. `
                        : ""}µg/m³ is the air-quality number — lower is cleaner.
                    </Text>
                  </View>
                )}
              </>
            )}

            <View style={s.div} />
            <Row
              icon={BellIcon}
              label="daily cleanest-window alert"
              onPress={async () => setRemOn(await onReminders())}
              trailing={<Text style={remOn ? s.trailVal : s.soon}>{remOn ? "on" : "off"}</Text>}
            />
            <View style={s.div} />
            <Row
              icon={MoonIcon}
              label="ambient mode"
              onPress={onAmbient}
            />
            <View style={s.div} />
            <Row
              icon={RouteIcon}
              label="share your week"
              onPress={shareWeek}
            />
          </View>

          <Pressable onPress={onClose} style={({ pressed }) => pressed && { opacity: 0.5 }}>
            <Text style={s.close}>close</Text>
          </Pressable>
        </ScrollView>
      </Animated.View>
    </>
  );
}

const s = StyleSheet.create({
  scrim: {
    position: "absolute", top: 0, bottom: 0, left: 0, right: 0,
    backgroundColor: "rgba(28,25,23,0.28)",
  },
  drawer: {
    position: "absolute", top: 0, bottom: 0, left: 0,
    width: Math.min(Dimensions.get("window").width * 0.78, 340),
    backgroundColor: "rgba(255,255,255,0.98)",
    borderRightWidth: 1, borderColor: T.glassBorder,
    shadowColor: "#000", shadowOpacity: 0.14, shadowRadius: 24, shadowOffset: { width: 4, height: 0 },
  },
  scroll: { paddingTop: 60, paddingHorizontal: 18, paddingBottom: 24 },

  brandRow: { flexDirection: "row", alignItems: "baseline", justifyContent: "space-between" },
  brand: { fontFamily: F.semi, fontSize: 13, color: T.accent, letterSpacing: 3, textTransform: "uppercase" },
  brandTag: { fontFamily: F.reg, fontSize: 11, color: T.ink3, letterSpacing: 0.4 },

  hero: {
    marginTop: 14, borderRadius: 18, padding: 14,
    backgroundColor: T.accentSoft, borderWidth: 1, borderColor: "rgba(15,118,110,0.22)",
  },
  heroCap: {
    fontFamily: F.semi, fontSize: 10.5, color: T.accent,
    letterSpacing: 1.4, textTransform: "uppercase",
  },
  heroLine: { fontFamily: F.semi, fontSize: 16.5, color: T.ink, marginTop: 6, lineHeight: 22 },
  heroSub: { fontFamily: F.reg, fontSize: 11.5, color: T.ink2, marginTop: 4, lineHeight: 16 },
  weekRow: { flexDirection: "row", marginTop: 12, alignItems: "flex-end" },
  dayCol: { flex: 1, alignItems: "center" },
  dayBarWrap: { height: 54, justifyContent: "flex-end" },
  dayBar: { width: 16, borderRadius: 5 },
  dayLabel: { fontFamily: F.reg, fontSize: 10, color: T.ink3, marginTop: 5 },
  dayLabelToday: { fontFamily: F.semi, color: T.accent },
  streak: { fontFamily: F.med, fontSize: 11.5, color: T.accent, marginTop: 10 },

  menu: { marginTop: 18 },
  row: {
    flexDirection: "row", alignItems: "center", gap: 12,
    paddingVertical: 10, paddingHorizontal: 6, borderRadius: 12,
  },
  rowLabel: { flex: 1, fontFamily: F.med, fontSize: 14, color: T.ink },
  tile: {
    width: 30, height: 30, borderRadius: 9, backgroundColor: T.accentSoft,
    alignItems: "center", justifyContent: "center",
  },
  chev: { fontFamily: F.semi, fontSize: 16, color: T.ink3, marginLeft: 2 },
  count: {
    fontFamily: F.semi, fontSize: 11, color: T.accent, backgroundColor: T.accentSoft,
    borderRadius: 999, paddingHorizontal: 8, paddingVertical: 2, overflow: "hidden",
  },
  trailVal: { fontFamily: F.semi, fontSize: 11.5, color: T.accent },
  soon: {
    fontFamily: F.med, fontSize: 10, color: T.ink3, borderWidth: 1, borderColor: T.glassBorder,
    borderRadius: 999, paddingHorizontal: 7, paddingVertical: 2, overflow: "hidden",
  },
  div: { height: StyleSheet.hairlineWidth, backgroundColor: T.glassBorder, marginLeft: 48 },

  expBody: {
    marginLeft: 42, marginTop: 2, marginBottom: 8, paddingLeft: 12,
    borderLeftWidth: 1, borderLeftColor: T.glassBorder,
  },
  expLine: { fontFamily: F.reg, fontSize: 12.5, color: T.ink2, lineHeight: 18, marginTop: 6 },
  expEm: { fontFamily: F.med, color: T.accent },
  unitNote: { fontFamily: F.reg, fontSize: 10.5, color: T.ink3, marginTop: 10, lineHeight: 15 },

  trip: { flexDirection: "row", alignItems: "center", paddingVertical: 8, gap: 8 },
  tripMid: { flex: 1, marginRight: 6 },
  tripTxt: { fontFamily: F.med, fontSize: 12.5, color: T.ink },
  tripMeta: { fontFamily: F.reg, fontSize: 10.5, color: T.ink3, marginTop: 2 },
  pill: {
    fontFamily: F.semi, fontSize: 11.5, fontVariant: ["tabular-nums"],
    borderRadius: 999, paddingHorizontal: 8, paddingVertical: 3, overflow: "hidden",
  },

  close: { fontFamily: F.med, fontSize: 13, color: T.ink2, textAlign: "center", marginTop: 14 },
});
