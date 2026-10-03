// metro.config.js — ALive-108 perf/RAM lane (docs/plan/perf-ram.md).
//
// Expo SDK 57's getDefaultConfig already sets the Hermes/terser pipeline;
// the only delta here is `inlineRequires: true`. Expo's default is `false`
// (see node_modules/@expo/metro-config/build/ExpoMetroConfig.js):
//
//   off: every module's body executes at bundle init, before first render —
//        all of react-native, expo-*, maplibre, react-native-svg, our JSON
//        modules… allocated up front whether used or not.
//   on:  the transform wraps each `require` so a module's body runs on
//        first use. Cold-start JS heap and time-to-interactive drop by
//        the amount of code not yet touched (measure: perf-ram.md §4).
//
// `experimentalImportSupport` is preserved at Expo's default `true`.
// Nothing else is changed: minifier stays metro-minify-terser, package
// exports stay enabled, asset pipeline untouched — the audit found no
// other knob here with a demonstrable RAM win.

const { getDefaultConfig } = require("expo/metro-config");

const config = getDefaultConfig(__dirname);

config.transformer.getTransformOptions = async () => ({
  transform: {
    experimentalImportSupport: true,
    inlineRequires: true,
  },
});

module.exports = config;
