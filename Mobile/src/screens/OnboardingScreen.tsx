// First-run flow + consent gate (docs/plan/onboarding.md, doc 07 §3).
// Three beats + the choice + the permission ask, tap-next:
//
//   1. the air right now — the boot /aqi read's real ambient number,
//      band-inked (the ambient beat the app already plays, carried INTO
//      the sheet instead of flashing under it). No number when there's
//      no read — a fetched number is honest, a canned one is not.
//   2. the trip arc in one idea — "every Delhi trip has an air price":
//      see it before you go, counted while you ride, receipt when you
//      arrive. Three one-line rows, not a card lecture.
//   3. nothing personal leaves this phone — the k≥3 card is the proof.
//   4. the sharing choice — two equal-size buttons, neither pre-picked.
//   5. the location ask — the plain-words reason sits next to the button
//      that fires the OS dialog, not three screens behind it. "not now"
//      is a real decline: the OS ask stays quiet (the nav engine re-asks
//      when the user actually needs position).
//
// Skip is persistent on every page the choice hasn't been answered on
// (beats + consent). Decision (docs/plan/onboarding.md): skip completes
// the flow with sharing ON — doc 07 §3 / doc 02 §7 make sharing the
// documented default, and Settings shows the state in one line with one
// tap to undo. The disclosure travels with the button — the "skipping
// counts as sharing on" line renders on every page skip exists on, so a
// page-0/1 skipper sees the consequence before tapping it. A skip still
// fires the OS location dialog (the system's own ask — skipping the tour
// is not declining position). On the permission page itself there is no
// skip: sharing is already answered there, and its two buttons (turn on
// location / not now) ARE the whole choice.
//
// Consent persists the moment it's tapped — quitting on the permission
// page after answering must not replay the tour (consent is the required
// gate; the permission primer is not). `onDone({ sharing, askLocation })`
// reports both so the shell knows whether the OS dialog may fire.
//
// Mount only while `visible` so each open starts at beat 1 fresh.

import React, { useEffect, useMemo, useState } from "react";
import {
  Animated,
  BackHandler,
  PanResponder,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import {
  bandIdx, bandInkIdx,
  fam, famSerif, NUM, V2Radius, V2T, V2Tint, V2Type,
} from "../theme";
import { t, type Lang, type StringKey } from "../i18n/strings";
import { Icon, type Glyph } from "../icons";
import { saveConsent, type SharingChoice } from "../store/consent";
import { DYNAMIC_TYPE, MIN_TOUCH, slop, useReduceMotion } from "../a11y";
import { confirm, tick } from "../haptics";
import { jank } from "../perf";

export type { SharingChoice } from "../store/consent";

const PAGE_COUNT = 5;
/** the consent step — past it, forward swipe is dead (the choice needs
 *  a tap, not a drift) and the footer Next steps aside for the page's
 *  own buttons */
const STEP_CHOICE = 3;

/** CPCB band index → the band word ("good" … "severe") under the number. */
const BAND_KEYS: StringKey[] = [
  "band_good", "band_satisfactory", "band_moderate",
  "band_poor", "band_veryPoor", "band_severe",
];

/* ---------- small pieces ---------- */

/** Progress dots — visual dots stay decorative; the reader gets the
 *  "page {n} of {m}" line as the group's label instead. */
function Dots({ active, lang }: { active: number; lang: Lang }) {
  return (
    <View
      style={ss.dots}
      accessible
      accessibilityRole="text"
      accessibilityLabel={t("onb_pageOf", lang, { n: active + 1, m: PAGE_COUNT })}
    >
      {Array.from({ length: PAGE_COUNT }).map((_, i) => (
        <View key={i} style={[ss.dot, i === active && ss.dotOn]} />
      ))}
    </View>
  );
}

/** One arc line — icon well + a single phrase. The trip's before /
 *  during / after rhythm at word-count, not card-count. */
function ArcLine({
  lang, icon, iconColor = V2T.text2, children,
}: {
  lang: Lang; icon: Glyph; iconColor?: string; children: string;
}) {
  return (
    <View style={ss.arcRow}>
      <View style={ss.arcIcon}>
        <Icon name={icon} color={iconColor} size={18} filled />
      </View>
      <Text {...DYNAMIC_TYPE} style={[ss.arcTxt, { fontFamily: fam(lang, "reg") }]}>
        {children}
      </Text>
    </View>
  );
}

/* ---------- sheet (mounted only while visible) ---------- */

function OnboardingSheet({
  lang,
  ambientUg,
  onDone,
}: {
  lang: Lang;
  /** the boot /aqi ambient read — live, so a field tick mid-tour just
   *  updates the number. null on an offline cold open: no fake number. */
  ambientUg: number | null;
  onDone: (r: { sharing: SharingChoice; askLocation: boolean }) => void;
}) {
  const [step, setStep] = useState(0);
  /* the consent answer is written the moment it's tapped (see header) —
   *  null until the choice page answers; skip before it lands the
   *  documented "on" default */
  const [sharing, setSharing] = useState<SharingChoice | null>(null);
  /* exit takes a beat — onDone's flags commit through the draw-hold
     (bounded, but not instant). Without a busy latch the buttons sat
     live-and-silent in that window and read as dead on a cold boot
     (e2e-sweep #3: post-wipe page-5 presses eaten). First press flips
     the whole exit set to a labelled busy state; further presses are
     honest no-ops. */
  const [leaving, setLeaving] = useState(false);
  const insets = useSafeAreaInsets();
  const reduceMotion = useReduceMotion();

  // soft rise-in per page, skipped under the OS reduce-motion switch —
  // lazy useState (not useRef) so the lint rule "no ref reads in render" holds
  const [anim] = useState(() => new Animated.Value(0));
  useEffect(() => {
    if (reduceMotion) {
      anim.setValue(1);
      return;
    }
    anim.setValue(0);
    jank("enter.onboard");
    Animated.timing(anim, {
      toValue: 1,
      duration: 200,
      // native driver — pure opacity timing; none of Sheet's mixed-graph
      // detach risk (that JS-driver guard is about drag transforms)
      useNativeDriver: true,
    }).start();
  }, [step, reduceMotion, anim]);
  // stable node — inline interpolation re-created per render trips RN 0.86's
  // animated-props detach path (same guard as ui.tsx Sheet)
  const rise = useMemo(() => anim.interpolate({ inputRange: [0, 1], outputRange: [10, 0] }), [anim]);

  /** Every exit path lands here — persists a still-unanswered choice
   *  (skip → "on", the documented default), then reports both answers. */
  const finish = (askLocation: boolean) => {
    const s = sharing ?? "on";
    if (!sharing) saveConsent({ seen: true, sharing: s, ts: Date.now() }).catch(() => {});
    onDone({ sharing: s, askLocation });
  };

  /** every exit press — haptic, latch busy, then finish once. */
  const leave = (askLocation: boolean, bump: () => void) => {
    if (leaving) return;
    bump();
    setLeaving(true);
    finish(askLocation);
  };

  /** The consent tap — writes the record immediately, then the
   *  permission page. */
  const answer = (s: SharingChoice) => {
    confirm();
    setSharing(s);
    saveConsent({ seen: true, sharing: s, ts: Date.now() }).catch(() => {});
    setStep(STEP_CHOICE + 1);
  };

  /* the dots read as a pager — make the swipe real: horizontal-dominant
     pans flip pages, vertical scroll passes through untouched
     (Android forensic find). Forward stops at the choice — swiping past
     consent would answer a question nobody was asked. */
  const swipe = useMemo(() => PanResponder.create({
    onMoveShouldSetPanResponder: (_e, g) =>
      Math.abs(g.dx) > 28 && Math.abs(g.dx) > Math.abs(g.dy) * 1.6,
    onPanResponderRelease: (_e, g) => {
      if (g.dx < -48 && step < STEP_CHOICE) setStep(step + 1);
      else if (g.dx > 48 && step > 0) setStep(step - 1);
    },
  }), [step]);

  const airIdx = bandIdx(ambientUg ?? null);
  const airInk = airIdx != null ? bandInkIdx(airIdx) : V2T.text;

  return (
    <View {...swipe.panHandlers}
      style={[ss.root, { paddingTop: insets.top + 12, paddingBottom: insets.bottom + 12 }]} accessibilityViewIsModal>
      <StatusBar style="dark" />

      {/* brand mark + persistent skip — same spots on every page */}
      <View style={ss.topRow}>
        {/* brand logotype — proper noun, same in en+hi; not a t() key */}
        <Text {...DYNAMIC_TYPE} style={[ss.wordmark, { fontFamily: famSerif(lang, "semi") }]}>
          ALIVE
        </Text>
        <View style={{ flex: 1 }} />
        {step <= STEP_CHOICE && (
          <Pressable
            onPress={() => leave(true, tick)}
            disabled={leaving}
            hitSlop={slop(10)}
            accessibilityRole="button"
            accessibilityState={{ busy: leaving, disabled: leaving }}
            accessibilityLabel={t("onb_skip", lang)}
            style={({ pressed }) => [ss.skipBtn, (pressed || leaving) && { opacity: 0.6 }]}
          >
            <Text {...DYNAMIC_TYPE} style={[ss.skipTxt, { fontFamily: fam(lang, "med") }]}>
              {t("onb_skip", lang)}
            </Text>
          </Pressable>
        )}
      </View>

      <ScrollView
        style={ss.scroll}
        contentContainerStyle={ss.body}
        showsVerticalScrollIndicator={false}
      >
        <Animated.View style={{ opacity: anim, transform: [{ translateY: rise }] }}>
          {step === 0 && (
            <View>
              {/* beat 1 — the air right now. The number IS the page:
                  the boot /aqi read carried into the sheet, band-inked.
                  No read → the statement carries the page alone. */}
              <Text
                {...DYNAMIC_TYPE}
                style={[ss.eyebrow, { fontFamily: fam(lang, "med") }]}
              >
                {t("onb_airKicker", lang)}
              </Text>
              {ambientUg != null ? (
                <View
                  style={ss.airRow}
                  accessible
                  accessibilityRole="text"
                  accessibilityLabel={t("peekAmbient", lang, { n: Math.round(ambientUg) })}
                >
                  <Text
                    {...DYNAMIC_TYPE}
                    numberOfLines={1}
                    adjustsFontSizeToFit
                    minimumFontScale={0.5}
                    style={[ss.airNum, NUM, { fontFamily: famSerif(lang, "light"), color: airInk }]}
                  >
                    ~{Math.round(ambientUg)}
                  </Text>
                  <View style={ss.airMeta}>
                    <Text {...DYNAMIC_TYPE} style={[ss.airUnit, { fontFamily: fam(lang, "med"), color: airInk }]}>
                      µg/m³
                    </Text>
                    {airIdx != null && (
                      <Text {...DYNAMIC_TYPE} style={[ss.airBand, { fontFamily: fam(lang, "med"), color: airInk }]}>
                        {t(BAND_KEYS[airIdx], lang)}
                      </Text>
                    )}
                  </View>
                </View>
              ) : null}
              <Text
                {...DYNAMIC_TYPE}
                accessibilityRole="header"
                style={[
                  ambientUg != null ? ss.airLine : ss.hero,
                  { fontFamily: ambientUg != null ? fam(lang, "reg") : famSerif(lang, "semi") },
                ]}
              >
                {t("onb_airLine", lang)}
              </Text>
            </View>
          )}

          {step === 1 && (
            <View>
              {/* beat 2 — one idea, the trip's own rhythm:
                  before / during / after, one line each */}
              <Text
                {...DYNAMIC_TYPE}
                accessibilityRole="header"
                style={[ss.hero, { fontFamily: famSerif(lang, "semi") }]}
              >
                {t("onb_whatTitle", lang)}
              </Text>
              <View style={ss.arc}>
                <ArcLine lang={lang} icon="search">{t("onb_arcLineSearch", lang)}</ArcLine>
                <ArcLine lang={lang} icon="dust" iconColor={V2T.breath1}>{t("onb_arcLineDose", lang)}</ArcLine>
                <ArcLine lang={lang} icon="flag">{t("onb_arcLineReceipt", lang)}</ArcLine>
              </View>
            </View>
          )}

          {step === 2 && (
            <View>
              {/* beat 3 — the phone does the counting; the k-threshold
                  card is the mechanism that keeps any one person
                  invisible, so it stays as the proof */}
              <Text
                {...DYNAMIC_TYPE}
                accessibilityRole="header"
                style={[ss.hero, { fontFamily: famSerif(lang, "semi") }]}
              >
                {t("onb_phoneTitle", lang)}
              </Text>
              <Text {...DYNAMIC_TYPE} style={[ss.lead, { fontFamily: fam(lang, "reg") }]}>
                {t("onb_phoneBody", lang)}
              </Text>
              <View style={ss.kCard}>
                <Text
                  {...DYNAMIC_TYPE}
                  style={[ss.kNum, NUM, { fontFamily: famSerif(lang, "semi") }]}
                >
                  3+
                </Text>
                <Text {...DYNAMIC_TYPE} style={[ss.kLabel, { fontFamily: fam(lang, "reg") }]}>
                  {t("onb_kLabel", lang)}
                </Text>
              </View>
            </View>
          )}

          {step === STEP_CHOICE && (
            <View>
              {/* the choice — two equal-size answers, neither pre-picked */}
              <Text
                {...DYNAMIC_TYPE}
                accessibilityRole="header"
                style={[ss.hero, { fontFamily: famSerif(lang, "semi") }]}
              >
                {t("consent_title", lang)}
              </Text>
              <Text {...DYNAMIC_TYPE} style={[ss.lead, { fontFamily: fam(lang, "reg") }]}>
                {t("consent_body", lang)}
              </Text>
              <View style={ss.choiceCol}>
                <Pressable
                  onPress={() => answer("on")}
                  accessibilityRole="button"
                  accessibilityLabel={`${t("consent_shareBtn", lang)} — ${t("consent_shareSub", lang)}`}
                  style={({ pressed }) => [
                    ss.choiceBtn,
                    ss.choiceShare,
                    pressed && { opacity: 0.8 },
                  ]}
                >
                  <Text
                    {...DYNAMIC_TYPE}
                    style={[ss.choiceShareTxt, { fontFamily: fam(lang, "semi") }]}
                  >
                    {t("consent_shareBtn", lang)}
                  </Text>
                  <Text
                    {...DYNAMIC_TYPE}
                    style={[ss.choiceShareSub, { fontFamily: fam(lang, "reg") }]}
                  >
                    {t("consent_shareSub", lang)}
                  </Text>
                </Pressable>
                <Pressable
                  onPress={() => answer("off")}
                  accessibilityRole="button"
                  accessibilityLabel={`${t("consent_keepBtn", lang)} — ${t("consent_keepSub", lang)}`}
                  style={({ pressed }) => [
                    ss.choiceBtn,
                    ss.choiceKeep,
                    pressed && { opacity: 0.8 },
                  ]}
                >
                  <Text
                    {...DYNAMIC_TYPE}
                    style={[ss.choiceKeepTxt, { fontFamily: fam(lang, "semi") }]}
                  >
                    {t("consent_keepBtn", lang)}
                  </Text>
                  <Text
                    {...DYNAMIC_TYPE}
                    style={[ss.choiceKeepSub, { fontFamily: fam(lang, "reg") }]}
                  >
                    {t("consent_keepSub", lang)}
                  </Text>
                </Pressable>
              </View>
            </View>
          )}

          {step === STEP_CHOICE + 1 && (
            <View>
              {/* the location ask — the reason sits on the button that
                  fires the OS dialog; "not now" is a real decline */}
              <Text
                {...DYNAMIC_TYPE}
                accessibilityRole="header"
                style={[ss.hero, { fontFamily: famSerif(lang, "semi") }]}
              >
                {t("onb_locTitle", lang)}
              </Text>
              <Text {...DYNAMIC_TYPE} style={[ss.lead, { fontFamily: fam(lang, "reg") }]}>
                {t("onb_locBody", lang)}
              </Text>
              <View style={ss.choiceCol}>
                <Pressable
                  onPress={() => leave(true, confirm)}
                  disabled={leaving}
                  accessibilityRole="button"
                  accessibilityState={{ busy: leaving, disabled: leaving }}
                  accessibilityLabel={leaving ? t("onb_leaving", lang) : t("onb_locBtn", lang)}
                  style={({ pressed }) => [
                    ss.choiceBtn,
                    ss.locBtn,
                    (pressed || leaving) && { opacity: 0.8 },
                  ]}
                >
                  <View style={ss.locBtnRow}>
                    <Icon name="locate" color={V2T.bg} size={18} filled />
                    <Text
                      {...DYNAMIC_TYPE}
                      style={[ss.choiceShareTxt, { fontFamily: fam(lang, "semi") }]}
                    >
                      {leaving ? t("onb_leaving", lang) : t("onb_locBtn", lang)}
                    </Text>
                  </View>
                </Pressable>
                <Pressable
                  onPress={() => leave(false, tick)}
                  disabled={leaving}
                  accessibilityRole="button"
                  accessibilityState={{ busy: leaving, disabled: leaving }}
                  accessibilityLabel={t("onb_locLater", lang)}
                  style={({ pressed }) => [ss.locLaterBtn, (pressed || leaving) && { opacity: 0.6 }]}
                >
                  <Text
                    {...DYNAMIC_TYPE}
                    style={[ss.locLaterTxt, { fontFamily: fam(lang, "med") }]}
                  >
                    {t("onb_locLater", lang)}
                  </Text>
                </Pressable>
              </View>
            </View>
          )}

        </Animated.View>
      </ScrollView>

      {/* the skip disclosure travels with the button — visible on every
          page skip exists on, not only the choice page it qualifies. It
          sits OUTSIDE the scroll: inside it, a page whose content
          overflows rendered the line half-clipped at the viewport edge
          (component-audit #2) — for a consent line, "present" means
          visible without scrolling. */}
      {step <= STEP_CHOICE && (
        <Text {...DYNAMIC_TYPE} style={[ss.footnote, { fontFamily: fam(lang, "reg") }]}>
          {t("consent_footnote", lang)}
        </Text>
      )}

      {/* footer: dots + next (choice + permission answer via their own
          buttons — a footer Next would fake a third option) */}
      <View style={ss.footer}>
        <Dots active={step} lang={lang} />
        {step < STEP_CHOICE ? (
          <Pressable
            onPress={() => { tick(); setStep(step + 1); }}
            accessibilityRole="button"
            accessibilityLabel={t("onb_next", lang)}
            style={({ pressed }) => [ss.nextBtn, pressed && { opacity: 0.8 }]}
          >
            <Text {...DYNAMIC_TYPE} style={[ss.nextTxt, { fontFamily: fam(lang, "semi") }]}>
              {t("onb_next", lang)}
            </Text>
            <Icon name="chevron" color={V2T.bg} size={16} />
          </Pressable>
        ) : (
          <View style={ss.nextGhost} />
        )}
      </View>
    </View>
  );
}

/* ---------- public component ---------- */

function OnboardingScreenInner({
  visible,
  lang = "en",
  ambientUg = null,
  onDone,
}: {
  visible: boolean;
  lang?: Lang;
  ambientUg?: number | null;
  onDone: (r: { sharing: SharingChoice; askLocation: boolean }) => void;
}) {
  /* hardware back stays inert — leaving needs an explicit answer or Skip
     (the old Modal's onRequestClose swallowed it; the overlay needs a
     BackHandler to keep that contract) */
  useEffect(() => {
    if (!visible) return;
    const sub = BackHandler.addEventListener("hardwareBackPress", () => true);
    return () => sub.remove();
  }, [visible]);

  /* overlay, not Modal — RN 0.86's Modal native present/dismiss segfaulted
     this stack on the search sheet (SIGSEGV in runningboardd); onboarding
     is the worst place to inherit that crash class */
  if (!visible) return null;
  return (
    <View style={ss.backdrop}>
      <OnboardingSheet lang={lang} ambientUg={ambientUg} onDone={onDone} />
    </View>
  );
}

export const OnboardingScreen = React.memo(OnboardingScreenInner);

export default OnboardingScreen;

const ss = StyleSheet.create({
  /* elevation must beat HomeScreen's 24 — Android dispatches sibling touches
     by z before mount order, so the still-mounted home scroll swallowed this
     sheet's drags. iOS ignores it. */
  backdrop: { ...StyleSheet.absoluteFill, backgroundColor: V2T.bg, elevation: 30 },
  root: {
    flex: 1,

  },

  // top bar — wordmark left, persistent skip right
  topRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 28,
    minHeight: MIN_TOUCH,
  },
  wordmark: {
    fontSize: V2Type.label - 1,
    letterSpacing: 3,
    color: V2T.text3,
  },
  skipBtn: {
    minHeight: MIN_TOUCH,
    justifyContent: "center",
    paddingHorizontal: 10,
    marginRight: -10,
  },
  skipTxt: { fontSize: V2Type.secondary, color: V2T.text2 },

  scroll: { flex: 1 },
  body: {
    flexGrow: 1,
    justifyContent: "center",
    paddingHorizontal: 28,
    paddingVertical: 12,
  },

  // editorial type scale — hero + lead on every page
  hero: { fontSize: V2Type.hero, color: V2T.text, letterSpacing: -0.3 },
  lead: {
    fontSize: V2Type.secondary,
    color: V2T.text2,
    marginTop: 16,
    lineHeight: 23,
  },

  // beat 1 — the ambient number owns the page. Ultra-light Satoshi
  // numeral band-inked (colour means the air, never decoration); unit +
  // band word sit in its margin, not beside it as equals.
  eyebrow: {
    fontSize: V2Type.label,
    color: V2T.text3,
    letterSpacing: 1.2,
    marginBottom: 18,
  },
  airRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 14,
  },
  airNum: {
    fontSize: 96,
    lineHeight: 100,
    letterSpacing: -3,
    flexShrink: 1,
  },
  airMeta: { paddingBottom: 14, gap: 2 },
  airUnit: { fontSize: V2Type.body, letterSpacing: 0.4 },
  airBand: { fontSize: V2Type.label },
  airLine: {
    fontSize: V2Type.title,
    color: V2T.text,
    marginTop: 26,
    lineHeight: 31,
    maxWidth: 300,
  },

  // beat 2 — the trip arc as three one-line rows, no cards
  arc: { marginTop: 34, gap: 22 },
  arcRow: { flexDirection: "row", alignItems: "center", gap: 16 },
  arcIcon: {
    width: 38,
    height: 38,
    borderRadius: 12,
    backgroundColor: V2T.surface2,
    alignItems: "center",
    justifyContent: "center",
  },
  arcTxt: { flex: 1, fontSize: V2Type.body, color: V2T.text, lineHeight: 23 },

  // beat 3 — the k-threshold stat card stays the proof
  kCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 18,
    marginTop: 30,
    backgroundColor: V2Tint.forest.wash,
    borderRadius: V2Radius.card,
    paddingVertical: 22,
    paddingHorizontal: 22,
  },
  kNum: { fontSize: V2Type.hero + 8, color: V2Tint.forest.ink },
  kLabel: { flex: 1, fontSize: V2Type.secondary, color: V2Tint.forest.ink, lineHeight: 20 },

  // the choice — equal-size buttons. Share fills ink with light text
  // (V2T.bg on ink ≫ 7:1); keep is a solid surface button, not a ghosted
  // link. Equal weight, no nudge.
  choiceCol: { gap: 12, marginTop: 30 },
  choiceBtn: {
    borderRadius: V2Radius.card,
    paddingVertical: 20,
    paddingHorizontal: 22,
    minHeight: 84,
    justifyContent: "center",
    gap: 4,
  },
  choiceShare: { backgroundColor: V2T.text },
  choiceKeep: {
    backgroundColor: V2T.surface2,
  },
  choiceShareTxt: { fontSize: V2Type.body, color: V2T.bg },
  choiceShareSub: { fontSize: V2Type.label, color: V2T.bg },
  choiceKeepTxt: { fontSize: V2Type.body, color: V2T.text },
  choiceKeepSub: { fontSize: V2Type.label, color: V2T.text2 },

  // the permission ask — the CTA carries the verb the OS dialog repeats;
  // "not now" is the quiet, honest decline beside it
  locBtn: { backgroundColor: V2T.text, minHeight: 64 },
  locBtnRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  locLaterBtn: {
    minHeight: MIN_TOUCH,
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 10,
  },
  locLaterTxt: { fontSize: V2Type.secondary, color: V2T.text2 },

  footnote: {
    fontSize: V2Type.label,
    color: V2T.text3,
    textAlign: "center",
    /* pinned above the footer now — horizontal breathing room matches
       the page gutter; marginTop stays small so the line hugs the dots */
    marginTop: 8,
    marginBottom: 4,
    paddingHorizontal: 28,
    lineHeight: 19,
  },

  footer: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 28,
    paddingTop: 14,
    gap: 16,
  },
  dots: { flexDirection: "row", gap: 6 },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: V2T.line },
  dotOn: { width: 18, backgroundColor: V2T.accent },
  nextBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: V2T.text,
    borderRadius: V2Radius.pill,
    paddingHorizontal: 28,
    height: 56,
    justifyContent: "center",
  },
  nextTxt: { fontSize: V2Type.body, color: V2T.bg },
  nextGhost: { height: 52 },
});
