You are the perf lane for ALive-108 — the owner's standing complaint is "glitchy and slow, I want ms responsiveness, peak fps". The design lanes made it look right; now make it FEEL fast. Deliver: measured jank wins on the real surfaces + a release-APK before/after where measurable.

Repo: <owner>/Delhi-Air-108, branch base/v2 (pull latest — apk-drive-v2 is building at HEAD but only touches generated dirs/gradle, not src). App: Mobile/ (Expo RN SDK54). iPhone-17 sim dev client for JS-thread measurement; Android KVM emulator if present on your box (memory `android-emulator-box`). Live API: http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com (GETs + /v2/plan + /v2/reroute only — NEVER POST /v2/feedback, /observe, /v2/trip).

HARD RULES
- Push code only — never deploy. `npx tsc --noEmit && npx expo lint` before push. Never hand-edit android/ios/.
- STRUCTURE FROZEN — no new/removed/reordered cards, no new data calls. Perf only.
- Nothing fake: if a "fix" can't be measured, say so — don't claim speed you can't show.
- Measure first: use React DevTools profiler / console.time-in-Dev / onLayout / the perf harness at tools/firstopen if it fits. Every claim gets a number.

MANDATE — the known suspects, then whatever profiling finds:
1. **useNativeDriver:false everywhere** — every entry spring (opacity+translateY in OnboardingScreen, SearchScreen, SettingsScreen, HomeScreen + ~60 Animated call sites) runs on the JS thread. Flip to `useNativeDriver:true` wherever the animated props support it (opacity/transform — the supported set). Verify no prop in the animation needs layout-driven values before flipping; if a site can't flip, comment why.
2. **HomeScreen zero memoization** — the whole card stack re-renders on every poll (dayNonce, field refresh ~60s). Profile which subtrees re-render wastefully (the day arc, sparkline, days-ahead strip are pure props — React.memo candidates). Add memo/useMemo where the props are stable; don't memo for memo's sake.
3. **The sheet-drift D1 question** — injected drags die on DelhiToday sheet on the Android-15 emulator. Read the sheet's gesture architecture (PanResponder? Animated.event? a library?) — if the JS-driven gesture path is the bottleneck, a Reanimated/native-gesture swap is the real fix; judge the cost honestly, do it only if it's a contained change.
4. **Re-render storms** — anything subscribed per-frame/per-poll that re-renders the tree: map layer props, context values recreated per render, unmemoized selectors in useShellFlow/useDayData.
5. **Startup** — first-open lane got first-number to ~2.8s; find the next cheap win (deferred imports? fewer awaits before first paint?) — measure before claiming.

Report: per-fix before/after numbers (ms to interactive, profiler render counts, dropped-frame estimate), the nativeDriver flip list (flipped / skipped+why), memo sites added, D1 progress, anything you measured that surprised you.
