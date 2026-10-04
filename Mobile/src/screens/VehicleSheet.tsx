// S8 · My vehicle (docs/plan/02 §S8) — asked once, ≤3 taps, never forced.
// Step 1 is the class picker: large select-cards (glyph + label + spec
// caption) grouped when there are more than six options — your own ride /
// shared / no engine — so the wall stays scannable. Fuel + year follow as
// one-tap cards for the classes that need them. "not sure" is a first-
// class answer: it means the Delhi fleet prior and the copy says so.
// onDone receives the finished VehicleProfile; onClose means dismissed
// with nothing saved.
//
// Mount contract (integrator) — unchanged:
//   <VehicleSheet
//     visible={open}
//     lang={lang}
//     current={flow.vehicle}
//     onDone={(p) => { flow.setVehicleProfile(p); setOpen(false); }}
//     onClose={() => setOpen(false)} />
// Re-opened from the options-sheet chip via CompareSheet's onVehiclePress.
import React, { useEffect, useRef, useState } from "react";
import {
  Dimensions, Keyboard, KeyboardAvoidingView, Platform, Pressable,
  ScrollView, StyleSheet, Text, TextInput, View,
  type StyleProp, type ViewStyle,
} from "react-native";
import { V2Radius, V2T, V2Type, fam } from "../theme";
import { DYNAMIC_TYPE } from "../a11y";
import { Icon, type Glyph } from "../icons";
import { t, type Lang, type StringKey } from "../i18n/strings";
import { Sheet } from "../ui";
import {
  fuelsFor, needsFuel, needsYear, vehicleLabel,
  type Fuel, type PucInfo, type VehicleClass, type VehicleProfile, type YearBand,
} from "../store/vehicle";

type Step = "cls" | "fuel" | "year" | "puc" | "done";

/* ── i18n hand-off ────────────────────────────────────────────────────────
 * The caption/group strings below are queued for src/i18n/strings.ts as
 * the `veh_*` keys listed in the lane report. Until the table lands them
 * `tl()` renders LOCAL; once a key exists there, t() wins automatically. */
const LOCAL = {
  en: {
    veh_grp_own: "your own",
    veh_grp_shared: "shared",
    veh_grp_noengine: "no engine",
    veh_why: "your pick sharpens the “your ride puts out” numbers — saved on this phone only",
    veh_cap_car: "petrol · diesel · CNG · EV",
    veh_cap_auto: "3-wheeler · mostly CNG",
    veh_cap_bike: "scooter · motorcycle",
    veh_cap_bus: "shared ride",
    veh_cap_metro: "electric · shared",
    veh_cap_cycle: "no exhaust",
    veh_cap_walk: "no exhaust",
    veh_cap_petrol: "cars · scooters · bikes",
    veh_cap_diesel: "more fine particles",
    veh_cap_cng: "lighter exhaust",
    veh_cap_ev: "no exhaust",
    veh_cap_y_pre2010: "BS-III or older",
    veh_cap_y_2010_2016: "mostly BS III–IV",
    veh_cap_y_2017_2020: "mostly BS-IV",
    veh_cap_y_2021plus: "BS-VI era",
    veh_cap_y_notsure: "we’ll use the Delhi average",
  },
  hi: {
    veh_grp_own: "अपनी गाड़ी",
    veh_grp_shared: "साझा सवारी",
    veh_grp_noengine: "बिना इंजन",
    veh_why: "आपकी पसंद से ‘गाड़ी का धुआँ’ अनुमान सटीक होता है — सिर्फ़ इस फ़ोन पर सेव",
    veh_cap_car: "पेट्रोल · डीज़ल · CNG · EV",
    veh_cap_auto: "3-व्हीलर · ज़्यादातर CNG",
    veh_cap_bike: "स्कूटर · मोटरसाइकिल",
    veh_cap_bus: "साझा सवारी",
    veh_cap_metro: "इलेक्ट्रिक · साझा",
    veh_cap_cycle: "धुआँ नहीं",
    veh_cap_walk: "धुआँ नहीं",
    veh_cap_petrol: "कार · स्कूटर · बाइक",
    veh_cap_diesel: "ज़्यादा बारीक कण",
    veh_cap_cng: "हल्का एग्ज़ॉस्ट",
    veh_cap_ev: "धुआँ नहीं",
    veh_cap_y_pre2010: "BS-III या पुरानी",
    veh_cap_y_2010_2016: "ज़्यादातर BS III–IV",
    veh_cap_y_2017_2020: "ज़्यादातर BS-IV",
    veh_cap_y_2021plus: "BS-VI दौर",
    veh_cap_y_notsure: "दिल्ली का औसत लेंगे",
  },
} as const;
type VehKey = keyof (typeof LOCAL)["en"];
const tr = t as (k: string, l?: Lang) => string;

/* ── option model ─────────────────────────────────────────────────────────
 * Seven classes > six → grouped (doc-brief rule). Order inside a group is
 * the original chip order; grouping mirrors the follow-up questions —
 * "your own" is exactly the set that can ask fuel/year. */
type ClassOpt = { cls: VehicleClass; glyph: Glyph; key: StringKey; cap: VehKey };
const CLASS_GROUPS: { title: VehKey; items: ClassOpt[] }[] = [
  {
    title: "veh_grp_own",
    items: [
      { cls: "car", glyph: "car", key: "vehicle_car", cap: "veh_cap_car" },
      { cls: "auto", glyph: "auto", key: "vehicle_auto", cap: "veh_cap_auto" },
      { cls: "bike", glyph: "bike", key: "vehicle_bike", cap: "veh_cap_bike" },
    ],
  },
  {
    title: "veh_grp_shared",
    items: [
      { cls: "bus", glyph: "bus", key: "vehicle_bus", cap: "veh_cap_bus" },
      { cls: "metro", glyph: "metro", key: "vehicle_metro", cap: "veh_cap_metro" },
    ],
  },
  {
    title: "veh_grp_noengine",
    items: [
      { cls: "cycle", glyph: "cycle", key: "vehicle_cycle", cap: "veh_cap_cycle" },
      { cls: "walk", glyph: "walk", key: "vehicle_walk", cap: "veh_cap_walk" },
    ],
  },
];
const CLASS_COUNT = CLASS_GROUPS.reduce((n, g) => n + g.items.length, 0);
const GROUPED = CLASS_COUNT > 6;

const FUEL_ORDER: { fuel: Fuel; key: StringKey; cap: VehKey }[] = [
  { fuel: "petrol", key: "fuelPetrol", cap: "veh_cap_petrol" },
  { fuel: "diesel", key: "fuelDiesel", cap: "veh_cap_diesel" },
  { fuel: "cng", key: "fuelCNG", cap: "veh_cap_cng" },
  { fuel: "ev", key: "fuelElectric", cap: "veh_cap_ev" },
];

const YEAR_ORDER: { year: YearBand; key: StringKey; cap: VehKey }[] = [
  { year: "pre_2010", key: "yearBefore2010", cap: "veh_cap_y_pre2010" },
  { year: "y2010_2016", key: "year2010to2016", cap: "veh_cap_y_2010_2016" },
  { year: "y2017_2020", key: "vehicle_year2017to2020", cap: "veh_cap_y_2017_2020" },
  { year: "y2021_plus", key: "vehicle_year2021plus", cap: "veh_cap_y_2021plus" },
  { year: "not_sure", key: "yearNotSure", cap: "veh_cap_y_notsure" },
];

const BS_STAGES: { bs: NonNullable<PucInfo["bs"]>; key: StringKey }[] = [
  { bs: "bs3", key: "puc_bs3" },
  { bs: "bs4", key: "puc_bs4" },
  { bs: "bs6", key: "puc_bs6" },
];

/* The certificate step exists only for an owned motor vehicle —
 * car/bike/auto, any tailpipe. EVs have no PUC readings, shared and
 * non-motor classes never reach the fuel/year questions at all. */
const pucEligible = (cls: VehicleClass | null, fuel: Fuel | null) =>
  !!cls && needsYear(cls) && fuel !== "ev";

/* the PUC readings are fuel-specific: petrol & CNG certificates print
 * CO% + HC ppm, diesel prints smoke-opacity %. (Auto's fuel is unasked —
 * overwhelmingly CNG — so it gets the gaseous-fuel fields too.) */
const pucFieldKeys = (fuel: Fuel | null) =>
  fuel === "diesel"
    ? (["smoke_pct"] as const)
    : (["co_pct", "hc_ppm"] as const);

const PUC_LIMITS: Record<"co_pct" | "hc_ppm" | "smoke_pct", [number, number]> = {
  co_pct: [0, 20], hc_ppm: [0, 20000], smoke_pct: [0, 100],
};

const parseReading = (s: string, field: keyof typeof PUC_LIMITS): number | null => {
  const v = parseFloat(s);
  const [lo, hi] = PUC_LIMITS[field];
  return Number.isFinite(v) && v >= lo && v <= hi ? v : null;
};

/** One large select-card: optional glyph, label + spec caption, and a
 *  radio dot so the selected state reads even without colour. ≥44pt. */
function OptionCard({ glyph, label, caption, active, onPress, lang, style }: {
  glyph?: Glyph; label: string; caption?: string; active: boolean;
  onPress: () => void; lang: Lang; style?: StyleProp<ViewStyle>;
}) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button"
      accessibilityState={{ selected: active }}
      accessibilityLabel={caption ? `${label}, ${caption}` : label}
      style={({ pressed }) => [s.card, active && s.cardOn, pressed && { opacity: 0.6 }, style]}>
      {glyph ? (
        <Icon name={glyph} color={active ? V2T.accent : V2T.text2} size={24} filled={active} />
      ) : null}
      <View style={s.cardBody}>
        <Text {...DYNAMIC_TYPE} style={[s.cardTxt, { fontFamily: fam(lang, "med") }, active && { color: V2T.accent }]}
          numberOfLines={1}>
          {label}
        </Text>
        {caption ? (
          /* 2-col cards truncate 'petrol · diesel · CNG · EV' mid-list —
             wrap to a second line, shrink as the last resort (forensic) */
          <Text {...DYNAMIC_TYPE} style={[s.cardCap, { fontFamily: fam(lang, "reg") }]}
            numberOfLines={2} adjustsFontSizeToFit minimumFontScale={0.8}>
            {caption}
          </Text>
        ) : null}
      </View>
      <View style={[s.radio, active && s.radioOn]}>
        {active ? <View style={s.radioDot} /> : null}
      </View>
    </Pressable>
  );
}

/** Pair up options into two-column rows (odd one out stretches a row). */
function pairs<T>(items: T[]): T[][] {
  const rows: T[][] = [];
  for (let i = 0; i < items.length; i += 2) rows.push(items.slice(i, i + 2));
  return rows;
}

function Wizard({ lang, current, onDone, onClose }: {
  lang: Lang;
  current: VehicleProfile | null;
  onDone: (p: VehicleProfile) => void;
  onClose: () => void;
}) {
  const [step, setStep] = useState<Step>("cls");
  const [cls, setCls] = useState<VehicleClass | null>(current?.cls ?? null);
  const [fuel, setFuel] = useState<Fuel | null>(current?.fuel ?? null);
  const [year, setYear] = useState<YearBand | null>(current?.year ?? null);
  const [saved, setSaved] = useState<VehicleProfile | null>(null);
  /* PUC answers — prefilled when a certificate was saved before (editing
     keeps its values; a cleared field saved back wipes that field). */
  const [pucBs, setPucBs] = useState<PucInfo["bs"]>(current?.puc?.bs ?? null);
  const [pucCo, setPucCo] = useState(current?.puc?.co_pct != null ? String(current.puc.co_pct) : "");
  const [pucHc, setPucHc] = useState(current?.puc?.hc_ppm != null ? String(current.puc.hc_ppm) : "");
  const [pucSmoke, setPucSmoke] = useState(current?.puc?.smoke_pct != null ? String(current.puc.smoke_pct) : "");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  /** i18n hand-off: real table key wins, LOCAL until it lands (see top). */
  const tl = (k: VehKey) => tr(k, lang) || LOCAL[lang][k] || LOCAL.en[k];

  const finish = (p: VehicleProfile) => {
    setSaved(p);
    setStep("done");
    // the result line stays up ~1s (doc S8) — then the answer leaves
    timer.current = setTimeout(() => onDone(p), 1000);
  };

  const pickClass = (c: VehicleClass) => {
    setCls(c);
    if (needsFuel(c)) setStep("fuel");
    else if (needsYear(c)) setStep("year");
    else finish({ cls: c, fuel: null, year: null });   // 1 tap for shared / non-motor
  };
  const pickFuel = (f: Fuel) => {
    setFuel(f);
    // every fuel-taking class (car, bike) also takes the year question
    setStep("year");
  };
  const pickYear = (y: YearBand) => {
    setYear(y);
    if (pucEligible(cls, fuel)) setStep("puc");
    else finish({ cls: cls!, fuel, year: y });
  };

  /* PUC step: "save" persists whatever was entered (all-empty → no cert);
     "skip" leaves the previously saved certificate untouched (or none). */
  const finishPuc = (save: boolean) => {
    let puc: PucInfo | null = null;
    if (save) {
      const entered: PucInfo = {
        bs: pucBs,
        co_pct: parseReading(pucCo, "co_pct"),
        hc_ppm: parseReading(pucHc, "hc_ppm"),
        smoke_pct: parseReading(pucSmoke, "smoke_pct"),
      };
      if (entered.bs != null || entered.co_pct != null ||
          entered.hc_ppm != null || entered.smoke_pct != null) puc = entered;
    } else {
      puc = current?.puc ?? null;
    }
    finish({ cls: cls!, fuel, year: year!, puc });
  };

  const back = step === "fuel" || step === "year" || step === "puc"
    ? () => setStep(
        step === "fuel" ? "cls"
        : step === "year" ? (needsFuel(cls!) ? "fuel" : "cls")
        : "year",
      )
    : null;

  /* progress dots — the path length is only known once a class is picked
   * (car/bike = 4 questions incl. PUC, auto = 3, shared/non-motor = 1). */
  const totalQ = cls
    ? 1 + (needsFuel(cls) ? 1 : 0) + (needsYear(cls) ? 1 : 0)
      + (pucEligible(cls, fuel) ? 1 : 0)
    : 0;
  const stepIdx = step === "cls" ? 0
    : step === "fuel" ? 1
    : step === "year" ? totalQ - (pucEligible(cls, fuel) ? 2 : 1)
    : totalQ - 1;   // puc / done — the last dot

  const classCard = ({ cls: c, glyph, key, cap }: ClassOpt) => (
    <OptionCard key={c} glyph={glyph} label={t(key, lang)} caption={tl(cap)}
      active={cls === c} onPress={() => pickClass(c)} lang={lang} style={s.cardHalf} />
  );

  return (
    <Sheet detent="half" onClose={onClose} style={s.sheet} lang={lang}>
      {step === "done" ? (
        <View style={s.doneWrap}>
          <Text {...DYNAMIC_TYPE} style={[s.doneTxt, { fontFamily: fam(lang, "med") }]}>{t("vehicleDone", lang)}</Text>
          {saved ? (
            <Text {...DYNAMIC_TYPE} style={[s.doneSub, { fontFamily: fam(lang, "reg") }]}>
              {vehicleLabel(saved, lang)}{saved.puc ? ` · ${t("puc_badge", lang)}` : ""}
            </Text>
          ) : null}
        </View>
      ) : (
        <>
          <View style={s.headRow}>
            <Text {...DYNAMIC_TYPE} style={[s.q, { fontFamily: fam(lang, "semi") }]}>
              {t(step === "cls" ? "vehicleQ1" : step === "fuel" ? "vehicleQ2"
                : step === "puc" ? "puc_title" : "vehicleQ3", lang)}
            </Text>
            {totalQ > 1 && (
              <View style={s.dots} accessible={false} importantForAccessibility="no">
                {Array.from({ length: totalQ }).map((_, i) => (
                  <View key={i} style={[s.dot, i <= stepIdx && s.dotOn]} />
                ))}
              </View>
            )}
          </View>
          {/* honest caption: the pick refines the emissions estimate —
              plain language, on-device only */}
          {step === "cls" && (
            <Text {...DYNAMIC_TYPE} style={[s.why, { fontFamily: fam(lang, "reg") }]}>{tl("veh_why")}</Text>
          )}
          {/* the certificate's job in plain words — grounded in YOUR
              vehicle, not the fleet average */}
          {step === "puc" && (
            <Text {...DYNAMIC_TYPE} style={[s.why, { fontFamily: fam(lang, "reg") }]}>
              {t("puc_helper", lang)}
            </Text>
          )}
          <ScrollView style={s.scroll} contentContainerStyle={s.scrollIn}
            showsVerticalScrollIndicator={false}
            /* a tap must still reach the cards while the PUC keyboard is
               up — 'handled' eats taps only when they would dismiss it */
            keyboardShouldPersistTaps="handled">
            {step === "cls" && (GROUPED ? (
              CLASS_GROUPS.map((g) => (
                <View key={g.title}>
                  <Text {...DYNAMIC_TYPE} style={[s.grp, { fontFamily: fam(lang, "med") }]}>{tl(g.title)}</Text>
                  {pairs(g.items).map((row, ri) => (
                    <View key={ri} style={s.gridRow}>
                      {row.map(classCard)}
                      {row.length === 1 ? <View style={s.cardHalf} /> : null}
                    </View>
                  ))}
                </View>
              ))
            ) : (
              pairs(CLASS_GROUPS.flatMap((g) => g.items)).map((row, ri) => (
                <View key={ri} style={s.gridRow}>{row.map(classCard)}</View>
              ))
            ))}
            {step === "fuel" && cls &&
              pairs(FUEL_ORDER.filter(({ fuel: f }) => fuelsFor(cls).includes(f)))
                .map((row, ri) => (
                  <View key={ri} style={s.gridRow}>
                    {row.map(({ fuel: f, key, cap }) => (
                      <OptionCard key={f} label={t(key, lang)} caption={tl(cap)}
                        active={fuel === f} onPress={() => pickFuel(f)} lang={lang}
                        style={s.cardHalf} />
                    ))}
                    {row.length === 1 ? <View style={s.cardHalf} /> : null}
                  </View>
                ))}
            {step === "year" &&
              YEAR_ORDER.map(({ year: y, key, cap }) => (
                <View key={y} style={s.listRow}>
                  <OptionCard label={t(key, lang)} caption={tl(cap)}
                    active={year === y} onPress={() => pickYear(y)} lang={lang} />
                </View>
              ))}
            {step === "puc" && (
              <View>
                <Text {...DYNAMIC_TYPE} style={[s.grp, { fontFamily: fam(lang, "med") }]}>
                  {t("puc_bsQ", lang)}
                </Text>
                <View style={s.gridRow}>
                  {BS_STAGES.map(({ bs, key }) => (
                    <OptionCard key={bs} label={t(key, lang)}
                      active={pucBs === bs}
                      onPress={() => setPucBs((cur) => (cur === bs ? null : bs))}
                      lang={lang} style={s.cardHalf} />
                  ))}
                </View>
                {/* measured readings — the fields the certificate carries
                    for this fuel; every one optional */}
                {pucFieldKeys(fuel).map((field) => {
                  const val = field === "co_pct" ? pucCo : field === "hc_ppm" ? pucHc : pucSmoke;
                  const set = field === "co_pct" ? setPucCo : field === "hc_ppm" ? setPucHc : setPucSmoke;
                  const labelKey = field === "co_pct" ? "puc_co" : field === "hc_ppm" ? "puc_hc" : "puc_smoke";
                  const hintKey = field === "co_pct" ? "puc_coHint" : field === "hc_ppm" ? "puc_hcHint" : "puc_smokeHint";
                  return (
                    <View key={field} style={s.fieldRow}>
                      <Text {...DYNAMIC_TYPE} style={[s.fieldLabel, { fontFamily: fam(lang, "med") }]}>
                        {t(labelKey, lang)}
                      </Text>
                      <TextInput
                        value={val}
                        onChangeText={set}
                        placeholder="—"
                        placeholderTextColor={V2T.text3}
                        keyboardType="decimal-pad"
                        maxLength={6}
                        accessibilityLabel={`${t(labelKey, lang)} — ${t(hintKey, lang)}`}
                        style={[s.input, { fontFamily: fam(lang, "reg") }]}
                      />
                      <Text {...DYNAMIC_TYPE} style={[s.fieldHint, { fontFamily: fam(lang, "reg") }]}>
                        {t(hintKey, lang)}
                      </Text>
                    </View>
                  );
                })}
              </View>
            )}
          </ScrollView>
          <View style={s.foot}>
            {back ? (
              <Pressable onPress={back} hitSlop={8} accessibilityRole="button"
                accessibilityLabel={t("vehicleQ_back", lang)} style={s.footBtn}>
                <Text {...DYNAMIC_TYPE} style={[s.footTxt, { fontFamily: fam(lang, "med") }]}>{t("vehicleQ_back", lang)}</Text>
              </Pressable>
            ) : <View />}
            <View style={s.footRight}>
              {step === "puc" && (
                <Pressable onPress={() => finishPuc(true)} hitSlop={8} accessibilityRole="button"
                  accessibilityLabel={t("receipt_save", lang)} style={s.footBtn}>
                  <Text {...DYNAMIC_TYPE} style={[s.footTxtAccent, { fontFamily: fam(lang, "semi") }]}>
                    {t("receipt_save", lang)}
                  </Text>
                </Pressable>
              )}
              {/* never forced — dismissing keeps the Delhi fleet prior;
                  on the PUC step skip finishes with whatever was saved
                  before (or no certificate) */}
              <Pressable
                onPress={step === "puc" ? () => finishPuc(false) : onClose}
                hitSlop={8} accessibilityRole="button"
                accessibilityLabel={t("vehicleQ_skip", lang)} style={s.footBtn}>
                <Text {...DYNAMIC_TYPE} style={[s.footTxt, { fontFamily: fam(lang, "med") }]}>{t("vehicleQ_skip", lang)}</Text>
              </Pressable>
            </View>
          </View>
        </>
      )}
    </Sheet>
  );
}

/** <VehicleSheet visible lang current onDone onClose/> — see header.
 *  Plain overlay, not RN Modal: a Modal window ignores the activity's
 *  adjustResize, so the decimal keyboard covered the PUC readings while
 *  typing. Anchored in the main window the sheet rides above the IME,
 *  and hardware BACK reaches App.tsx's dispatcher (vehicleOpen) — the
 *  same path Modal's onRequestClose used to take. */
export function VehicleSheet({
  visible, lang = "en", current = null, onDone, onClose,
}: {
  visible: boolean;
  lang?: Lang;
  current?: VehicleProfile | null;
  onDone: (p: VehicleProfile) => void;
  onClose: () => void;
}) {
  /* closing while a PUC field holds focus leaves the IME up over the
     compare sheet (unmount does not ask the IME to hide) — dismiss on
     every visible→false edge so save / skip / ✕ / BACK all end quiet */
  useEffect(() => {
    if (!visible) Keyboard.dismiss();
  }, [visible]);

  if (!visible) return null;
  return (
    <View style={s.overlay} pointerEvents="box-none">
      <View style={s.backdrop} />
      {/* the overlay pattern alone isn't enough on this build — the
          window does not resize for the IME, so the sheet's bottom
          edge sat under the decimal keyboard (same KAV mechanism
          SearchScreen relies on) */}
      <KeyboardAvoidingView
        style={s.kav}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
      >
        <Wizard lang={lang} current={current} onDone={onDone} onClose={onClose} />
      </KeyboardAvoidingView>
    </View>
  );
}

export default VehicleSheet;

const s = StyleSheet.create({
  overlay: { position: "absolute", top: 0, left: 0, right: 0, bottom: 0 },
  backdrop: { position: "absolute", top: 0, left: 0, right: 0, bottom: 0, backgroundColor: V2T.scrim },
  kav: { flex: 1 },
  /* half-detent (~50% viewport) crops the grouped class grid's last row
     on first paint — cap at 72% so cycle/walk is fully visible without
     a full-screen takeover. */
  sheet: { position: "absolute", bottom: 0, left: 0, right: 0,
           maxHeight: Math.round(Dimensions.get("window").height * 0.72) },
  headRow: { flexDirection: "row", alignItems: "center", paddingRight: 20 },
  q: { flex: 1, fontSize: V2Type.body, color: V2T.text, paddingLeft: 20, paddingRight: 8, paddingTop: 4, paddingBottom: 10 },
  dots: { flexDirection: "row", gap: 5, paddingBottom: 8 },
  dot: { width: 5, height: 5, borderRadius: 2.5, backgroundColor: V2T.line },
  dotOn: { backgroundColor: V2T.accent },
  why: {
    fontSize: V2Type.label, color: V2T.text3,
    paddingHorizontal: 20, paddingBottom: 10, marginTop: -4,
  },
  scroll: { flexGrow: 0, flexShrink: 1 },
  scrollIn: { paddingHorizontal: 16, paddingBottom: 6 },
  grp: {
    fontSize: V2Type.label, color: V2T.text3,
    paddingHorizontal: 4, marginTop: 4, marginBottom: 6,
  },
  gridRow: { flexDirection: "row", gap: 8, marginBottom: 8 },
  listRow: { marginBottom: 8 },
  card: {
    flexDirection: "row", alignItems: "center", gap: 10,
    backgroundColor: V2T.surface2, borderRadius: V2Radius.row,
    borderWidth: 1, borderColor: V2T.line,
    paddingHorizontal: 12, paddingVertical: 10, minHeight: 56,
  },
  cardHalf: { flex: 1 },
  /* accentTint bg + accent label was ~3.5:1 — selected card goes to
     surface so the accent label (4.51:1 on white) stays readable; the
     accent border + radio carry the selected signal */ cardOn: { borderColor: V2T.accent, backgroundColor: V2T.surface },
  cardBody: { flex: 1, gap: 1 },
  cardTxt: { fontSize: V2Type.secondary, color: V2T.text },
  cardCap: { fontSize: V2Type.label, color: V2T.text3 },
  radio: {
    width: 18, height: 18, borderRadius: 9,
    borderWidth: 1.5, borderColor: V2T.line,
    alignItems: "center", justifyContent: "center",
  },
  radioOn: { borderColor: V2T.accent },
  radioDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: V2T.accent },
  foot: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    paddingHorizontal: 20, paddingTop: 4, paddingBottom: 12,
  },
  footBtn: { minHeight: 44, justifyContent: "center", paddingHorizontal: 4 },
  footRight: { flexDirection: "row", alignItems: "center", gap: 16 },
  footTxt: { fontSize: V2Type.label, color: V2T.text3 },
  footTxtAccent: { fontSize: V2Type.secondary, color: V2T.accent },
  /* PUC certificate fields — label + numeric input + hint, one row each */
  fieldRow: { marginBottom: 12 },
  fieldLabel: { fontSize: V2Type.label, color: V2T.text2, marginBottom: 4, paddingHorizontal: 4 },
  input: {
    backgroundColor: V2T.surface2, borderRadius: V2Radius.row,
    borderWidth: 1, borderColor: V2T.line,
    paddingHorizontal: 12, paddingVertical: 9,
    fontSize: V2Type.secondary, color: V2T.text, minHeight: 44,
  },
  fieldHint: { fontSize: V2Type.label, color: V2T.text3, marginTop: 4, paddingHorizontal: 4 },
  doneWrap: { paddingHorizontal: 20, paddingVertical: 30, alignItems: "center" },
  doneTxt: { fontSize: V2Type.secondary, color: V2T.text, textAlign: "center" },
  doneSub: { fontSize: V2Type.label, color: V2T.text3, marginTop: 8 },
});
