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
