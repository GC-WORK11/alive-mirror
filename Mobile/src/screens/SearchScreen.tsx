// S2 — instant search (docs/plan/02-consumer-ux.md §S2, docs/plan/04 §2).
// Full-screen sheet over the map; keyboard up instantly. Empty field: Home,
// Work (if set), last 5 recents. Typing: T0 rows paint in the same frame,
// server tiers stream in below a hairline. Every visible string goes
// through t(); every colour through V2T. No blur, no gradients.

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Keyboard,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StatusBar as RNStatusBar,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import Svg, { Path } from "react-native-svg";
import { NUM, V2Radius, V2T, V2Type } from "../theme";
import { t, type Lang } from "../i18n/strings";
import { Icon } from "../icons";
import {
  distKm,
  query as t0query,
  warm,
  type LatLon,
  type PlaceResult,
  type SearchSelection,
} from "../search/t0";
import { mergeResults, ServerSearch, type ServerTiers } from "../search/client";
import { addRecent, getPlaces, type PlaceStore } from "../search/recents";
import { categoryGlyph } from "../search/CategoryIcon";

export type { SearchSelection } from "../search/t0";
export type { PlaceResult } from "../search/t0";

const T0_LIMIT = 6;

const fmtDist = (km: number): string =>
  km < 1
    ? `${Math.max(50, Math.round((km * 1000) / 50) * 50)} m`
    : km < 10
      ? `${(Math.round(km * 10) / 10).toFixed(1)} km`
      : `${Math.round(km)} km`;

const samePlace = (a: PlaceResult, b: PlaceResult) =>
  a.name.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim() ===
    b.name.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim() &&
  Math.hypot((a.lat - b.lat) * 110.6, (a.lon - b.lon) * 99.4) * 1000 < 75;

/* ---------- rows ---------- */

function PlaceRow({
  glyph, title, subtitle, distLabel, outsideNote, dim, onPress,
}: {
  glyph: React.ReactNode;
  title: string;
  subtitle?: string;
  distLabel?: string;
  outsideNote?: string;
  dim?: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`${title}${subtitle ? `, ${subtitle}` : ""}`}
      style={({ pressed }) => [
        ss.row,
        pressed && { backgroundColor: V2T.surface2 },
        dim && { opacity: 0.55 },
      ]}
    >
      <View style={ss.glyphBox}>{glyph}</View>
      <View style={ss.rowText}>
        <Text style={ss.rowTitle} numberOfLines={1}>{title}</Text>
        {outsideNote ? (
          <Text style={ss.rowOutside} numberOfLines={1}>{outsideNote}</Text>
        ) : subtitle ? (
          <Text style={ss.rowSub} numberOfLines={1}>{subtitle}</Text>
        ) : null}
      </View>
      {distLabel ? <Text style={[ss.rowDist, NUM]}>{distLabel}</Text> : null}
    </Pressable>
  );
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
  const [search] = useState(() => new ServerSearch(80));
  const inputRef = useRef<TextInput>(null);

  /* mount: warm the index, load saved places, raise the keyboard */
  useEffect(() => {
    warm();
    getPlaces().then(setStore).catch(() => {});
    inputRef.current?.focus();
    return () => search.dispose();
  }, [search]);

  const loc = userLocation ?? undefined;

  const onChange = useCallback(
    (text: string) => {
      setQ(text);
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

  const pick = useCallback(
    (p: PlaceResult) => {
      Keyboard.dismiss();
      addRecent(p).then(() => getPlaces().then(setStore)).catch(() => {});
      onSelect({ type: "place", place: p });
    },
    [onSelect],
  );

  const distLabel = useCallback(
    (p: PlaceResult) => (loc ? fmtDist(distKm(p, loc)) : undefined),
    [loc],
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

  const renderPlace = (p: PlaceResult, key: string) => (
    <PlaceRow
      key={key}
      glyph={categoryGlyph(p.kind, V2T.text2)}
      title={p.name}
      subtitle={p.subtitle}
      distLabel={distLabel(p)}
      outsideNote={p.outside_ncr ? t("outsideDelhi", lang) : undefined}
      dim={p.outside_ncr}
      onPress={() => pick(p)}
    />
  );

  const actionRows = (
    <>
      <PlaceRow
        glyph={<Icon name="locate" color={V2T.accent} size={20} />}
        title={t("yourLocation", lang)}
        onPress={() => {
          Keyboard.dismiss();
          onSelect({ type: "current_location" });
        }}
      />
      <PlaceRow
        glyph={<Icon name="pin" color={V2T.text2} size={20} />}
        title={t("chooseOnMap", lang)}
        onPress={() => {
          Keyboard.dismiss();
          onSelect({ type: "choose_on_map" });
        }}
      />
    </>
  );

  return (
    <View style={ss.root}>
      {/* search bar — pill 999 (doc 03) */}
      <View style={ss.bar}>
        <Pressable onPress={onClose} hitSlop={10} accessibilityRole="button" accessibilityLabel="back" style={ss.barBtn}>
          <BackGlyph color={V2T.text2} />
        </Pressable>
        <TextInput
          ref={inputRef}
          style={ss.input}
          value={q}
          onChangeText={onChange}
          placeholder={t("searchPlaceholder", lang)}
          placeholderTextColor={V2T.text3}
          autoFocus
          autoCorrect={false}
          autoCapitalize="none"
          returnKeyType="search"
          clearButtonMode="never"
          accessibilityLabel={t("searchPlaceholder", lang)}
        />
        {q.length > 0 && (
          <Pressable
            onPress={() => onChange("")}
            hitSlop={10}
            accessibilityRole="button"
            accessibilityLabel="clear"
            style={ss.barBtn}
          >
            <Icon name="close" color={V2T.text3} size={16} />
          </Pressable>
        )}
      </View>

      <KeyboardAvoidingView
        style={ss.flex}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView
          style={ss.flex}
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={ss.listContent}
        >
          {!typing ? (
            <>
              {store.home && (
                <PlaceRow
                  glyph={<Icon name="flag" color={V2T.accent} size={20} />}
                  title={t("home", lang)}
                  subtitle={store.home.name}
                  distLabel={distLabel(store.home)}
                  onPress={() => pick(store.home!)}
                />
              )}
              {store.work && (
                <PlaceRow
                  glyph={<Icon name="flag" color={V2T.text2} size={20} />}
                  title={t("work", lang)}
                  subtitle={store.work.name}
                  distLabel={distLabel(store.work)}
                  onPress={() => pick(store.work!)}
                />
              )}
              {store.recents.length > 0 && (
                <Text style={ss.sectionLabel}>{t("recents", lang)}</Text>
              )}
              {store.recents.map((p, i) => (
                <PlaceRow
                  key={`recent-${i}`}
                  glyph={<Icon name="clock" color={V2T.text2} size={20} />}
                  title={p.name}
                  subtitle={p.subtitle}
                  distLabel={distLabel(p)}
                  outsideNote={p.outside_ncr ? t("outsideDelhi", lang) : undefined}
                  dim={p.outside_ncr}
                  onPress={() => pick(p)}
                />
              ))}
              {actionRows}
            </>
          ) : (
            <>
              {t0rows.map((p, i) => renderPlace(p, `t0-${i}`))}
              <View style={ss.hairline} />
              {tiers === null ? (
                <Text style={ss.waiting}>{t("searching", lang)}</Text>
              ) : (
                serverRows.map((p, i) => renderPlace(p, `srv-${p.tier}-${i}`))
              )}
              {actionRows}
            </>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
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
  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
      statusBarTranslucent
    >
      <View style={ss.backdrop}>
        <StatusBar style="light" />
        {visible ? (
          <SearchSheet
            onSelect={onSelect}
            onClose={onClose}
            userLocation={userLocation}
            lang={lang}
          />
        ) : null}
      </View>
    </Modal>
  );
}

export default SearchScreen;

const ss = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.35)" },
  root: {
    flex: 1,
    marginTop: Platform.select({
      ios: 48,
      android: (RNStatusBar.currentHeight ?? 24) + 8,
      default: 16,
    }),
    backgroundColor: V2T.bg,
    borderTopLeftRadius: V2Radius.sheet,
    borderTopRightRadius: V2Radius.sheet,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderColor: V2T.line,
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
    backgroundColor: V2T.surface2,
    borderRadius: V2Radius.pill,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: V2T.line,
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
  listContent: { paddingBottom: 32 },
  sectionLabel: {
    color: V2T.text3,
    fontSize: V2Type.label,
    fontWeight: "600",
    letterSpacing: 0.6,
    textTransform: "uppercase",
    marginTop: 10,
    marginBottom: 2,
    marginHorizontal: 18,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    minHeight: 54,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: V2Radius.row,
  },
  glyphBox: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: V2T.surface,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
  },
  rowText: { flex: 1, marginRight: 10 },
  rowTitle: { color: V2T.text, fontSize: V2Type.body, fontWeight: "500" },
  rowSub: { color: V2T.text2, fontSize: V2Type.label, marginTop: 1 },
  rowOutside: { color: V2T.text3, fontSize: V2Type.label, marginTop: 1 },
  rowDist: { color: V2T.text2, fontSize: V2Type.label },
  hairline: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: V2T.line,
    marginHorizontal: 14,
    marginVertical: 4,
  },
  waiting: {
    color: V2T.text3,
    fontSize: V2Type.label,
    marginHorizontal: 18,
    marginVertical: 10,
  },
});
