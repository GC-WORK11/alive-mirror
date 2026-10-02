import * as Notifications from "expo-notifications";
import { Platform } from "react-native";

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: false,
    shouldSetBadge: false,
  }),
});

export async function requestPerms(): Promise<boolean> {
  const { granted } = await Notifications.requestPermissionsAsync();
  return granted;
}

export async function ensureChannel() {
  if (Platform.OS === "android") {
    await Notifications.setNotificationChannelAsync("departures", {
      name: "Departures",
      importance: Notifications.AndroidImportance.DEFAULT,
      sound: null,
    });
  }
}

const fmtHr = (h: number) => `${((h - 1) % 12) + 1}${h < 12 ? "am" : "pm"}`;

/** Daily morning briefing — "delhi's cleanest window today" — armed from
    the app's /today curve each time it opens; fires once next morning. */
export async function scheduleDailyBrief(opts: {
  startHour: number; endHour: number; dropPct: number;
}): Promise<string | null> {
  await ensureChannel();
  const fire = new Date();
  fire.setHours(6, 45, 0, 0);
  if (fire.getTime() <= Date.now()) fire.setDate(fire.getDate() + 1);
  const secs = Math.floor((fire.getTime() - Date.now()) / 1000);
  return Notifications.scheduleNotificationAsync({
    content: {
      title: "delhi's cleanest window today",
      body: `${fmtHr(opts.startHour)}–${fmtHr(opts.endHour)} — air runs ${opts.dropPct}% lighter. plan the smoky trips around it.`,
    },
    trigger: {
      type: Notifications.SchedulableTriggerInputTypes.TIME_INTERVAL,
      seconds: secs,
      repeats: false,
      channelId: "departures",
    },
  });
}

export async function scheduleDeparture(opts: {
  fireAt: Date;
  savedPct: number;
}): Promise<string | null> {
  const secs = Math.floor((opts.fireAt.getTime() - Date.now()) / 1000);
  if (secs < 30) return null;
  await ensureChannel();
  return Notifications.scheduleNotificationAsync({
    content: {
      title: "ALive-108",
      body: `same trip now — ${opts.savedPct}% less PM2.5`,
    },
    trigger: {
      type: Notifications.SchedulableTriggerInputTypes.TIME_INTERVAL,
      seconds: secs,
      repeats: false,
      channelId: "departures",
    },
  });
}
