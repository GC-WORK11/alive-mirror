import * as Device from "expo-device";

/* The iOS Simulator's virtualized GPU wedges MapLibre's transition-
   handler table — every SIGSEGV chased through this stack (plan:first,
   sheet commits, the 60 s report poll, an idle death) carried the same
   "cannot add handler to 0 from 0" render-thread signature while a
   camera transition was in flight or being cancelled. duration: 0 takes
   the camera's instant path — no transition is registered, so nothing
   can race a draw. Real hardware keeps every animation untouched; the
   trade is only visible on a sim, where a jump beats a dead process. */
export const camDur = Device.isDevice
  ? (ms: number) => ms
  : () => 0;
