// First-run flow + consent gate (docs/plan/onboarding.md, doc 07 §3).
// Three pages, tap-next: what ALive does — the trip arc "see the smoke
// before you go · dose while you travel · a receipt when you arrive" told
// in the product's own strings — then why sharing helps (anonymous,
// aggregate, k≥3, stated plainly), then the sharing choice itself: two
// equal-size buttons, neither pre-picked.
//
// Skip is persistent on every page. Decision (docs/plan/onboarding.md):
// skip completes the flow with sharing ON — doc 07 §3 / doc 02 §7 make
// sharing the documented default, and Settings shows the state in one
// line with one tap to undo. The disclosure travels with the button —
// the "skipping counts as sharing on" line renders on EVERY page, so a
// page-0/1 skipper sees the consequence before tapping it.
//
// Mount only while `visible` so each open starts at page 1 fresh.
//
// ── strings — all copy is real t() keys; page 1 deliberately re-uses
// product strings (the search bar, the live counter, the receipt)
// instead of paraphrasing. onb_kLabel carries the k-card sentence minus
// the big "3+" numeral beside it; onb_pageOf is the reader's label for
// the otherwise-decorative dots.

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
import { fam, famSerif, NUM, V2Radius, V2T, V2Tint, V2Type } from "../theme";
import { t, type Lang } from "../i18n/strings";
import { Icon, type Glyph } from "../icons";
import { saveConsent, type SharingChoice } from "../store/consent";
import { DYNAMIC_TYPE, MIN_TOUCH, slop, useReduceMotion } from "../a11y";
import { confirm, tick } from "../haptics";
import { jank } from "../perf";

export type { SharingChoice } from "../store/consent";

const PAGE_COUNT = 3;

/** Journey row 1's mode strip — the compare sheet's real mode set,
 *  "every way there" made visible. */
const MODE_STRIP: Glyph[] = ["walk", "bike", "auto", "car", "bus", "metro"];

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

/** One plain-words fact on the why-sharing page. */
function Fact({ lang, children }: { lang: Lang; children: string }) {
  return (
    <View style={ss.fact}>
      <View style={ss.factDot} />
      <Text {...DYNAMIC_TYPE} style={[ss.factTxt, { fontFamily: fam(lang, "reg") }]}>
        {children}
      </Text>
    </View>
  );
}

/** One stage of the trip arc — a tinted card + the product's own strings
 *  (the register's card stack: one idea each, the icon's own colour). */
function JourneyRow({
  lang,
  icon,
  iconColor = V2T.text2,
  kicker,
  title,
  subs,
  children,
}: {
  lang: Lang;
  icon: Glyph;
  iconColor?: string;
  /** the stage's tint well — colour is the row's identity, not decoration */
  well?: { wash: string; ink: string };
  kicker?: string;
  title: string;
  subs?: string[];
  children?: React.ReactNode;
}) {
  return (
    /* one surface for every stage — the stage is told by its words,
       not a tint per row */
    <View style={[ss.jRow, { backgroundColor: V2T.surface }]}>
      <View style={ss.jIcon}>
        <Icon name={icon} color={iconColor} size={22} filled />
      </View>
      <View style={ss.jText}>
        {kicker ? (
          <Text {...DYNAMIC_TYPE} style={[ss.jKicker, { fontFamily: fam(lang, "semi") }]}>
            {kicker}
          </Text>
        ) : null}
        <Text {...DYNAMIC_TYPE} style={[ss.jTitle, { fontFamily: famSerif(lang, "med") }]}>
          {title}
        </Text>
        {subs?.map((s) => (
          <Text
            key={s}
            {...DYNAMIC_TYPE}
            style={[ss.jSub, { fontFamily: fam(lang, "reg") }]}
          >
            {s}
          </Text>
        ))}
        {children}
      </View>
    </View>
  );
}

/* ---------- sheet (mounted only while visible) ---------- */

function OnboardingSheet({
  lang,
  onDone,
}: {
  lang: Lang;
  onDone: (r: { sharing: SharingChoice }) => void;
}) {
  const [step, setStep] = useState(0);
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

  /** Every exit path lands here — persists the answer, then reports it. */
  const finish = (sharing: SharingChoice) => {
    saveConsent({ seen: true, sharing, ts: Date.now() }).catch(() => {});
    onDone({ sharing });
  };

  // Skip → sharing on (doc 07 §3 default; see header note + onboarding.md).
  const skip = () => finish("on");

  /* the dots read as a pager — make the swipe real: horizontal-dominant
     pans flip pages, vertical scroll passes through untouched
     (Android forensic find) */
  const swipe = useMemo(() => PanResponder.create({
    onMoveShouldSetPanResponder: (_e, g) =>
      Math.abs(g.dx) > 28 && Math.abs(g.dx) > Math.abs(g.dy) * 1.6,
    onPanResponderRelease: (_e, g) => {
      if (g.dx < -48 && step < PAGE_COUNT - 1) setStep(step + 1);
      else if (g.dx > 48 && step > 0) setStep(step - 1);
    },
  }), [step]);

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
        <Pressable
          onPress={() => { tick(); skip(); }}
          hitSlop={slop(10)}
          accessibilityRole="button"
          accessibilityLabel={t("onb_skip", lang)}
          style={({ pressed }) => [ss.skipBtn, pressed && { opacity: 0.6 }]}
        >
          <Text {...DYNAMIC_TYPE} style={[ss.skipTxt, { fontFamily: fam(lang, "med") }]}>
            {t("onb_skip", lang)}
          </Text>
        </Pressable>
      </View>

      <ScrollView
        style={ss.scroll}
        contentContainerStyle={ss.body}
        showsVerticalScrollIndicator={false}
      >
        <Animated.View style={{ opacity: anim, transform: [{ translateY: rise }] }}>
          {step === 0 && (
            <View>
              {/* p1 — what the app does, in the product's own words:
                  search → live counter → receipt. The onb_arc* kickers
                  carry the before/during/after beat over each row. */}
              <Text
                {...DYNAMIC_TYPE}
                accessibilityRole="header"
                style={[ss.hero, { fontFamily: famSerif(lang, "semi") }]}
              >
                {t("onb_whatTitle", lang)}
              </Text>
              <Text {...DYNAMIC_TYPE} style={[ss.lead, { fontFamily: fam(lang, "reg") }]}>
                {t("onb_whatBody", lang)}
              </Text>
              <View style={ss.journey}>
                {/* before you go — the search bar + "every way there" modes */}
                <JourneyRow
                  lang={lang}
                  icon="search"
                  well={V2Tint.forest}
                  kicker={t("onb_arcBefore", lang)}
                  title={t("searchPlaceholder", lang)}
                  subs={[t("checkingRoutes", lang)]}
                >
                  <View style={ss.modeRow}>
                    {MODE_STRIP.map((g) => (
                      <Icon key={g} name={g} color={V2T.text3} size={17} />
                    ))}
                  </View>
                </JourneyRow>
                {/* while you travel — the live dose counter, as in nav.
                    The dust glyph is the default breathe icon; the
                    cigarette only returns with show_cig on — onboarding
                    always reads the default surface. */}
                <JourneyRow
                  lang={lang}
                  icon="dust"
                  well={V2Tint.sand}
                  iconColor={V2T.breath1}
                  kicker={t("onb_arcDuring", lang)}
                  title={t("nav_breathe", lang)}
                  subs={[t("onboard_breatheSub", lang)]}
                />
                {/* when you arrive — the receipt's two real lines */}
                <JourneyRow
                  lang={lang}
                  icon="flag"
                  well={V2Tint.forest}
                  kicker={t("onb_arcAfter", lang)}
                  title={t("youreHere", lang)}
                  subs={[
                    t("onboard_receiptSub1", lang),
                    t("onboard_receiptSub2", lang),
                  ]}
                />
              </View>
            </View>
          )}

          {step === 1 && (
            <View>
              {/* p2 — why sharing helps: anonymous, aggregate, k≥3, honest */}
              <Text
                {...DYNAMIC_TYPE}
                accessibilityRole="header"
                style={[ss.hero, { fontFamily: famSerif(lang, "semi") }]}
              >
                {t("onb_privacyTitle", lang)}
              </Text>
              <Text {...DYNAMIC_TYPE} style={[ss.lead, { fontFamily: fam(lang, "reg") }]}>
                {t("settingsShareExplain", lang)}
              </Text>
              {/* the k-threshold — the mechanism that keeps any one person
                  invisible. Big numeral carries the claim, label explains it
                  (onb_kLabel: the settingsStoreK sentence minus its inline 3+). */}
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
              <View style={ss.facts}>
                <Fact lang={lang}>{t("onb_privacyNoAccount", lang)}</Fact>
                <Fact lang={lang}>{t("settingsStoreTrim", lang)}</Fact>
                <Fact lang={lang}>{t("onb_privacyLocation", lang)}</Fact>
              </View>
            </View>
          )}

          {step === 2 && (
            <View>
              {/* p3 — the choice: two equal-size answers, neither pre-picked */}
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
                  onPress={() => { confirm(); finish("on"); }}
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
                  onPress={() => { confirm(); finish("off"); }}
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

        </Animated.View>
      </ScrollView>

      {/* the skip disclosure travels with the button — visible on every
          page, not only the choice page it qualifies. It sits OUTSIDE
          the scroll: inside it, a page whose content overflows rendered
          the line half-clipped at the viewport edge (component-audit
          #2) — for a consent line, "present" means visible without
          scrolling. */}
      <Text {...DYNAMIC_TYPE} style={[ss.footnote, { fontFamily: fam(lang, "reg") }]}>
        {t("consent_footnote", lang)}
      </Text>

      {/* footer: dots + next (the choice page answers via its own buttons) */}
      <View style={ss.footer}>
        <Dots active={step} lang={lang} />
        {step < PAGE_COUNT - 1 ? (
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
  onDone,
}: {
  visible: boolean;
  lang?: Lang;
  onDone: (r: { sharing: SharingChoice }) => void;
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
      <OnboardingSheet lang={lang} onDone={onDone} />
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

  // p1 — the trip arc as a stack of tinted cards, one beat each
  journey: {
    marginTop: 30,
    gap: 12,
  },
  jRow: {
    flexDirection: "row",
    gap: 14,
    paddingVertical: 16,
    paddingHorizontal: 16,
    borderRadius: V2Radius.card,
  },
  jIcon: {
    width: 42,
    height: 42,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
  },
  jText: { flex: 1, gap: 4, paddingTop: 2 },
  /* the before/during/after beat — a small warm label, not a mono eyebrow */
  jKicker: {
    fontSize: V2Type.label,
    color: V2T.text2,
    marginBottom: 1,
  },
  jTitle: { fontSize: V2Type.body, color: V2T.text },
  jSub: { fontSize: V2Type.label, color: V2T.text2, lineHeight: 19 },
  modeRow: { flexDirection: "row", gap: 12, marginTop: 8 },

  // p2 — the k-threshold stat card + fact list
  kCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 18,
    marginTop: 26,
    backgroundColor: V2Tint.forest.wash,
    borderRadius: V2Radius.card,
    paddingVertical: 22,
    paddingHorizontal: 22,
  },
  kNum: { fontSize: V2Type.hero + 8, color: V2Tint.forest.ink },
  kLabel: { flex: 1, fontSize: V2Type.secondary, color: V2Tint.forest.ink, lineHeight: 20 },
  facts: { marginTop: 24, gap: 13 },
  fact: { flexDirection: "row", alignItems: "flex-start" },
  factDot: {
    width: 5,
    height: 5,
    borderRadius: 2.5,
    backgroundColor: V2T.text3,
    marginTop: 8,
    marginRight: 12,
  },
  factTxt: { flex: 1, fontSize: V2Type.secondary, color: V2T.text2, lineHeight: 22 },

  // p3 — equal-size choice buttons. Share fills ink with light text
  // (V2T.bg on ink ≫ 7:1); keep is
  // a solid surface button, not a ghosted link. Equal weight, no nudge.
  choiceCol: { gap: 12, marginTop: 28 },
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
