// S8 · My vehicle (docs/plan/02 §S8) — asked once, ≤3 taps, never forced.
// class chip → fuel (car/bike only) → year band (car/bike/auto) → done.
// "not sure" is a first-class answer: it means the Delhi fleet prior and
// we say so. onDone receives the finished VehicleProfile; onClose means
// dismissed with nothing saved.
//
// Mount contract (integrator):
//   <VehicleSheet
//     visible={open}
//     lang={lang}
//     current={flow.vehicle}
//     onDone={(p) => { flow.setVehicleProfile(p); setOpen(false); }}
//     onClose={() => setOpen(false)} />
// Re-opened from the options-sheet chip via CompareSheet's onVehiclePress.
import React, { useEffect, useRef, useState } from "react";
import { Modal, Pressable, StyleSheet, Text, View } from "react-native";
import { V2Radius, V2T, V2Type, fam } from "../theme";
import { Icon, type Glyph } from "../icons";
import { t, type Lang, type StringKey } from "../i18n/strings";
import { Sheet } from "../ui";
import {
  fuelsFor, needsFuel, needsYear, vehicleLabel,
  type Fuel, type VehicleClass, type VehicleProfile, type YearBand,
} from "../store/vehicle";

type Step = "cls" | "fuel" | "year" | "done";

const CLASS_ORDER: { cls: VehicleClass; glyph: Glyph; key: StringKey }[] = [
  { cls: "car", glyph: "car", key: "vehicle_car" },
  { cls: "auto", glyph: "auto", key: "vehicle_auto" },
  { cls: "bike", glyph: "bike", key: "vehicle_bike" },
  { cls: "bus", glyph: "bus", key: "vehicle_bus" },
  { cls: "metro", glyph: "metro", key: "vehicle_metro" },
  { cls: "cycle", glyph: "cycle", key: "vehicle_cycle" },
  { cls: "walk", glyph: "walk", key: "vehicle_walk" },
];

const FUEL_ORDER: { fuel: Fuel; key: StringKey }[] = [
  { fuel: "petrol", key: "fuelPetrol" },
  { fuel: "diesel", key: "fuelDiesel" },
  { fuel: "cng", key: "fuelCNG" },
  { fuel: "ev", key: "fuelElectric" },
];

const YEAR_ORDER: { year: YearBand; key: StringKey }[] = [
  { year: "pre_2010", key: "yearBefore2010" },
  { year: "y2010_2016", key: "year2010to2016" },
  { year: "y2017_2020", key: "vehicle_year2017to2020" },
  { year: "y2021_plus", key: "vehicle_year2021plus" },
  { year: "not_sure", key: "yearNotSure" },
];

function Chip({ label, glyph, active, onPress, lang }: {
  label: string; glyph?: Glyph; active: boolean; onPress: () => void; lang: Lang;
}) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button"
      style={({ pressed }) => [s.chip, active && s.chipOn, pressed && { opacity: 0.6 }]}>
      {glyph ? (
        <Icon name={glyph} color={active ? V2T.accent : V2T.text2} size={22} filled={active} />
      ) : null}
      <Text style={[s.chipTxt, { fontFamily: fam(lang, "med") }, active && { color: V2T.accent }]}>
        {label}
      </Text>
    </Pressable>
  );
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
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

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
  const pickYear = (y: YearBand) => { setYear(y); finish({ cls: cls!, fuel, year: y }); };

  const back = step === "fuel" || step === "year"
    ? () => setStep(step === "fuel" ? "cls" : needsFuel(cls!) ? "fuel" : "cls")
    : null;

  return (
    <Sheet detent="half" onClose={onClose} style={s.sheet} lang={lang}>
      {step === "done" ? (
        <View style={s.doneWrap}>
          <Text style={[s.doneTxt, { fontFamily: fam(lang, "med") }]}>{t("vehicleDone", lang)}</Text>
          {saved ? (
            <Text style={[s.doneSub, { fontFamily: fam(lang, "reg") }]}>{vehicleLabel(saved, lang)}</Text>
          ) : null}
        </View>
      ) : (
        <>
          <Text style={[s.q, { fontFamily: fam(lang, "semi") }]}>
            {t(step === "cls" ? "vehicleQ1" : step === "fuel" ? "vehicleQ2" : "vehicleQ3", lang)}
          </Text>
          <View style={s.chips}>
            {step === "cls" && CLASS_ORDER.map(({ cls: c, glyph, key }) => (
              <Chip key={c} label={t(key, lang)} glyph={glyph}
                active={cls === c} onPress={() => pickClass(c)} lang={lang} />
            ))}
            {step === "fuel" && cls &&
              FUEL_ORDER.filter(({ fuel: f }) => fuelsFor(cls).includes(f)).map(({ fuel: f, key }) => (
                <Chip key={f} label={t(key, lang)}
                  active={fuel === f} onPress={() => pickFuel(f)} lang={lang} />
              ))}
            {step === "year" &&
              YEAR_ORDER.map(({ year: y, key }) => (
                <Chip key={y} label={t(key, lang)}
                  active={year === y} onPress={() => pickYear(y)} lang={lang} />
              ))}
          </View>
          <View style={s.foot}>
            {back ? (
              <Pressable onPress={back} hitSlop={8} accessibilityRole="button">
                <Text style={[s.footTxt, { fontFamily: fam(lang, "med") }]}>{t("vehicleQ_back", lang)}</Text>
              </Pressable>
            ) : <View />}
            {/* never forced — dismissing keeps the Delhi fleet prior */}
            <Pressable onPress={onClose} hitSlop={8} accessibilityRole="button">
              <Text style={[s.footTxt, { fontFamily: fam(lang, "med") }]}>{t("vehicleQ_skip", lang)}</Text>
            </Pressable>
          </View>
        </>
      )}
    </Sheet>
  );
}

/** <VehicleSheet visible lang current onDone onClose/> — see header. */
export function VehicleSheet({
  visible, lang = "en", current = null, onDone, onClose,
}: {
  visible: boolean;
  lang?: Lang;
  current?: VehicleProfile | null;
  onDone: (p: VehicleProfile) => void;
  onClose: () => void;
}) {
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={s.backdrop}>
        <View style={{ flex: 1 }} />
        {visible ? (
          <Wizard lang={lang} current={current} onDone={onDone} onClose={onClose} />
        ) : null}
      </View>
    </Modal>
  );
}

export default VehicleSheet;

const s = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.4)" },
  sheet: { position: "absolute", bottom: 0, left: 0, right: 0 },
  q: { fontSize: V2Type.body, color: V2T.text, paddingHorizontal: 20, paddingTop: 4, paddingBottom: 12 },
  chips: {
    flexDirection: "row", flexWrap: "wrap", gap: 8,
    paddingHorizontal: 16, paddingBottom: 8,
  },
  chip: {
    flexDirection: "row", alignItems: "center", gap: 8,
    backgroundColor: V2T.surface2, borderRadius: V2Radius.pill,
    paddingHorizontal: 16, paddingVertical: 11,
    borderWidth: 1, borderColor: V2T.line,
  },
  chipOn: { borderColor: V2T.accent, backgroundColor: "rgba(76,141,255,0.12)" },
  chipTxt: { fontSize: V2Type.secondary, color: V2T.text },
  foot: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    paddingHorizontal: 20, paddingTop: 6, paddingBottom: 14,
  },
  footTxt: { fontSize: V2Type.label, color: V2T.text3 },
  doneWrap: { paddingHorizontal: 20, paddingVertical: 30, alignItems: "center" },
  doneTxt: { fontSize: V2Type.secondary, color: V2T.text, textAlign: "center" },
  doneSub: { fontSize: V2Type.label, color: V2T.text3, marginTop: 8 },
});
