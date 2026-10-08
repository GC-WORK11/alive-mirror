const {
  withAndroidManifest,
  withDangerousMod,
  AndroidConfig,
} = require("expo/config-plugins");
const fs = require("fs");
const path = require("path");

/* Profile-based backup — the owner ask (local-store lane): the user's own
   Google account restores their on-device stores on a new phone; we never
   host anything. Android Auto Backup (free, account-tied, no server of
   ours) covers the app's files dir — where expo-file-system's
   Paths.document lives — but ONLY if the payload stays under its ~25 MB
   quota. Unbounded candidates get excluded so the small honest stores
   (ledger, daylog, daysum, settings, consent, vehicle, places, outbox,
   events, contributor) always fit:

     - mbgl-offline.db   — the MapLibre offline pack + ambient tile cache
                           (27 MB pack + up to ~160 MB ambient). Every tile
                           re-downloads; on Android it sits in files/, not
                           the auto-excluded cache dir. .mapbox/ covers any
                           layout where the store nests under its own dir.
     - delhi.pmtiles     — optional dev-drop local basemap (tens of MB);
                           regenerable from the tile pipeline.
     - alive-cache/      — last-good API payloads (plan/strip/depart/
                           daycurve/outlook). Bounded to ~12 MB by
                           api/cache.ts's sweeper, but regenerable —
                           re-fetched on first contact after restore.
     - perf_log.jsonl    — PERF_ON dev instrumentation only.
     - ReactNativeDevSupport — dev-support artifacts, never user data.

   Both rule styles are declared so coverage holds across the fleet:
   dataExtractionRules (API 31+, cloud-backup + device-transfer) and
   fullBackupContent (API <= 30). */

const EXCLUDED = [
  "mbgl-offline.db",
  "mbgl-offline.db-journal",
  "mbgl-offline.db-wal",
  "mbgl-offline.db-shm",
  ".mapbox",
  "delhi.pmtiles",
  "alive-cache",
  "perf_log.jsonl",
  "ReactNativeDevSupport",
];

const block = (tag) =>
  [
    `  <${tag}>`,
    `    <include domain="file" path="."/>`,
    ...EXCLUDED.map((p) => `    <exclude domain="file" path="${p}"/>`),
    `    <include domain="sharedpref" path="."/>`,
    `  </${tag}>`,
  ].join("\n");

const DATA_EXTRACTION_RULES = `<?xml version="1.0" encoding="utf-8"?>
<data-extraction-rules>
${block("cloud-backup")}
${block("device-transfer")}
</data-extraction-rules>
`;

const FULL_BACKUP_CONTENT = `<?xml version="1.0" encoding="utf-8"?>
<full-backup-content>
  <include domain="file" path="."/>
${EXCLUDED.map((p) => `  <exclude domain="file" path="${p}"/>`).join("\n")}
  <include domain="sharedpref" path="."/>
</full-backup-content>
`;

module.exports = function withBackupRules(config) {
  config = withAndroidManifest(config, (c) => {
    const app = AndroidConfig.Manifest.getMainApplicationOrThrow(c.modResults);
    app.$["android:allowBackup"] = "true";
    app.$["android:dataExtractionRules"] = "@xml/alive_data_extraction_rules";
    app.$["android:fullBackupContent"] = "@xml/alive_backup_rules";
    return c;
  });
  return withDangerousMod(config, [
    "android",
    async (c) => {
      const dir = path.join(
        c.modRequest.platformProjectRoot,
        "app", "src", "main", "res", "xml",
      );
      fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(
        path.join(dir, "alive_data_extraction_rules.xml"),
        DATA_EXTRACTION_RULES,
      );
      fs.writeFileSync(
        path.join(dir, "alive_backup_rules.xml"),
        FULL_BACKUP_CONTENT,
      );
      return c;
    },
  ]);
};
