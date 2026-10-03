/** Layers button — bottom-left round control (doc 02 §S1). Opens the
 * layers sheet; active dot state when any optional layer is on. */
import React from "react";
import { MapButton } from "../../ui";
import { t, type Lang } from "../../i18n/strings";

export function LayersButton({ anyOn, onPress, lang }: { anyOn: boolean; onPress: () => void; lang: Lang }) {
  return <MapButton glyph="layers" active={anyOn} onPress={onPress} label={t("a11yLayers", lang)} />;
}
