// Perf marks first — t0 is this module's eval, before the App import tree
// and the expo/React module evals run. See src/startup/marks.ts.
import { mark, markOnce } from "./src/startup/marks";

import React from "react";
import { registerRootComponent } from "expo";

import App from "./App";

mark("index:eval");

// Thin root wrapper: stamps app:didMount / app:firstFrame without touching
// App.tsx (owned by another lane) — render and behavior are identical.
function Root() {
  React.useEffect(() => {
    markOnce("app:didMount");
    const raf = requestAnimationFrame(() => markOnce("app:firstFrame"));
    return () => cancelAnimationFrame(raf);
  }, []);
  return React.createElement(App);
}

// registerRootComponent calls AppRegistry.registerComponent('main', () => Root);
// It also ensures that whether you load the app in Expo Go or in a native build,
// the environment is set up appropriately
registerRootComponent(Root);
mark("index:registered");
