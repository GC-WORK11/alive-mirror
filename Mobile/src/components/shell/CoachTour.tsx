/** First-run coach tour — one spotlight walk over the home surface
 *  (docs/plan + the coach-tour lane): the ambient number, the dose
 *  ledger, the air-map door, the "where to?" entry, the week strip.
 *  Ordered the way a Delhi person needs them — air first, plan last.
 *
 *  It is an overlay, NOT a gate: the scrim and the ring take no touches
 *  (pointerEvents="none"), the root is box-none — every tap, drag and
 *  scroll lands on the real UI underneath; only the caption card's own
 *  buttons eat a press. The live numbers keep painting behind it.
 *
 *  Seen-flag lives in store/tour.ts (same File/Paths store as
 *  welcome/consent): written when the tour is presented — dismiss,
 *  skip, or the surface underneath taking over — so it plays once per
 *  install and never again. A force-quit before first paint re-arms it
 *  honestly.
 *
 *  Geometry: targets report themselves through the module registry —
 *  <TourTarget id> wraps a node, useMeasureTarget(id) attaches one in
 *  place. Each report stores CONTENT-space coords (windowY + scroll
 *  offset - scrollViewY), so the hole tracks a live drag or the tour's
 *  own scroll-to-target with no re-measure. A stop whose target never
 *  rendered (the week strip hides until a day counts) shows its caption
 *  centred, no hole — nothing is ever pointed at empty space. */
import React, {
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import {
  Dimensions,
  Pressable,
  StyleSheet,
  Text,
  View,
  type ScrollView,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { V2Elev, V2Radius, V2T, V2Type, fam } from "../../theme";
import { t, type Lang, type StringKey } from "../../i18n/strings";
import { DYNAMIC_TYPE } from "../../a11y";
import { FadeIn } from "../../ui";
import { tap, tick } from "../../haptics";
import { holdMapDraw } from "../../map/drawHold";
import { markTourSeen } from "../../store/tour";
import { bump } from "../../perf";

/* ---------------- target registry (content-space rects) ---------------- */

export type TourTargetId =
  | "hero"        // the ambient/dose hero block
  | "heroLedger"  // sparse-day progress row — the ledger filling up
  | "day"         // "your day" card (counted days only)
  | "doorMap"     // the Air-map row inside the doors card
  | "cta"         // the pinned "Where to?" pill
  | "week";       // the week strip (renders once a day counted)

type Rect = { x: number; y: number; w: number; h: number };
type Slot = { win: Rect; contentY: number };

const slots = new Map<TourTargetId, Slot>();
const remeasure = new Map<TourTargetId, () => void>();
const listeners = new Set<() => void>();
const scroll = { viewY: 0, offset: 0 };
let scrollerTo: ((contentY: number) => void) | null = null;
let version = 0;

const notify = () => { version += 1; listeners.forEach((f) => f()); };

function reportRect(id: TourTargetId, win: Rect | null): void {
  const dead = win == null || win.w < 2 || win.h < 2;
  const prev = slots.get(id);
  if (dead) {
    if (!prev) return;
    slots.delete(id);
  } else {
    const slot: Slot = { win, contentY: win.y + scroll.offset - scroll.viewY };
    if (prev && prev.win.x === win.x && prev.win.y === win.y
      && prev.win.w === win.w && prev.win.h === win.h) return;
    slots.set(id, slot);
  }
  notify();
}

/** Live window rect for a target — content-space storage + the current
 *  scroll offset means this stays true mid-drag, no re-measure. */
const liveRect = (id: TourTargetId): Rect | null => {
  const s = slots.get(id);
  return s ? { x: s.win.x, y: s.contentY - scroll.offset + scroll.viewY,
    w: s.win.w, h: s.win.h } : null;
};

/** Attach to any View/Pressable: `ref={m.node} onLayout={m.onLayout}`.
 *  The callback ref reports null on the ELEMENT's own unmount, so a
 *  conditional target can't leave a stale hole behind. (Named `node`,
 *  not `ref` — the react-hooks/refs lint reads any `.ref` member as a
 *  render-time ref access.) */
export function useMeasureTarget(id: TourTargetId): {
  node: (v: View | null) => void;
  onLayout: () => void;
} {
  /* the element lives in state, not a ref — the react-hooks/refs lint
     treats every member of a ref-derived object as a render-time ref
     access; a state node keeps the API (and the render) clean */
  const [el, setEl] = useState<View | null>(null);
  const measure = useCallback(() => {
    el?.measureInWindow((x, y, w, h) => reportRect(id, { x, y, w, h }));
  }, [id, el]);
  /* the callback ref reports null on the ELEMENT's own unmount, so a
     conditional target can't leave a stale hole behind */
  const attach = useCallback((v: View | null) => {
    setEl(v);
    if (!v) reportRect(id, null);
  }, [id]);
  /* mount + settle measures — FadeIn's translate finishes ~260 ms in */
  useEffect(() => {
    if (!el) return;
    remeasure.set(id, measure);
    measure();
    const t = setTimeout(measure, 550);
    return () => {
      remeasure.delete(id);
      clearTimeout(t);
    };
  }, [id, el, measure]);
  return { node: attach, onLayout: measure };
}

/** Wrapper form for children that can't take a ref — a plain View that
 *  keeps block layout. `collapsable={false}` so Android never flattens
 *  the measuring node away. */
export function TourTarget({ id, children, style }: {
  id: TourTargetId; children: React.ReactNode; style?: object;
}) {
  const { node, onLayout } = useMeasureTarget(id);
  return (
    <View ref={node} onLayout={onLayout} collapsable={false} style={style}>
      {children}
    </View>
  );
}

/* the home ScrollView wiring — the screen registers its scroller and
 * reports its own window-y (the scroll view IS the viewport box);
 * everything else is math here */
export function useTourScroller(
  scrollRef: React.RefObject<ScrollView | null>,
): void {
  useEffect(() => {
    /* the scroll view IS the viewport box; measureInWindow is a host-
       component method, reachable through getNativeScrollRef (the
       ScrollView instance type doesn't forward it) */
    const native = scrollRef.current?.getNativeScrollRef?.() as View | undefined;
    native?.measureInWindow?.((x: number, y: number) => { scroll.viewY = y; });
    scrollerTo = (contentY) =>
      scrollRef.current?.scrollTo({ y: Math.max(0, contentY), animated: true });
    return () => { scrollerTo = null; };
  }, [scrollRef]);
}
/** feed from ScrollView onScroll — throttled; every tick shifts liveRect. */
export function tourScrolled(offset: number): void {
  if (scroll.offset === offset) return;
  scroll.offset = offset;
  notify();
}

/* ---------------- the overlay ---------------- */

type Stop = { ids: TourTargetId[]; title: StringKey; body: StringKey };
/* ambient → ledger → map → plan entry → week — the owner's order; a stop
   picks the first id with a live rect (ledger = the day card when one is
   counted, else the hero's "counting" progress row) */
const STOPS: Stop[] = [
  { ids: ["hero"],               title: "homeAirNowLead",     body: "tourAmbient" },
  { ids: ["day", "heroLedger"],  title: "dayTitle",           body: "tourLedger" },
  { ids: ["doorMap"],            title: "homeLinkMap",        body: "tourMap" },
  { ids: ["cta"],                title: "searchPlaceholder",  body: "tourGo" },
  { ids: ["week"],               title: "weekTitle",          body: "tourWeek" },
];

const PAD = 9;      // breathing room around the target inside the hole
const RING_R = 20;  // the register's card corner

export function CoachTour({ lang, onDone }: { lang: Lang; onDone: () => void }) {
  bump("tour.CoachTour");
  const insets = useSafeAreaInsets();
  const v = useSyncExternalStore(
    (f) => { listeners.add(f); return () => { listeners.delete(f); }; },
    () => version,
  );
  const viewH = Dimensions.get("window").height;
  const viewW = Dimensions.get("window").width;
  /* arm delay — the sheet + FadeIn transforms settle post-onboarding
     before the first measure is trusted (the 550 ms per-target settle
     covers the drift). */
  const [shown, setShown] = useState(false);
  const [idx, setIdx] = useState(0);
  const doneRef = useRef(false);
  /* onDone through a ref: the caller passes an inline lambda, so its
     identity churns every App commit — a [done]-dep cleanup refired on
     every render and presented the tour on the FIRST state change after
     mount. Empty deps = cleanup only on a real unmount. */
  const onDoneRef = useRef(onDone);
  useEffect(() => { onDoneRef.current = onDone; }, [onDone]);
  const done = useCallback(() => {
    if (doneRef.current) return;
    doneRef.current = true;
    onDoneRef.current();
  }, []);
  /* unmount = presented (nav-away through the live scrim, home exit, or
     the predicate flipping) — one-time is the contract either way */
  useEffect(() => () => done(), [done]);
  useEffect(() => {
    holdMapDraw();   // an overlay mount — same draw-hold convention
    /* written at MOUNT, not dismissal: a kill mid-tour or a tap that
       walks through the live scrim never replays it — "never re-shows"
       outranks "finish the walk" */
    void markTourSeen();
    const t = setTimeout(() => setShown(true), 700);
    return () => clearTimeout(t);
  }, []);

  const stop = STOPS[idx];
  const rect = stop.ids.map(liveRect).find((r): r is Rect => r != null) ?? null;

  /* scroll the target into a comfortable band when the step lands —
     nothing scrolls for pinned chrome (cta) or targets already in view */
  useEffect(() => {
    if (!shown) return;
    const s = stop.ids.map((i) => slots.get(i)).find(Boolean);
    if (!s) return;
    const y = s.contentY - scroll.offset + scroll.viewY;
    const inView = y >= scroll.viewY + 4 && y + s.win.h <= viewH * 0.62;
    if (!inView && scrollerTo) scrollerTo(s.contentY - viewH * 0.30);
  }, [idx, shown, stop, viewH]);
  /* a late-mounted target (day card landing mid-tour, the week strip
     counting mid-tour) re-measures everything once when the registry
     learns it — cheap guard against a rect the effect missed */
  useEffect(() => {
    const t = setTimeout(() => remeasure.forEach((f) => f()), 380);
    return () => clearTimeout(t);
  }, [idx, v]);

  if (!shown) return null;
  const last = idx === STOPS.length - 1;
  /* the hole, padded + clamped to the viewport so an off-screen rect
     can't smear the scrim */
  const hole = rect
    ? { x: Math.max(0, rect.x - PAD), y: Math.max(0, rect.y - PAD),
        w: Math.min(viewW, rect.x - PAD + rect.w + PAD * 2) - Math.max(0, rect.x - PAD),
        h: rect.h + PAD * 2 }
    : null;
  const holeBottom = hole ? hole.y + hole.h : 0;
  /* caption placement: under the hole when it fits, over it when the
     hole sits low, bottom-anchored when there's nothing to point at */
  const below = hole != null && holeBottom + 150 < viewH;
  const cardAnchor: object = hole == null
    ? { bottom: insets.bottom + 40, left: 20, right: 20 }
    : below
      ? { top: holeBottom + 14, left: 20, right: 20 }
      : { bottom: Math.max(insets.bottom + 16, viewH - hole.y + 14), left: 20, right: 20 };

  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="box-none"
      accessibilityViewIsModal={false}>
      {/* the scrim — four panes, none of them touchable; the UI under
          the tour keeps answering taps while the dim says "look here" */}
      {hole ? (
        <>
          <View pointerEvents="none" style={[ss.scrim, { left: 0, top: 0, width: viewW, height: hole.y }]} />
          <View pointerEvents="none" style={[ss.scrim, { left: 0, top: holeBottom, width: viewW, height: Math.max(0, viewH - holeBottom) }]} />
          <View pointerEvents="none" style={[ss.scrim, { left: 0, top: hole.y, width: hole.x, height: hole.h }]} />
          <View pointerEvents="none" style={[ss.scrim, { left: hole.x + hole.w, top: hole.y, width: Math.max(0, viewW - (hole.x + hole.w)), height: hole.h }]} />
          {/* the ring — paper stroke + a whisper of ink, the register's
              "selected" grammar, not a new colour */}
          <View pointerEvents="none" style={[ss.ring, {
            left: hole.x - 2, top: hole.y - 2,
            width: hole.w + 4, height: hole.h + 4,
          }]} />
        </>
      ) : (
        <View pointerEvents="none" style={[ss.scrim, StyleSheet.absoluteFill]} />
      )}

      {/* the caption card — the only touchable: skip, and next/got it */}
      <FadeIn key={idx} delay={0} style={[ss.card, cardAnchor]}>
        <Text {...DYNAMIC_TYPE} numberOfLines={1}
          style={[ss.cardTitle, { fontFamily: fam(lang, "semi") }]}>
          {t(stop.title, lang)}
        </Text>
        <Text {...DYNAMIC_TYPE} style={[ss.cardBody, { fontFamily: fam(lang, "reg") }]}>
          {t(stop.body, lang)}
        </Text>
        <View style={ss.cardRow}>
          <Pressable onPress={() => { tick(); done(); }} hitSlop={10}
            accessibilityRole="button" accessibilityLabel={t("tourSkip", lang)}
            style={({ pressed }) => [ss.skipBtn, pressed && { opacity: 0.6 }]}>
            <Text {...DYNAMIC_TYPE} style={[ss.skipTxt, { fontFamily: fam(lang, "med") }]}>
              {t("tourSkip", lang)}
            </Text>
          </Pressable>
          <View style={ss.dots}>
            {STOPS.map((_, i) => (
              <View key={i} style={[ss.dot, i === idx && ss.dotOn]} />
            ))}
          </View>
          <Pressable
            onPress={() => {
              tap();
              if (last) done();
              else setIdx(idx + 1);
            }}
            accessibilityRole="button"
            accessibilityLabel={t(last ? "tourDone" : "tourNext", lang)}
            style={({ pressed }) => [ss.nextBtn, pressed && { opacity: 0.85 }]}>
            <Text {...DYNAMIC_TYPE} style={[ss.nextTxt, { fontFamily: fam(lang, "med") }]}>
              {t(last ? "tourDone" : "tourNext", lang)}
            </Text>
          </Pressable>
        </View>
      </FadeIn>
    </View>
  );
}

const ss = StyleSheet.create({
  scrim: { position: "absolute", backgroundColor: V2T.scrim },
  ring: {
    position: "absolute",
    borderRadius: RING_R,
    borderWidth: 1.5,
    borderColor: V2T.surface,
    ...V2Elev.float,
  },
  card: {
    position: "absolute",
    ...V2Elev.pop,
    backgroundColor: V2T.glassDeep,
    borderRadius: V2Radius.card,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: V2T.glassLine,
    paddingHorizontal: 18, paddingTop: 14, paddingBottom: 14,
  },
  cardTitle: { color: V2T.text, fontSize: V2Type.body },
  cardBody: { color: V2T.text2, fontSize: V2Type.secondary, lineHeight: 20, marginTop: 4 },
  cardRow: {
    flexDirection: "row", alignItems: "center",
    marginTop: 12, gap: 12,
  },
  dots: { flex: 1, flexDirection: "row", justifyContent: "center", gap: 5 },
  dot: { width: 5, height: 5, borderRadius: 2.5, backgroundColor: V2T.surface3 },
  dotOn: { backgroundColor: V2T.text },
  skipBtn: { paddingVertical: 6, paddingHorizontal: 2 },
  skipTxt: { color: V2T.text3, fontSize: V2Type.label },
  nextBtn: {
    backgroundColor: V2T.text, borderRadius: V2Radius.pill,
    paddingHorizontal: 16, paddingVertical: 8,
  },
  nextTxt: { color: V2T.bg, fontSize: V2Type.label },
});
