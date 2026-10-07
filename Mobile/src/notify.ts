/** Local notifications — the departure ping + the morning "cleanest window"
 *  brief (docs/plan/02: consumer voice, no jargon, en+hi via i18n).
 *
 *  Audited against expo-notifications v57:
 *   - channels are created before the permission prompt (Android 13 won't
 *     show it until at least one channel exists)
 *   - getPermissionsAsync is checked before requestPermissionsAsync so we
 *     never re-fire a system dialog the user already answered
 *   - every schedule call returns the notification id or null — callers get
 *     an honest boolean, never a thrown rejection
 *   - one pending notification per purpose: fixed identifiers, cancelled
 *     before re-arming, so repeated arming can't stack pings
 *   - fire times are clamped out of quiet hours (settings may carry
 *     quietStart/quietEnd hour keys; 22→7 until the settings lane adds them)
 *
 *  Reboot: RECEIVE_BOOT_COMPLETED is auto-added by the library's manifest and
 *  its own receiver re-arms scheduled notifications — no plugin needed.
 *  Exact-time delivery on Android 12+ needs SCHEDULE_EXACT_ALARM in
 *  app.json android.permissions — flagged in docs/plan/notifications.md. */
import * as Notifications from "expo-notifications";
import { Platform } from "react-native";
import { feltKeyForBand, t, type Lang, type StringKey } from "./i18n/strings";
import { loadSettings, type ShellSettings } from "./components/shell/settings";

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: false,
    shouldSetBadge: false,
  }),
});

/* ---- channels: one per purpose so each can be muted separately in system
   settings. Names go through i18n — Android shows them in Settings → Apps →
   Notifications. (The OS keeps the name from the first creation per id.) ---- */
const CH_DEPARTURE = "departures";
const CH_BRIEF = "daily-brief";
const CH_EVENTS = "air-events";

async function ensureChannels(lang: Lang): Promise<void> {
  if (Platform.OS !== "android") return;
  // leave-time ping the user asked for — worth a heads-up
  await Notifications.setNotificationChannelAsync(CH_DEPARTURE, {
    name: t("notify_chan_departure", lang),
    importance: Notifications.AndroidImportance.HIGH,
    sound: "default",
    enableVibrate: true,
    vibrationPattern: [0, 250, 250, 250],
  });
  // ambient morning info — silent, shade-only
  await Notifications.setNotificationChannelAsync(CH_BRIEF, {
    name: t("notify_chan_brief", lang),
    importance: Notifications.AndroidImportance.LOW,
    sound: null,
    enableVibrate: false,
  });
  // real air events (fires building, band crossings, clean windows) —
  // heads-up like the departure ping; the per-kind settings toggles are
  // the user's volume control on what reaches the shade
  await Notifications.setNotificationChannelAsync(CH_EVENTS, {
    name: t("notify_chan_events", lang),
    importance: Notifications.AndroidImportance.HIGH,
    sound: "default",
    enableVibrate: true,
    vibrationPattern: [0, 250, 250, 250],
  });
}

/* ---- prefs: lang + quiet hours, read from the settings file each arm so a
   language or quiet-hour change applies to the next scheduled ping. The
   quiet keys are additive to ShellSettings — loadSettings spreads unknown
   keys from the JSON, so they take effect the day the settings lane adds
   them; defaults hold until then. ---- */
const QUIET = { start: 22, end: 7 };         // hours 0–23; start === end disables
const MAX_QUIET_SHIFT_MS = 2 * 60 * 60 * 1000;

type Prefs = { lang: Lang; qStart: number; qEnd: number };

async function prefs(): Promise<Prefs> {
  try {
    const s = (await loadSettings()) as ShellSettings & {
      quietStart?: number;
      quietEnd?: number;
    };
    const hr = (v: unknown, d: number) =>
      typeof v === "number" && v >= 0 && v <= 23 ? Math.floor(v) : d;
    return {
      lang: s.lang === "hi" ? "hi" : "en",
      qStart: hr(s.quietStart, QUIET.start),
      qEnd: hr(s.quietEnd, QUIET.end),
    };
  } catch {
    return { lang: "en", qStart: QUIET.start, qEnd: QUIET.end };
  }
}

const inQuiet = (d: Date, s: number, e: number): boolean => {
  if (s === e) return false;                  // quiet hours disabled
  const h = d.getHours() + d.getMinutes() / 60;
  return s < e ? h >= s && h < e : h >= s || h < e;
};

/** If `d` lands inside quiet hours, push it to the quiet end (same day if
    still ahead, else tomorrow). Overnight windows (22→7) handled both ways. */
const outOfQuiet = (d: Date, s: number, e: number): Date => {
  if (!inQuiet(d, s, e)) return d;
  const out = new Date(d);
  out.setHours(e, 0, 0, 0);
  if (out.getTime() <= d.getTime()) out.setDate(out.getDate() + 1);
  return out;
};

const granted = (p: Notifications.NotificationPermissionsStatus): boolean =>
  p.granted ||
  p.ios?.status === Notifications.IosAuthorizationStatus.PROVISIONAL ||
  p.ios?.status === Notifications.IosAuthorizationStatus.EPHEMERAL;

/** Ask for notification permission once, correctly. */
export async function requestPerms(): Promise<boolean> {
  try {
    const { lang } = await prefs();
    await ensureChannels(lang);              // Android 13: prompt needs a channel
    const cur = await Notifications.getPermissionsAsync();
    if (granted(cur)) return true;
    if (cur.canAskAgain === false) return false; // user said no; OS won't ask again
    return granted(await Notifications.requestPermissionsAsync());
  } catch {
    return false;
  }
}

/* ---- one pending ping per purpose — fixed identifiers + cancel-before-arm
   so re-arming replaces instead of stacking ---- */
const ID_DEPARTURE = "alive-departure";
const ID_BRIEF = "alive-daily-brief";

export async function cancelDeparture(): Promise<void> {
  await Notifications.cancelScheduledNotificationAsync(ID_DEPARTURE).catch(() => {});
}
export async function cancelDailyBrief(): Promise<void> {
  await Notifications.cancelScheduledNotificationAsync(ID_BRIEF).catch(() => {});
}

/* same window-label rule as HomeScreen.fmtHr — en keeps am/pm, hi gets
   "बजे" so a Hindi notification never carries Latin letters */
const fmtHr = (h: number, lang: Lang) =>
  lang === "hi"
    ? `${((h + 11) % 12) + 1} बजे`
    : `${((h + 11) % 12) + 1}${h % 24 < 12 ? "am" : "pm"}`;

/** Daily morning briefing — "delhi's cleanest window today" — armed from the
    app's /today curve each time the toggle flips on; fires once next morning
    (copy depends on that day's curve, so it re-arms rather than repeats).
    Slides out of quiet hours; returns the id or null on any failure. */
export async function scheduleDailyBrief(opts: {
  startHour: number;
  endHour: number;
  dropPct: number;
}): Promise<string | null> {
  try {
    const p = await prefs();
    await ensureChannels(p.lang);
    const fire = new Date();
    fire.setHours(6, 45, 0, 0);
    if (fire.getTime() <= Date.now()) fire.setDate(fire.getDate() + 1);
    const at = outOfQuiet(fire, p.qStart, p.qEnd);
    await cancelDailyBrief();
    return await Notifications.scheduleNotificationAsync({
      identifier: ID_BRIEF,
      content: {
        title: t("notify_brief_title", p.lang),
        body: t("notify_brief_body", p.lang, {
          win: `${fmtHr(opts.startHour, p.lang)}–${fmtHr(opts.endHour, p.lang)}`,
          p: Math.max(1, Math.round(opts.dropPct)),
        }),
      },
      trigger: {
        type: Notifications.SchedulableTriggerInputTypes.DATE,
        date: at,
        channelId: CH_BRIEF,
      },
    });
  } catch {
    return null;
  }
}

/* ---- air events (store/events.ts) — immediate, not scheduled: each ping
   fires the moment a real field crosses its rule. Quiet-hours shifting
   would be a lie here ("air just turned poor" delivered at 7am isn't
   "just") — the OS's own DND is the user's quiet switch for these. ---- */

/** The event kinds events.ts can raise — "fires_nc" is the same belt
   build with the wind NOT carrying it to Delhi (evaluated.fires.carrying
   !== true): a real claim, worded differently. */
export type AirEventKind =
  "fires" | "fires_nc" | "band" | "window" | "stagnation" | "severe";

const EV_KEYS: Record<AirEventKind, { title: StringKey; body: StringKey }> = {
  fires:      { title: "notifyFiresTitle",  body: "notifyFiresBody" },
  fires_nc:   { title: "notifyFiresNcTitle", body: "notifyFiresNcBody" },
  band:       { title: "notifyBandTitle",   body: "notifyBandBody" },
  window:     { title: "notifyWindowTitle", body: "notifyWindowBody" },
  stagnation: { title: "notifyStagTitle",   body: "notifyStagBody" },
  severe:     { title: "notifySevereTitle", body: "notifySevereBody" },
};

/** Immediate local notification for a real air event — trigger:null so it
    delivers now, on the events channel. One identifier per kind: a worse
    reading REPLACES its earlier card in the shade rather than stacking a
    row of escalating duplicates. Returns the id or null on any failure. */
export async function notifyAirEvent(
  kind: AirEventKind,
  lang: Lang,
  vars: Record<string, string | number>,
): Promise<string | null> {
  try {
    await ensureChannels(lang);
    const keys = EV_KEYS[kind];
    /* band names its own felt words from the wire idx/prev — single-sourced
       through feltKeyForBand like every other surface in the app */
    const v = kind === "band"
      ? { ...vars,
          word: t(feltKeyForBand(typeof vars.idx === "number" ? vars.idx : null), lang),
          was: t(feltKeyForBand(typeof vars.prev === "number" ? vars.prev : null), lang) }
      : vars;
    return await Notifications.scheduleNotificationAsync({
      identifier: `air-event-${kind}`,
      content: {
        title: t(keys.title, lang),
        body: t(keys.body, lang, v),
        sound: "default",
      },
      trigger: null, // deliver immediately — the event already happened
    });
  } catch {
    return null;
  }
}

/** "leave now — lighter air" ping at the hour the /depart endpoint says the
    air window opens. Inside quiet hours it slides to quiet end — but only up
    to 2h; a reminder fired hours after the window would be a lie, so we skip
    it (return null) instead. */
export async function scheduleDeparture(opts: {
  fireAt: Date;
  savedPct: number;
}): Promise<string | null> {
  try {
    if (opts.fireAt.getTime() - Date.now() < 30_000) return null;
    const p = await prefs();
    const at = outOfQuiet(opts.fireAt, p.qStart, p.qEnd);
    if (at.getTime() - opts.fireAt.getTime() > MAX_QUIET_SHIFT_MS) return null;
    await ensureChannels(p.lang);
    await cancelDeparture();
    return await Notifications.scheduleNotificationAsync({
      identifier: ID_DEPARTURE,
      content: {
        title: t("notify_departure_title", p.lang),
        body: t("notify_departure_body", p.lang, {
          p: Math.max(1, Math.round(opts.savedPct)),
        }),
        sound: "default", // pre-Android-8 fallback; channel governs 8+
      },
      trigger: {
        type: Notifications.SchedulableTriggerInputTypes.DATE,
        date: at,
        channelId: CH_DEPARTURE,
      },
    });
  } catch {
    return null;
  }
}
