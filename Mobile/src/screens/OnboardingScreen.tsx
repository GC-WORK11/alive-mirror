// First-run flow + consent gate (docs/plan/onboarding.md, doc 07 §3).
// Three slides, tap-next: what ALive does (with the two numbers), the
// privacy promise + location primer, then the sharing choice — two
// equal-weight buttons, an explicit and honest answer.
//
// Skip is persistent on every slide. Decision (recorded in
// docs/plan/onboarding.md): skip completes the flow with sharing ON —
// doc 07 §3 and doc 02 §7 make sharing the default, and Settings shows
// the state in one line with one tap to undo. The choice slide states
// this plainly ("skipping counts as sharing on").
//
// Mount only while `visible` so each open starts at slide 1 fresh.

import React, { useState } from "react";
import {
  Modal,
  Platform,
  Pressable,
  StatusBar as RNStatusBar,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import { fam, NUM, V2Radius, V2T, V2Type } from "../theme";
import { t, type Lang } from "../i18n/strings";
import { Icon } from "../icons";
import { saveConsent, type SharingChoice } from "../store/consent";

export type { SharingChoice } from "../store/consent";

const SLIDE_COUNT = 3;

/* ---------- small pieces ---------- */

function Dots({ active }: { active: number }) {
  return (
    <View style={ss.dots}>
      {Array.from({ length: SLIDE_COUNT }).map((_, i) => (
        <View key={i} style={[ss.dot, i === active && ss.dotOn]} />
      ))}
    </View>
  );
}

/** One plain-words bullet on the privacy slide. */
function Bullet({ children }: { children: string }) {
  return (
    <View style={ss.bullet}>
      <View style={ss.bulletDot} />
      <Text style={ss.bulletTxt}>{children}</Text>
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

  /** Every exit path lands here — persists the answer, then reports it. */
  const finish = (sharing: SharingChoice) => {
    saveConsent({ seen: true, sharing, ts: Date.now() }).catch(() => {});
    onDone({ sharing });
  };

  // Skip → sharing on (doc 07 §3 default; see header note + onboarding.md).
  const skip = () => finish("on");

  return (
    <View style={ss.root}>
      <StatusBar style="light" />

      {/* persistent skip — same spot on every slide */}
      <View style={ss.topRow}>
        <View style={{ flex: 1 }} />
        <Pressable
          onPress={skip}
          hitSlop={12}
          accessibilityRole="button"
          accessibilityLabel={t("onb_skip", lang)}
          style={({ pressed }) => [ss.skipBtn, pressed && { opacity: 0.6 }]}
        >
          <Text style={[ss.skipTxt, { fontFamily: fam(lang, "med") }]}>
            {t("onb_skip", lang)}
          </Text>
        </Pressable>
      </View>

      <View style={ss.body}>
        {step === 0 && (
          <>
            <Text style={[ss.title, { fontFamily: fam(lang, "semi") }]}>
              {t("onb_whatTitle", lang)}
            </Text>
            <Text style={[ss.bodyTxt, { fontFamily: fam(lang, "reg") }]}>
              {t("onb_whatBody", lang)}
            </Text>
            {/* the two numbers, as they'll appear on every trip */}
            <View style={ss.numRow}>
              <View style={ss.numCard}>
                <Icon name="cigarette" color={V2T.breath1} size={22} />
                <Text style={[ss.numVal, NUM, { fontFamily: fam(lang, "semi") }]}>≈ 0.1</Text>
                <Text style={[ss.numLabel, { fontFamily: fam(lang, "reg") }]}>
                  {t("onb_numInLabel", lang)}
                </Text>
              </View>
              <View style={ss.numCard}>
                <Icon name="smoke" color={V2T.out1} size={22} />
                <Text style={[ss.numVal, NUM, { fontFamily: fam(lang, "semi") }]}>≈ 1.4 kg</Text>
                <Text style={[ss.numLabel, { fontFamily: fam(lang, "reg") }]}>
                  {t("onb_numOutLabel", lang)}
                </Text>
              </View>
            </View>
            <Text style={[ss.caption, { fontFamily: fam(lang, "reg") }]}>
              {t("onb_numCaption", lang)}
            </Text>
          </>
        )}

        {step === 1 && (
          <>
            <Text style={[ss.title, { fontFamily: fam(lang, "semi") }]}>
              {t("onb_privacyTitle", lang)}
            </Text>
            <View style={{ marginTop: 18, alignSelf: "stretch" }}>
              <Bullet>{t("onb_privacyNoAccount", lang)}</Bullet>
              <Bullet>{t("onb_privacyTrimmed", lang)}</Bullet>
              <Bullet>{t("onb_privacyLocation", lang)}</Bullet>
            </View>
          </>
        )}

        {step === 2 && (
          <>
            <Text style={[ss.title, { fontFamily: fam(lang, "semi") }]}>
              {t("consent_title", lang)}
            </Text>
            <Text style={[ss.bodyTxt, { fontFamily: fam(lang, "reg") }]}>
              {t("consent_body", lang)}
            </Text>
            {/* the choice — two equal-weight answers, neither pre-picked */}
            <View style={ss.choiceCol}>
              <Pressable
                onPress={() => finish("on")}
                accessibilityRole="button"
                accessibilityLabel={t("consent_shareBtn", lang)}
                style={({ pressed }) => [ss.choiceBtn, ss.choiceShare, pressed && { opacity: 0.75 }]}
              >
                <Text style={[ss.choiceBtnTxt, { fontFamily: fam(lang, "semi") }]}>
                  {t("consent_shareBtn", lang)}
                </Text>
                <Text style={[ss.choiceBtnSub, { fontFamily: fam(lang, "reg") }]}>
                  {t("consent_shareSub", lang)}
                </Text>
              </Pressable>
              <Pressable
                onPress={() => finish("off")}
                accessibilityRole="button"
                accessibilityLabel={t("consent_keepBtn", lang)}
                style={({ pressed }) => [ss.choiceBtn, ss.choiceKeep, pressed && { opacity: 0.75 }]}
              >
                <Text style={[ss.choiceBtnTxt, { fontFamily: fam(lang, "semi") }]}>
                  {t("consent_keepBtn", lang)}
                </Text>
                <Text style={[ss.choiceBtnSub, { fontFamily: fam(lang, "reg") }]}>
                  {t("consent_keepSub", lang)}
                </Text>
              </Pressable>
            </View>
            <Text style={[ss.caption, { fontFamily: fam(lang, "reg") }]}>
              {t("consent_footnote", lang)}
            </Text>
          </>
        )}
      </View>

      {/* footer: dots + next (choice slide answers via its own buttons) */}
      <View style={ss.footer}>
        <Dots active={step} />
        {step < SLIDE_COUNT - 1 ? (
          <Pressable
            onPress={() => setStep(step + 1)}
            accessibilityRole="button"
            accessibilityLabel={t("onb_next", lang)}
            style={({ pressed }) => [ss.nextBtn, pressed && { opacity: 0.75 }]}
          >
            <Text style={[ss.nextTxt, { fontFamily: fam(lang, "semi") }]}>
              {t("onb_next", lang)}
            </Text>
          </Pressable>
        ) : (
          <View style={{ height: 46 }} />
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
    paddingTop: Platform.select({
      ios: 56,
      android: (RNStatusBar.currentHeight ?? 24) + 12,
      default: 20,
    }),
    paddingHorizontal: 28,
    paddingBottom: 28,
  },
  topRow: { flexDirection: "row", alignItems: "center", minHeight: 36 },
  skipBtn: { paddingVertical: 8, paddingHorizontal: 4 },
  skipTxt: { fontSize: V2Type.secondary, color: V2T.text2 },

  body: { flex: 1, justifyContent: "center" },
  title: {
    fontSize: V2Type.title + 4,
    color: V2T.text,
    textAlign: "center",
    lineHeight: 34,
  },
  bodyTxt: {
    fontSize: V2Type.secondary,
    color: V2T.text2,
    textAlign: "center",
    marginTop: 14,
    lineHeight: 22,
  },
  caption: {
    fontSize: V2Type.label,
    color: V2T.text3,
    textAlign: "center",
    marginTop: 14,
  },

  // slide 1 — the two numbers
  numRow: { flexDirection: "row", gap: 12, marginTop: 24 },
  numCard: {
    flex: 1,
    alignItems: "center",
    backgroundColor: V2T.surface,
    borderRadius: V2Radius.row,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: V2T.line,
    paddingVertical: 16,
    paddingHorizontal: 8,
    gap: 6,
  },
  numVal: { fontSize: V2Type.title, color: V2T.text },
  numLabel: {
    fontSize: V2Type.label,
    color: V2T.text2,
    textAlign: "center",
    lineHeight: 17,
  },

  // slide 2 — privacy bullets
  bullet: { flexDirection: "row", marginBottom: 14 },
  bulletDot: {
    width: 5,
    height: 5,
    borderRadius: 2.5,
    backgroundColor: V2T.accent,
    marginTop: 8,
    marginRight: 12,
  },
  bulletTxt: {
    flex: 1,
    fontSize: V2Type.secondary,
    color: V2T.text2,
    lineHeight: 22,
  },

  // slide 3 — equal-weight choice buttons
  choiceCol: { gap: 12, marginTop: 24 },
  choiceBtn: {
    borderRadius: V2Radius.row,
    paddingVertical: 16,
    paddingHorizontal: 18,
    alignItems: "center",
    minHeight: 68,
    justifyContent: "center",
  },
  choiceShare: { backgroundColor: V2T.accent },
  choiceKeep: {
    backgroundColor: V2T.surface2,
    borderWidth: 1,
    borderColor: V2T.line,
  },
  choiceBtnTxt: { fontSize: V2Type.body, color: V2T.text, textAlign: "center" },
  choiceBtnSub: {
    fontSize: V2Type.label,
    color: V2T.text2,
    textAlign: "center",
    marginTop: 3,
  },

  footer: { alignItems: "center", gap: 16 },
  dots: { flexDirection: "row", gap: 6 },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: V2T.line },
  dotOn: { backgroundColor: V2T.accent },
  nextBtn: {
    backgroundColor: V2T.accent,
    borderRadius: V2Radius.pill,
    paddingHorizontal: 44,
    height: 46,
    justifyContent: "center",
  },
  nextTxt: { fontSize: V2Type.body, color: V2T.text },
});
