// S2 — instant search (docs/plan/02-consumer-ux.md §S2, docs/plan/04 §2).
// Full-screen sheet over the map; keyboard up instantly. Empty field: Home,
// Work (if set), last 5 recents. Typing: T0 rows paint in the same frame,
// server tiers stream in below a hairline. Matched characters of each title
// stay bright while the rest dims — no colour spent. "Your location" and
// "Choose on map" live in a bottom bar pinned above the keyboard so they're
// always one tap away. Every visible string goes through t() (or the LOCAL
// staging table below); every colour through V2T. No blur, no gradients.

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Animated,
  BackHandler,
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import Svg, { Path } from "react-native-svg";
import { NUM, V2Radius, V2T, V2Type, fam } from "../theme";
import { DYNAMIC_TYPE } from "../a11y";
import { t, type Lang } from "../i18n/strings";
import { Icon } from "../icons";
import {
  distKm,
  normalize,
  query as t0query,
  warm,
  type LatLon,
  type PlaceResult,
  type SearchSelection,
} from "../search/t0";
import { mergeResults, ServerSearch, type ServerTiers } from "../search/client";
import { addRecent, getPlaces, setSaved, type PlaceStore, type SavedSlot } from "../search/recents";
import { categoryGlyph } from "../search/CategoryIcon";
import { confirm, tick } from "../haptics";

export type { SearchSelection } from "../search/t0";
export type { PlaceResult } from "../search/t0";

const T0_LIMIT = 6;
const ROW_H = 54; // ≥44 pt touch target; fixed so results never shift under a finger

const fmtDist = (km: number): string =>
  km < 1
    ? `${Math.max(50, Math.round((km * 1000) / 50) * 50)} m`
    : km < 10
      ? `${(Math.round(km * 10) / 10).toFixed(1)} km`
      : `${Math.round(km)} km`;

const samePlace = (a: PlaceResult, b: PlaceResult) =>
  normalize(a.name) === normalize(b.name) &&
  Math.hypot((a.lat - b.lat) * 110.6, (a.lon - b.lon) * 99.4) * 1000 < 75;

/* ---------- matched-prefix highlight ----------
 * t0 ranks on normalized name tokens (nt.startsWith(qt)); we replay that same
 * test on the raw name's words so the highlighted span is exactly the span t0
 * matched. Abbreviations expand normalize-side, so "gk" lights all of
 * "Greater Kailash". Punctuation between words is never highlighted. */
const WORD = /[a-z0-9]+/gi;

function matchSpans(name: string, query: string): [number, number][] {
  const toks = normalize(query).split(" ").filter(Boolean);
  if (!toks.length) return [];
  const spans: [number, number][] = [];
  for (const m of name.matchAll(WORD)) {
    const w = m[0].toLowerCase();
    const start = m.index ?? 0;
    for (const qt of toks) {
      if (w.startsWith(qt)) {
        spans.push([start, start + Math.min(qt.length, w.length)]);
        break;
      }
    }
  }
  return spans;
}

/* ---------- rows ---------- */

function Title({ text, query, lang }: { text: string; query: string; lang: Lang }) {
  const spans = useMemo(() => matchSpans(text, query), [text, query]);
  const base = [ss.rowTitle, { fontFamily: fam(lang, "med") }];
  if (!spans.length) return <Text {...DYNAMIC_TYPE} style={base} numberOfLines={1}>{text}</Text>;
  // matched chars stay full-bright + semibold; the rest dims one step — the
  // eye lands on the match without a rupee of colour spent.
  const parts: React.ReactNode[] = [];
  let i = 0;
  spans.forEach(([s, e], k) => {
    if (s > i) parts.push(<Text {...DYNAMIC_TYPE} key={`d${k}`} style={[ss.rowTitleDim, { fontFamily: fam(lang, "reg") }]}>{text.slice(i, s)}</Text>);
    parts.push(<Text {...DYNAMIC_TYPE} key={`h${k}`} style={{ fontFamily: fam(lang, "semi") }}>{text.slice(s, e)}</Text>);
    i = e;
  });
  if (i < text.length) parts.push(<Text {...DYNAMIC_TYPE} key="tail" style={[ss.rowTitleDim, { fontFamily: fam(lang, "reg") }]}>{text.slice(i)}</Text>);
  return <Text {...DYNAMIC_TYPE} style={base} numberOfLines={1}>{parts}</Text>;
}

function PlaceRow({
  glyph, title, subtitle, distLabel, outsideNote, dim, lang, query = "",
  onPress, onLongPress, armed,
}: {
  glyph: React.ReactNode;
  title: string;
  subtitle?: string;
  distLabel?: string;
  outsideNote?: string;
  dim?: boolean;
  lang: Lang;
  query?: string;
  onPress: () => void;
  onLongPress?: () => void;
  armed?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      onLongPress={onLongPress}
      delayLongPress={320}
      accessibilityRole="button"
      accessibilityLabel={`${title}${subtitle ? `, ${subtitle}` : ""}${distLabel ? `, ${distLabel}` : ""}`}
      style={({ pressed }) => [
        ss.row,
        (pressed || armed) && { backgroundColor: "rgba(255,255,255,0.55)" },
        dim && { opacity: 0.55 },
      ]}
    >
      <View style={ss.glyphBox}>{glyph}</View>
      <View style={ss.rowText}>
        <Title text={title} query={query} lang={lang} />
        {outsideNote ? (
          <Text {...DYNAMIC_TYPE} style={[ss.rowOutside, { fontFamily: fam(lang, "reg") }]} numberOfLines={1}>{outsideNote}</Text>
        ) : subtitle ? (
          <Text {...DYNAMIC_TYPE} style={[ss.rowSub, { fontFamily: fam(lang, "reg") }]} numberOfLines={1}>{subtitle}</Text>
        ) : null}
      </View>
      {distLabel ? <Text {...DYNAMIC_TYPE} style={[ss.rowDist, NUM, { fontFamily: fam(lang, "reg") }]}>{distLabel}</Text> : null}
    </Pressable>
  );
}

function SectionLabel({ children, lang }: { children: string; lang: Lang }) {
  return (
    <Text {...DYNAMIC_TYPE} accessibilityRole="header" style={[ss.sectionLabel, { fontFamily: fam(lang, "semi") }]}>
      {children}
    </Text>
  );
}

/* Long-press action strip — the write path for the Home/Work slots the
 * empty field renders top of list. One row arms at a time: pick a place,
 * tap a slot. Slots already holding that exact place dim to their saved
 * label instead of re-writing. Saved rows arm in remove-mode — one slot,
 * one trash action. */
function SaveStrip({
  place, removeSlot, store, lang, onSave, onRemove,
}: {
  place: PlaceResult;
  removeSlot?: SavedSlot;
  store: PlaceStore;
  lang: Lang;
  onSave: (slot: SavedSlot, p: PlaceResult) => void;
  onRemove: (slot: SavedSlot) => void;
}) {
  if (removeSlot) {
    return (
      <View style={ss.saveStrip}>
        <Pressable
          onPress={() => { confirm(); onRemove(removeSlot); }}
          accessibilityRole="button"
          style={({ pressed }) => [ss.saveBtn, pressed && { opacity: 0.65 }]}
        >
          <Icon name="trash" color={V2T.pinDest} size={15} />
          <Text {...DYNAMIC_TYPE} style={[ss.saveTxt, { fontFamily: fam(lang, "med"), color: V2T.pinDest }]}>
            {t(removeSlot === "home" ? "removeHome" : "removeWork", lang)}
          </Text>
        </Pressable>
      </View>
    );
  }
  const slotBtn = (slot: SavedSlot) => {
    const held = store[slot];
    const already = held != null && samePlace(held, place);
    return (
      <Pressable
        key={slot}
        disabled={already}
        onPress={() => { confirm(); onSave(slot, place); }}
        accessibilityRole="button"
        style={({ pressed }) => [ss.saveBtn, pressed && { opacity: 0.65 }, already && { opacity: 0.45 }]}
      >
        <Icon name={slot} color={already ? V2T.text3 : V2T.accent} size={15} />
        <Text {...DYNAMIC_TYPE} style={[ss.saveTxt, { fontFamily: fam(lang, "med"), color: already ? V2T.text3 : V2T.accent }]}>
          {t(already ? (slot === "home" ? "savedHome" : "savedWork") : (slot === "home" ? "saveAsHome" : "saveAsWork"), lang)}
        </Text>
      </Pressable>
    );
  };
  return <View style={ss.saveStrip}>{slotBtn("home")}{slotBtn("work")}</View>;
}

function BackGlyph({ color }: { color: string }) {
  return (
    <Svg width={22} height={22} viewBox="0 0 24 24">
      <Path d="M14.5 5.5 8 12l6.5 6.5" stroke={color} strokeWidth={2} fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

/* ---------- sheet (mounted only while visible → fresh state each open) ---------- */

function SearchSheet({
  onSelect,
  onClose,
  userLocation,
  lang,
}: {
  onSelect: (sel: SearchSelection) => void;
  onClose: () => void;
  userLocation?: LatLon | null;
  lang: Lang;
}) {
  const [q, setQ] = useState("");
  const [t0rows, setT0rows] = useState<PlaceResult[]>([]);
  const [tiers, setTiers] = useState<ServerTiers | null>(null);
  const [store, setStore] = useState<PlaceStore>({ recents: [], home: null, work: null });
  // armed = the row whose long-press save/remove strip is showing
  const [armed, setArmed] = useState<{ place: PlaceResult; removeSlot?: SavedSlot } | null>(null);
  const [search] = useState(() => new ServerSearch(80));
  const inputRef = useRef<TextInput>(null);
  const closingRef = useRef(false);
  const insets = useSafeAreaInsets();
  /* mount in two frames: the shell commits first, the field+list subtree
     lands next frame — one giant mount commit against the map's draw
     thread is the residual-SIGSEGV trigger (ci15: search-open ~2/5).
     Keyboard waits for the enter spring to finish for the same reason. */
  const [bodyReady, setBodyReady] = useState(false);

  useEffect(() => {
    warm();
    getPlaces().then(setStore).catch(() => {});
    const raf = requestAnimationFrame(() => setBodyReady(true));
    const foc = setTimeout(() => { if (!closingRef.current) inputRef.current?.focus(); }, 350);
    /* cold-start race: the 350 ms focus() can fire before the window token
       accepts IME — field ends focused with mInputShown=false and the
       first keystrokes drop (seen on first-ever open post-install). If
       keyboardDidShow never fired by 1400 ms, focus() once more; the latch
       also blocks a re-raise after the user's own dismiss. */
    let kbShown = false;
    const ks = Keyboard.addListener("keyboardDidShow", () => { kbShown = true; });
    const refoc = setTimeout(() => {
      if (!closingRef.current && !kbShown) inputRef.current?.focus();
    }, 1400);
    return () => { cancelAnimationFrame(raf); clearTimeout(foc); clearTimeout(refoc); ks.remove(); search.dispose(); };
  }, [search]);

  const loc = userLocation ?? undefined;

  const onChange = useCallback(
    (text: string) => {
      setQ(text);
      setArmed(null);   // the list just rebuilt — the armed row may be gone
      const trimmed = text.trim();
      if (!trimmed) {
        setT0rows([]);
        setTiers(null);
        search.setQuery("", loc, () => {});
        return;
      }
      // T0 paints synchronously — same frame as the keystroke.
      setT0rows(t0query(text, loc, T0_LIMIT));
      setTiers(null); // waiting on the server tiers again
      search.setQuery(trimmed, loc, (res) => setTiers(res));
    },
    [loc, search],
  );

  /* Keyboard.dismiss() is async — closing the sheet in the same tick tears
     the scene down while the keyboard proxy is mid-handoff, and that race
     segfaults this RN/iOS-sim stack (same class as the autoFocus fix). Run
     the close on keyboardDidHide instead of a fixed delay — event-driven,
     with a 500ms cap if the keyboard never rose (no event ever arrives).
     Imperceptible to a user; identical UX on hardware. */
  const dismissThen = useCallback((fn: () => void) => {
    closingRef.current = true; // no late focus() while the sheet tears down
    if (!Keyboard.isVisible()) { fn(); return; }
    let done = false;
    const fire = () => { if (!done) { done = true; sub.remove(); fn(); } };
    const sub = Keyboard.addListener("keyboardDidHide", fire);
    Keyboard.dismiss();
    setTimeout(fire, 500);
  }, []);

  const pick = useCallback(
    (p: PlaceResult) => {
      tick();   // the row landed — light tick before the sheet slides away
      dismissThen(() => {
        addRecent(p).then(() => getPlaces().then(setStore)).catch(() => {});
        onSelect({ type: "place", place: p });
      });
    },
    [onSelect, dismissThen],
  );

  const distLabel = useCallback(
    (p: PlaceResult) => (loc ? fmtDist(distKm(p, loc)) : undefined),
    [loc],
  );

  const saveSlot = useCallback((slot: SavedSlot, p: PlaceResult | null) => {
    setArmed(null);
    setSaved(slot, p).then(setStore).catch(() => {});
  }, []);

  const armedFor = useCallback(
    (p: PlaceResult) => armed != null && !armed.removeSlot && samePlace(armed.place, p),
    [armed],
  );

  const armedRemove = useCallback(
    (slot: SavedSlot) => armed?.removeSlot === slot,
    [armed],
  );

  /* T0 section + deduped server rows below the hairline (doc 04 §2 merge) */
  const merged = useMemo(
    () => mergeResults(t0rows, tiers?.t1 ?? [], tiers?.t2 ?? []),
    [t0rows, tiers],
  );
  const serverRows = useMemo(
    () => merged.filter((p) => p.tier !== "t0" && !t0rows.some((l) => samePlace(l, p))),
    [merged, t0rows],
  );
  const typing = q.trim().length > 0;
  const pending = tiers === null;
  const empty = typing && !pending && merged.length === 0;

  const submit = useCallback(() => {
    // hardware/software "search" key = pick the top hit — the fastest path.
    if (merged[0]) pick(merged[0]);
  }, [merged, pick]);

  const renderPlace = (p: PlaceResult, key: string) => (
    <View key={key}>
      <PlaceRow
        lang={lang}
        query={q}
        glyph={categoryGlyph(p.kind, V2T.text2)}
        title={p.name}
        subtitle={p.subtitle}
        distLabel={distLabel(p)}
        outsideNote={p.outside_ncr ? t("outsideDelhi", lang) : undefined}
        dim={p.outside_ncr}
        armed={armedFor(p)}
        onPress={() => pick(p)}
        onLongPress={() => { tick(); setArmed(armedFor(p) ? null : { place: p }); }}
      />
      {armedFor(p) && (
        <SaveStrip place={p} store={store} lang={lang} onSave={saveSlot} onRemove={(slot) => saveSlot(slot, null)} />
      )}
    </View>
  );

  const hasSaved = !!(store.home || store.work);
  const hasRecents = store.recents.length > 0;

  return (
    <View style={[ss.root, { marginTop: insets.top + 8 }]}>
      {/* search bar — pill 999 (doc 03) */}
      <View style={ss.bar}>
        <Pressable
          onPress={() => { tick(); dismissThen(onClose); }}
          hitSlop={10}
          accessibilityRole="button"
          accessibilityLabel={t("a11yBack", lang)}
          style={ss.barBtn}
        >
          <BackGlyph color={V2T.text2} />
        </Pressable>
        <TextInput {...DYNAMIC_TYPE}
          ref={inputRef}
          style={[ss.input, { fontFamily: fam(lang, "reg") }]}
          value={q}
          onChangeText={onChange}
          onSubmitEditing={submit}
          placeholder={t("searchPlaceholder", lang)}
          placeholderTextColor={V2T.text2} // text3-on-surface2 = 4.33:1 < AA
          /* no autoFocus — becomeFirstResponder during mount races the
             responder chain on this stack; the +350ms focus lands after
             the enter spring settles */
          autoCorrect={false}
          autoCapitalize="none"
          autoComplete="off"
          spellCheck={false}
          keyboardAppearance="light"
          returnKeyType="search"
          clearButtonMode="never"
          accessibilityLabel={t("searchPlaceholder", lang)}
        />
        {q.length > 0 && (
          <Pressable
            onPress={() => { tick(); onChange(""); }}
            hitSlop={10}
            accessibilityRole="button"
            accessibilityLabel={t("a11yClear", lang)}
            style={ss.barBtn}
          >
            <Icon name="close" color={V2T.text3} size={16} />
          </Pressable>
        )}
      </View>

      {bodyReady && (
      <KeyboardAvoidingView
        style={ss.flex}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
      >
        {/* bounded list — ≤6 T0 + ≤12 merged + 7 saved/recents, so a plain
            ScrollView at a fixed row height stays jank-free (doc §S2) */}
        <ScrollView
          style={ss.flex}
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={ss.listContent}
        >
          {!typing ? (
            <>
              {hasSaved && <SectionLabel lang={lang}>{t("sidebarSavedPlaces", lang)}</SectionLabel>}
              {store.home && (
                <>
                  <PlaceRow
                    lang={lang}
                    glyph={<Icon name="home" color={V2T.accent} size={20} />}
                    title={t("home", lang)}
                    subtitle={store.home.name}
                    distLabel={distLabel(store.home)}
                    armed={armedRemove("home")}
                    onPress={() => pick(store.home!)}
                    onLongPress={() => { tick(); setArmed(armedRemove("home") ? null : { place: store.home!, removeSlot: "home" }); }}
                  />
                  {armedRemove("home") && (
                    <SaveStrip place={store.home} removeSlot="home" store={store} lang={lang} onSave={saveSlot} onRemove={(slot) => saveSlot(slot, null)} />
                  )}
                </>
              )}
              {store.work && (
                <>
                  <PlaceRow
                    lang={lang}
                    glyph={<Icon name="work" color={V2T.text2} size={20} />}
                    title={t("work", lang)}
                    subtitle={store.work.name}
                    distLabel={distLabel(store.work)}
                    armed={armedRemove("work")}
                    onPress={() => pick(store.work!)}
                    onLongPress={() => { tick(); setArmed(armedRemove("work") ? null : { place: store.work!, removeSlot: "work" }); }}
                  />
                  {armedRemove("work") && (
                    <SaveStrip place={store.work} removeSlot="work" store={store} lang={lang} onSave={saveSlot} onRemove={(slot) => saveSlot(slot, null)} />
                  )}
                </>
              )}
              {hasRecents && <SectionLabel lang={lang}>{t("recents", lang)}</SectionLabel>}
              {store.recents.map((p, i) => (
                <View key={`recent-${i}`}>
                  <PlaceRow
                    lang={lang}
                    glyph={<Icon name="clock" color={V2T.text2} size={20} />}
                    title={p.name}
                    subtitle={p.subtitle}
                    distLabel={distLabel(p)}
                    outsideNote={p.outside_ncr ? t("outsideDelhi", lang) : undefined}
                    dim={p.outside_ncr}
                    armed={armedFor(p)}
                    onPress={() => pick(p)}
                    onLongPress={() => { tick(); setArmed(armedFor(p) ? null : { place: p }); }}
                  />
                  {armedFor(p) && (
                    <SaveStrip place={p} store={store} lang={lang} onSave={saveSlot} onRemove={(slot) => saveSlot(slot, null)} />
                  )}
                </View>
              ))}
              {!hasSaved && !hasRecents && (
                <View style={ss.stateBlock} accessibilityLiveRegion="polite">
                  <Icon name="search" color={V2T.text3} size={22} />
                  <Text {...DYNAMIC_TYPE} style={[ss.stateText, { fontFamily: fam(lang, "reg") }]}>
                    {t("emptySearchHint", lang)}
                  </Text>
                </View>
              )}
            </>
          ) : (
            <>
              {merged.length > 0 && <SectionLabel lang={lang}>{t("resultsHeader", lang)}</SectionLabel>}
              {t0rows.map((p, i) => renderPlace(p, `t0-${i}`))}
              {(pending || serverRows.length > 0) && t0rows.length > 0 && <View style={ss.hairline} />}
              {pending ? (
                <View style={ss.statusRow} accessibilityLiveRegion="polite">
                  <Text {...DYNAMIC_TYPE} style={[ss.waiting, { fontFamily: fam(lang, "reg") }]}>{t("searching", lang)}</Text>
                </View>
              ) : (
                serverRows.map((p, i) => renderPlace(p, `srv-${p.tier}-${i}`))
              )}
              {empty && (
                <View style={ss.stateBlock} accessibilityLiveRegion="polite">
                  <Icon name="search" color={V2T.text3} size={22} />
                  <Text {...DYNAMIC_TYPE} style={[ss.stateText, { fontFamily: fam(lang, "reg") }]}>
                    {t("noPlaceFound", lang)}
                  </Text>
                </View>
              )}
            </>
          )}
        </ScrollView>

        {/* action bar — pinned above the keyboard; "Choose on map" is always
            one tap away even mid-scroll (doc 02 §S2). */}
        <View style={[ss.actionBar, { paddingBottom: insets.bottom + 6 }]}>
          <Pressable
            onPress={() => { tick(); dismissThen(() => onSelect({ type: "current_location" })); }}
            accessibilityRole="button"
            accessibilityLabel={t("yourLocation", lang)}
            style={({ pressed }) => [ss.actionBtn, pressed && { backgroundColor: "rgba(255,255,255,0.55)" }]}
          >
            <Icon name="locate" color={V2T.accent} size={18} />
            <Text {...DYNAMIC_TYPE} style={[ss.actionTxt, { fontFamily: fam(lang, "med") }]} numberOfLines={1}>
              {t("yourLocation", lang)}
            </Text>
          </Pressable>
          <View style={ss.actionSplit} />
          <Pressable
            onPress={() => { tick(); dismissThen(() => onSelect({ type: "choose_on_map" })); }}
            accessibilityRole="button"
            accessibilityLabel={t("chooseOnMap", lang)}
            accessibilityHint={t("mapPickHint", lang)}
            style={({ pressed }) => [ss.actionBtn, pressed && { backgroundColor: "rgba(255,255,255,0.55)" }]}
          >
            <Icon name="pin" color={V2T.accent} size={18} />
            <Text {...DYNAMIC_TYPE} style={[ss.actionTxt, { fontFamily: fam(lang, "med") }]} numberOfLines={1}>
              {t("chooseOnMap", lang)}
            </Text>
          </Pressable>
        </View>
      </KeyboardAvoidingView>
      )}
    </View>
  );
}

/* ---------- public component: <SearchScreen visible onSelect onClose userLocation/> ---------- */

export function SearchScreen({
  visible,
  onSelect,
  onClose,
  userLocation,
  lang = "en",
}: {
  visible: boolean;
  onSelect: (sel: SearchSelection) => void;
  onClose: () => void;
  userLocation?: LatLon | null;
  lang?: Lang;
}) {
  /* Android hardware back must close the sheet — Modal used to provide this;
     the overlay needs BackHandler explicitly. */
  useEffect(() => {
    if (!visible) return;
    const sub = BackHandler.addEventListener("hardwareBackPress", () => { onClose(); return true; });
    return () => sub.remove();
  }, [visible, onClose]);

  /* the Modal used to slide the sheet up — keep that enter on the overlay:
     stable animated nodes + JS driver (the proven-safe pattern from Sheet;
     native-driven springs are what segfault this RN/iOS stack) */
  const [enter] = useState(() => new Animated.Value(0));
  const [enterTy] = useState(() => enter.interpolate({ inputRange: [0, 1], outputRange: [36, 0] }));
  useEffect(() => {
    if (visible) {
      enter.setValue(0);
      Animated.spring(enter, { toValue: 1, damping: 24, stiffness: 240, useNativeDriver: false }).start();
    }
  }, [visible, enter]);

  /* plain absolute overlay — every other sheet in the app renders this way.
     RN Modal's native present/dismiss segfaults this stack (reproduced three
     times live: open, quick-pick dismiss, cold present) — no Modal, no crash
     class. Identical UX: scrim backdrop + sheet over the map. */
  if (!visible) return null;
  return (
    <View style={ss.backdrop}>
      <StatusBar style="dark" />
      <Animated.View style={{ flex: 1, opacity: enter, transform: [{ translateY: enterTy }] }}>
        <SearchSheet
          onSelect={onSelect}
          onClose={onClose}
          userLocation={userLocation}
          lang={lang}
        />
      </Animated.View>
    </View>
  );
}

export default SearchScreen;

const ss = StyleSheet.create({
  backdrop: { ...StyleSheet.absoluteFill, backgroundColor: V2T.scrim },
  root: {
    flex: 1,
    // marginTop comes from useSafeAreaInsets inline

    backgroundColor: V2T.glassDeep,
    borderTopLeftRadius: V2Radius.sheet,
    borderTopRightRadius: V2Radius.sheet,
    borderTopWidth: 1,
    borderColor: V2T.glassEdge,
    overflow: "hidden",
  },
  bar: {
    flexDirection: "row",
    alignItems: "center",
    height: 52,
    marginHorizontal: 12,
    marginTop: 10,
    marginBottom: 6,
    paddingHorizontal: 10,
    backgroundColor: V2T.glassSoft,
    borderRadius: V2Radius.pill,
    borderWidth: 1,
    borderColor: V2T.glassLine,
  },
  barBtn: { padding: 6 },
  input: {
    flex: 1,
    color: V2T.text,
    fontSize: V2Type.body,
    marginLeft: 6,
    paddingVertical: 0,
  },
  flex: { flex: 1 },
  listContent: { paddingBottom: 16, flexGrow: 1 },
  sectionLabel: {
    color: V2T.text3,
    fontSize: V2Type.label,
    letterSpacing: 0.6,
    textTransform: "uppercase",
    marginTop: 10,
    marginBottom: 2,
    marginHorizontal: 18,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    minHeight: ROW_H,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: V2Radius.row,
  },
  glyphBox: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: V2T.glassFaint,
    borderWidth: 1, borderColor: V2T.glassLine,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
  },
  rowText: { flex: 1, marginRight: 10 },
  rowTitle: { color: V2T.text, fontSize: V2Type.body },
  rowTitleDim: { color: V2T.text2 },
  rowSub: { color: V2T.text2, fontSize: V2Type.label, marginTop: 1 },
  rowOutside: { color: V2T.text3, fontSize: V2Type.label, marginTop: 1 },
  rowDist: { color: V2T.text2, fontSize: V2Type.label },
  hairline: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: V2T.glassLine,
    marginHorizontal: 14,
    marginVertical: 4,
  },
  statusRow: { minHeight: ROW_H, justifyContent: "center" },
  waiting: {
    color: V2T.text3,
    fontSize: V2Type.label,
    marginHorizontal: 18,
    marginVertical: 10,
  },
  stateBlock: {
    minHeight: 120,
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    paddingHorizontal: 40,
  },
  stateText: {
    color: V2T.text2,
    fontSize: V2Type.secondary,
    textAlign: "center",
    lineHeight: 21,
  },
  actionBar: {
    flexDirection: "row",
    alignItems: "stretch",
    borderTopWidth: 1,
    borderColor: V2T.glassLine,
    backgroundColor: V2T.glass,
    // paddingBottom from useSafeAreaInsets inline
  },
  actionBtn: {
    flex: 1,
    minHeight: 48,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    paddingHorizontal: 8,
  },
  actionSplit: {
    width: StyleSheet.hairlineWidth,
    backgroundColor: V2T.glassLine,
    marginVertical: 12,
  },
  actionTxt: { color: V2T.text, fontSize: V2Type.secondary },
  saveStrip: {
    flexDirection: "row",
    gap: 8,
    paddingHorizontal: 56,   // sits under the row's text column
    paddingBottom: 10,
    paddingTop: 2,
    backgroundColor: V2T.glassSoft,
  },
  saveBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    minHeight: 36,
    paddingHorizontal: 12,
    borderRadius: V2Radius.pill,
    backgroundColor: V2T.glassFaint,
    borderWidth: 1,
    borderColor: V2T.glassLine,
  },
  saveTxt: { fontSize: V2Type.label },
});
