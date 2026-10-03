/** Locate button — bottom-right round control (doc 02 §S1).
 * Active (following) = filled accent puck. */
import React from "react";
import { MapButton } from "../../ui";
import { t, type Lang } from "../../i18n/strings";

export function LocateButton({ active, onPress, lang }: { active: boolean; onPress: () => void; lang: Lang }) {
  return <MapButton glyph="locate" active={active} onPress={onPress} label={t("a11yLocate", lang)} />;
}
