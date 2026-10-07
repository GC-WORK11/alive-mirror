/// <reference types="node" />
/**
 * Gazetteer-tail localization (testday-ios finding 3) — "fountain" and
 * "muslim place of worship" bypassed localizeKind() raw: English kind
 * strings leaked into Hindi search subtitles. This pins the fixed
 * behavior: normalization (case, underscores), the "kind · anchor"
 * compound split, the synonym map, and the localized generic fallback
 * for the corpus's uncharted noise tail.
 *
 * Parked in the store runner — it's the harness whose stubs already
 * load i18n/strings (daylog imports it for modeLabel/placeNameLabel).
 * Run: cd Mobile && node src/store/test-runner.mjs
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { localizeKind } from "../i18n/strings";

describe("localizeKind — the reported leaks", () => {
  it("muslim place of worship → मस्जिद, every wire form", () => {
    // raw corpus form (underscores), cleanSubtitle form (spaces),
    // and the capitalized server/recents form all land on the key
    assert.equal(localizeKind("muslim_place_of_worship", "hi"), "मस्जिद");
    assert.equal(localizeKind("muslim place of worship", "hi"), "मस्जिद");
    assert.equal(localizeKind("Muslim place of worship", "hi"), "मस्जिद");
  });

  it("fountain → फ़व्वारा", () => {
    assert.equal(localizeKind("fountain", "hi"), "फ़व्वारा");
    assert.equal(localizeKind("fountain", "en"), "fountain");
  });

  it("the rest of the worship family localizes too", () => {
    assert.equal(localizeKind("hindu place of worship", "hi"), "मंदिर");
    assert.equal(localizeKind("christian place of worship", "hi"), "चर्च");
    assert.equal(localizeKind("sikh place of worship", "hi"), "गुरुद्वारा");
  });
});

describe("localizeKind — normalization and compounds", () => {
  it("is case- and underscore-insensitive on known kinds", () => {
    assert.equal(localizeKind("Mosque", "hi"), "मस्जिद");
    assert.equal(localizeKind("railway_station", "hi"), "रेलवे स्टेशन");
  });

  it("localizes the kind inside 'kind · anchor' without touching the anchor", () => {
    assert.equal(localizeKind("mosque · Hauz Khas", "hi"), "मस्जिद · Hauz Khas");
    assert.equal(localizeKind("mosque · Hauz Khas", "en"), "mosque · Hauz Khas");
  });

  it("an all-name compound passes through verbatim", () => {
    assert.equal(localizeKind("Rajiv Chowk · Connaught Place", "hi"),
      "Rajiv Chowk · Connaught Place");
  });
});

describe("localizeKind — the tail's fallback honesty", () => {
  it("an uncharted lowercase kind-token becomes the generic place label in hi", () => {
    // corpus noise like "pyrotechnics"/"glaziery" — not worth a key,
    // but a Devanagari subtitle stays Devanagari
    assert.equal(localizeKind("pyrotechnics", "hi"), "जगह");
  });

  it("the same unknown stays honest English in en", () => {
    assert.equal(localizeKind("pyrotechnics", "en"), "pyrotechnics");
  });

  it("an unmatched capitalized string is real info — never flattened", () => {
    // address/name fragments carry meaning a generic "place" would erase
    assert.equal(localizeKind("Block C, Noida", "hi"), "Block C, Noida");
  });
});
