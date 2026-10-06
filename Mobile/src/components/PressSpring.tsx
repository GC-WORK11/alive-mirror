/** PressSpring — the register's one press gesture (lane motion-v3,
 *  docs/20 §6: spring physics for every touch, scale ≥0.96, no bounce).
 *
 *  A pure wrapper: whatever's inside keeps its own Pressable, styles and
 *  handlers — the Animated.View around it dips to `scale` on touch-down
 *  and springs home on release/cancel. Touch events bubble through the
 *  wrapper regardless of which descendant holds the responder, so the
 *  dip tracks the real finger, not a guessed press lifecycle. Scroll or
 *  pan takeovers land on onTouchCancel → the surface settles back, never
 *  sticks dipped.
 *
 *  Physical, not playful: damping 12 / stiffness 180 / mass 1 settles in
 *  ~250 ms with no overshoot past 1. Native driver — scale is a lone
 *  transform node, no mixed animated graph (RN 0.86 detach class).
 *  useReduceMotion → the wrapper is inert: presses still work, nothing
 *  moves.
 *
 *  Mount:
 *    <PressSpring style={s.card}>          // wrapper carries the shell
 *      <Pressable onPress={…} style={s.row}>…</Pressable>
 *    </PressSpring>
 *  `style` lands on the scaling surface — put the control's own box there
 *  (margins/radius/flex) so the dip pivots around its real bounds. Omit it
 *  and the wrapper hugs its child.
 */
import React, { useState } from "react";
import { Animated, type StyleProp, type ViewStyle } from "react-native";
import { useReduceMotion } from "../a11y";

export function PressSpring({
  children, style, scale = 0.96,
}: {
  children: React.ReactNode;
  /** box style of the scaled surface — margins, radius, flex share */
  style?: StyleProp<ViewStyle>;
  /** press depth; the register floor is 0.96 */
  scale?: number;
}) {
  const reduce = useReduceMotion();
  const [v] = useState(() => new Animated.Value(1));
  const spring = (target: number) => {
    if (reduce) return;
    Animated.spring(v, {
      toValue: target, damping: 12, stiffness: 180, mass: 1,
      useNativeDriver: true,
    }).start();
  };
  return (
    <Animated.View
      onTouchStart={() => spring(scale)}
      onTouchEnd={() => spring(1)}
      onTouchCancel={() => spring(1)}
      style={[style, { transform: [{ scale: v }] }]}>
      {children}
    </Animated.View>
  );
}
