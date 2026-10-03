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
// line with one tap to undo. The choice page discloses it plainly
// ("skipping counts as sharing on") — no dark patterns.
//
// Mount only while `visible` so each open starts at page 1 fresh.
//
// ── strings seam — proposed NEW keys for src/i18n/strings.ts ─────────
// All rendered copy below is existing t() keys; page 1 deliberately
// re-uses real product strings (the search bar, the live counter, the
// receipt) instead of paraphrasing. When adopting, add each to BOTH the
// `en` and `hi` tables:
//   onb_arcBefore  "before you go"     — kicker over journey row 1
//   onb_arcDuring  "while you travel"  — kicker over journey row 2
//   onb_arcAfter   "when you arrive"   — kicker over journey row 3
//   onb_whyTitle   e.g. "shared trips build Delhi's air map" — optional
//                  harder-leading p2 heading (current title keeps the
//                  privacy promise, which is also honest)
//   onb_kLabel     "different travellers must cross a street before it
//                  can appear on the map" — k-card label without the
//                  inline "3+" the big numeral already carries
//   onb_pageOf     "page {n} of {m}"   — a11y label for the dots (they're
//                  hidden from the reader until this key exists)

import React, { useEffect, useState } from "react";
import {
  Animated,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { fam, NUM, V2Radius, V2T, V2Type } from "../theme";
import { t, type Lang } from "../i18n/strings";
import { Icon, type Glyph } from "../icons";
import { saveConsent, type SharingChoice } from "../store/consent";
import { DYNAMIC_TYPE, MIN_TOUCH, slop, useReduceMotion } from "../a11y";

export type { SharingChoice } from "../store/consent";

const PAGE_COUNT = 3;

/** Journey row 1's mode strip — the compare sheet's real mode set,
 *  "every way there" made visible. */
const MODE_STRIP: Glyph[] = ["walk", "bike", "auto", "car", "bus", "metro"];

/* ---------- small pieces ---------- */

/** Progress dots — decorative; the page titles carry position. */
function Dots({ active }: { active: number }) {
  return (
    <View
      style={ss.dots}
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
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

/** One stage of the trip arc — icon chip + the product's own strings. */
function JourneyRow({
  lang,
  icon,
  iconColor = V2T.text2,
  title,
  subs,
  last = false,
  children,
}: {
  lang: Lang;
  icon: Glyph;
  iconColor?: string;
  title: string;
  subs?: string[];
  last?: boolean;
  children?: React.ReactNode;
}) {
  return (
    <View style={[ss.jRow, last && ss.jRowLast]}>
      <View style={ss.jIcon}>
        <Icon name={icon} color={iconColor} size={18} />
      </View>
      <View style={ss.jText}>
        <Text {...DYNAMIC_TYPE} style={[ss.jTitle, { fontFamily: fam(lang, "med") }]}>
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
    Animated.timing(anim, {
      toValue: 1,
      duration: 200,
      useNativeDriver: true,
    }).start();
  }, [step, reduceMotion, anim]);
  const rise = anim.interpolate({ inputRange: [0, 1], outputRange: [10, 0] });

  /** Every exit path lands here — persists the answer, then reports it. */
  const finish = (sharing: SharingChoice) => {
    saveConsent({ seen: true, sharing, ts: Date.now() }).catch(() => {});
    onDone({ sharing });
  };

  // Skip → sharing on (doc 07 §3 default; see header note + onboarding.md).
  const skip = () => finish("on");

  return (
    <View style={[ss.root, { paddingTop: insets.top + 12, paddingBottom: insets.bottom + 12 }]} accessibilityViewIsModal>
      <StatusBar style="dark" />

      {/* brand mark + persistent skip — same spots on every page */}
      <View style={ss.topRow}>
        {/* brand logotype — proper noun, same in en+hi; not a t() key */}
        <Text {...DYNAMIC_TYPE} style={[ss.wordmark, { fontFamily: fam(lang, "semi") }]}>
          ALIVE
        </Text>
        <View style={{ flex: 1 }} />
        <Pressable
          onPress={skip}
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
                  search → live counter → receipt.
                  PROPOSED kickers onb_arcBefore/onb_arcDuring/onb_arcAfter
                  above rows 1-3 (see header). */}
              <Text
                {...DYNAMIC_TYPE}
                accessibilityRole="header"
                style={[ss.hero, { fontFamily: fam(lang, "semi") }]}
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
                  title={t("searchPlaceholder", lang)}
                  subs={[t("checkingRoutes", lang)]}
                >
                  <View style={ss.modeRow}>
                    {MODE_STRIP.map((g) => (
                      <Icon key={g} name={g} color={V2T.text3} size={17} />
                    ))}
                  </View>
                </JourneyRow>
                {/* while you travel — the live dose counter, as in nav */}
                <JourneyRow
                  lang={lang}
                  icon="cigarette"
                  iconColor={V2T.breath1}
                  title={t("nav_breathe", lang)}
                  subs={[t("onboard_breatheSub", lang)]}
                />
                {/* when you arrive — the receipt's two real lines */}
                <JourneyRow
                  lang={lang}
                  icon="flag"
                  title={t("youreHere", lang)}
                  subs={[
                    t("onboard_receiptSub1", lang),
                    t("onboard_receiptSub2", lang),
                  ]}
                  last
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
                style={[ss.hero, { fontFamily: fam(lang, "semi") }]}
              >
                {t("onb_privacyTitle", lang)}
              </Text>
              <Text {...DYNAMIC_TYPE} style={[ss.lead, { fontFamily: fam(lang, "reg") }]}>
                {t("settingsShareExplain", lang)}
              </Text>
              {/* the k-threshold — the mechanism that keeps any one person
                  invisible. Big numeral carries the claim, label explains it.
                  PROPOSED onb_kLabel without the repeated "3+" (see header). */}
              <View style={ss.kCard}>
                <Text
                  {...DYNAMIC_TYPE}
                  style={[ss.kNum, NUM, { fontFamily: fam(lang, "semi") }]}
                >
                  3+
                </Text>
                <Text {...DYNAMIC_TYPE} style={[ss.kLabel, { fontFamily: fam(lang, "reg") }]}>
                  {t("settingsStoreK", lang)}
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
                style={[ss.hero, { fontFamily: fam(lang, "semi") }]}
              >
                {t("consent_title", lang)}
              </Text>
              <Text {...DYNAMIC_TYPE} style={[ss.lead, { fontFamily: fam(lang, "reg") }]}>
                {t("consent_body", lang)}
              </Text>
              <View style={ss.choiceCol}>
                <Pressable
                  onPress={() => finish("on")}
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
                  onPress={() => finish("off")}
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
              <Text {...DYNAMIC_TYPE} style={[ss.footnote, { fontFamily: fam(lang, "reg") }]}>
                {t("consent_footnote", lang)}
              </Text>
            </View>
          )}
        </Animated.View>
      </ScrollView>

      {/* footer: dots + next (the choice page answers via its own buttons) */}
      <View style={ss.footer}>
        <Dots active={step} />
        {step < PAGE_COUNT - 1 ? (
          <Pressable
            onPress={() => setStep(step + 1)}
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

export function OnboardingScreen({
  visible,
  lang = "en",
  onDone,
}: {
  visible: boolean;
  lang?: Lang;
  onDone: (r: { sharing: SharingChoice }) => void;
}) {
  return (
    <Modal
      visible={visible}
      animationType="fade"
      // hardware back stays inert — leaving needs an explicit answer or Skip
      onRequestClose={() => {}}
      statusBarTranslucent
    >
      <View style={ss.backdrop}>
        {visible ? <OnboardingSheet lang={lang} onDone={onDone} /> : null}
      </View>
    </Modal>
  );
}

export default OnboardingScreen;

const ss = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: V2T.bg },
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

  // p1 — the trip arc as a hairline spec sheet
  journey: {
    marginTop: 30,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: V2T.line,
  },
  jRow: {
    flexDirection: "row",
    gap: 14,
    paddingVertical: 15,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: V2T.line,
  },
  jRowLast: { borderBottomWidth: 0 },
  jIcon: {
    width: 40,
    height: 40,
    borderRadius: V2Radius.row,
    backgroundColor: V2T.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: V2T.line,
    alignItems: "center",
    justifyContent: "center",
  },
  jText: { flex: 1, gap: 4, paddingTop: 2 },
  jTitle: { fontSize: V2Type.body, color: V2T.text },
  jSub: { fontSize: V2Type.label, color: V2T.text2, lineHeight: 19 },
  modeRow: { flexDirection: "row", gap: 12, marginTop: 8 },

  // p2 — the k-threshold stat card + fact list
  kCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 18,
    marginTop: 26,
    backgroundColor: V2T.surface,
    borderRadius: V2Radius.sheet,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: V2T.line,
    paddingVertical: 20,
    paddingHorizontal: 22,
  },
  kNum: { fontSize: V2Type.hero + 8, color: V2T.text },
  kLabel: { flex: 1, fontSize: V2Type.label, color: V2T.text2, lineHeight: 19 },
  facts: { marginTop: 24, gap: 13 },
  fact: { flexDirection: "row", alignItems: "flex-start" },
  factDot: {
    width: 5,
    height: 5,
    borderRadius: 2.5,
    backgroundColor: V2T.accent,
    marginTop: 8,
    marginRight: 12,
  },
  factTxt: { flex: 1, fontSize: V2Type.secondary, color: V2T.text2, lineHeight: 22 },

  // p3 — equal-size choice buttons. Share fills accent with light text
  // (V2T.bg on accent ≈ 5.2:1 — text2-on-accent failed at ~1.9:1); keep is
  // a solid surface button, not a ghosted link. Equal weight, no nudge.
  choiceCol: { gap: 12, marginTop: 28 },
  choiceBtn: {
    borderRadius: V2Radius.row,
    paddingVertical: 18,
    paddingHorizontal: 20,
    minHeight: 76,
    justifyContent: "center",
    gap: 4,
  },
  choiceShare: { backgroundColor: V2T.accent },
  choiceKeep: {
    backgroundColor: V2T.surface2,
    borderWidth: 1,
    borderColor: V2T.line,
  },
  choiceShareTxt: { fontSize: V2Type.body, color: V2T.bg },
  choiceShareSub: { fontSize: V2Type.label, color: V2T.bg },
  choiceKeepTxt: { fontSize: V2Type.body, color: V2T.text },
  choiceKeepSub: { fontSize: V2Type.label, color: V2T.text2 },
  footnote: {
    fontSize: V2Type.label,
    color: V2T.text3,
    textAlign: "center",
    marginTop: 16,
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
    backgroundColor: V2T.accent,
    borderRadius: V2Radius.pill,
    paddingHorizontal: 26,
    height: 52,
    justifyContent: "center",
  },
  nextTxt: { fontSize: V2Type.body, color: V2T.bg },
  nextGhost: { height: 52 },
});
