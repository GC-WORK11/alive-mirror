/** ExploreSheet — the 'stay & play' settle phase router for the search
 *  flow's explore intents (hackathon features 2 & 3). Each ask is a
 *  dedicated component now:
 *
 *    stays    — StaysSheet: lodging rows near the anchor on warm
 *               hairlines, each scored by the live-anchored next-24 h
 *               forecast AT ITS OWN coordinates, ranked lightest-first.
 *               A tap drops the stay on the air map.
 *    playtime — PlaytimeSheet: the rolling next-24 h curve as a banded
 *               bar strip, the lightest window in words, the heaviest
 *               callout, the server's verdict.
 *
 *  Every number is the endpoint's; empty/sparse/thin reads are said,
 *  never filled. */
import React from "react";
import type { ExploreAnchor, ExploreMode } from "../../api/explore";
import type { Lang } from "../../i18n/strings";
import { StaysSheet } from "./StaysSheet";
import { PlaytimeSheet } from "./PlaytimeSheet";

type Props = {
  mode: ExploreMode;
  anchor: ExploreAnchor;
  lang: Lang;
  onModeChange: (m: ExploreMode) => void;
  onPin: (p: { lat: number; lon: number; name: string }) => void;
  onClose: () => void;
};

export function ExploreSheet({ mode, anchor, lang, onModeChange, onPin, onClose }: Props) {
  return mode === "stays" ? (
    <StaysSheet anchor={anchor} lang={lang}
      onModeChange={onModeChange} onPin={onPin} onClose={onClose} />
  ) : (
    <PlaytimeSheet anchor={anchor} lang={lang}
      onModeChange={onModeChange} onClose={onClose} />
  );
}
