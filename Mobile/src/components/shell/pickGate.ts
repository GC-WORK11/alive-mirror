/* pickTailGate — the pick-race surface gate (demo-vid-android): a pick's
   async tail may only write journey state while the surface still belongs
   to it. "stay" writes (locPickFailed/pickTooClose re-arm) need search
   still up; the "advance" write tolerates search→compare because the
   journey already moved in this pick's own direction. Anything else
   (idle after a back-press, mapPickArmed, a newer surface) means the
   write must not happen: writing setPhase("search") there remounts an
   EMPTY Where-to — the bounce the drive caught. Kept in its own pure
   module so nav/pickRace.test.ts can import the real predicate without
   dragging in react-native. `surface` is useShellFlow's Phase. */
export function pickTailGate(surface: string, intent: "stay" | "advance"): boolean {
  /* "place" joins the allowed set for both intents — it's the settle
     surface inside the pick's own direction (a live advance may cross
     it; a retreat re-arms search from it). "idle" stays out of
     "advance": an armed mapPickArmed idle must never get hijacked by a
     stale async tail — synchronous pick paths check `!== "nav"`
     directly instead of going through this gate. */
  if (intent === "advance")
    return surface === "search" || surface === "compare" || surface === "place";
  return surface === "search" || surface === "place";
}
