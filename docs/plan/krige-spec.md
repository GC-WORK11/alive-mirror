# krige-spec — exact algorithm for `server/krige.py`

Normative reference. The C++ port (doc 08) must reproduce `KrigeField`
outputs bit-close (target ≤1e-9 relative per 06 §5 "Engine parity"); any
ambiguity in this document is a bug — resolve it against `krige.py`,
then fix this file.

## 1. Scope

Ordinary kriging only. The unknown mean is a single constant; there are
NO drift/trend terms (that would be universal kriging). Callers supply
the trend externally: `airindex` kriges station-minus-model residuals
around the CAMS prior, `airfield` kriges the de-biased concentration
field directly. Residual inputs are legitimately negative — the estimate
is therefore never clamped (see §6).

## 2. Public contract

```python
KF = KrigeField()                     # module singleton
kf = KrigeField().fit(samples, key="pm2_5")   # fit returns self
kf.on                                  # bool: kriging usable?
kf.estimate(lat, lon)                  # -> (mu, sigma) | None
```

- `samples`: iterable of `(lat, lon, name, {key: value})`; `name` is
  ignored. Values are what is being interpolated (µg/m³ or residuals).
- `estimate` returns Python floats `(µ̂, σ̂)` in the same units as the
  inputs, or `None` when kriging is off or the query is non-finite.
- `fit` may be called repeatedly on one instance; each call fully
  resets state before refitting.

## 3. Constants (exact literals — not derived)

| name | value | meaning |
|---|---|---|
| `_KY` | 110.6 | km per degree latitude |
| `_KX` | 99.4 | km per degree longitude at 28.6°N |
| `_RANGE_KM` (`R`) | 15.0 | exponential range, km |
| `_NUGGET_FRAC` | 0.15 | nugget = this fraction of total sill |
| `_MIN_SAMPLES` | 20 | unique locations required to fit |
| `_MIN_SILL` | 2.0 | µg²/m⁶ — min sample variance to fit |
| `_VAR_FLOOR` | 1.0 | µg²/m⁶ — min reported kriging variance |

## 4. Projection

Each geographic coordinate maps to kilometres:

```
u = lat * 110.6        (northing)
v = lon * 99.4         (easting)
d(x, x') = hypot(u - u', v - v')        # km, equirectangular at ~28.6°N
```

All distances below are in these projected km.

## 5. Statistical model

Observations are a smooth latent field plus independent noise:

```
y_i = Z(x_i) + eps_i
eps_i ~ iid, var N                          (instrument + micro-scale)
cov(Z(x), Z(x')) = C(d) = P * exp(-d / R)   exponential, partial sill P
```

with

```
sill = Var(y)   (population variance of the merged samples, divide by n)
N    = 0.15 * sill        (nugget)
P    = sill - N = 0.85 * sill   (partial/structural sill)
```

Equivalent semivariogram of the observed process, for d > 0:
`gamma(d) = N + P * (1 - exp(-d / R))`, `gamma(0) = 0`; total sill
`gamma(inf) = P + N = sill`. The variogram is NOT fitted from pair
clouds — sill comes from the sample variance, `R` and the nugget
fraction are fixed constants (the field refreshes every 15 min and must
not churn its geometry).

## 6. `fit(samples, key)` — pipeline (order is normative)

1. **Parse/validate**, iterating `samples` in input order. For each
   element: unpack `(lat, lon, name, vals)`; `z = float((vals or {}).get(key))`;
   `lat, lon` coerced via `float()`. Any coercion failure or non-finite
   `lat/lon/z` → sample skipped silently. Malformed elements (wrong
   arity, non-dict `vals`, …) are skipped the same way — never fatal.
2. **Duplicate merge**: samples whose `(lat, lon)` float pair is
   bit-identical are merged into one record at the FIRST occurrence's
   position; value = arithmetic mean of the group's `z` (summed in
   encounter order, divided by count).
3. **Gates** (both leave `.on = False`, i.e. honest "kriging off",
   callers fall back to IDW):
   - unique locations `n < 20` → off;
   - `sill = (1/n) * sum((z_i - z̄)²) < 2.0` → off (covers all-equal and
     near-flat fields; σ on a flat field is fake precision).
4. **Assemble** the `(n+1) × (n+1)` augmented system, row/column order =
   merged-sample order, Lagrange block last:

   ```
   K_ij = P * exp(-d_ij / R) + N * delta_ij        i, j = 1..n
   A = [ K   1 ]
       [ 1ᵀ  0 ]
   ```

   The diagonal nugget `N·I` is the regularizer: `λ_min(K) ≥ N ≥ 0.3`,
   so coincident or nearly-coincident stations cannot make the system
   singular.
5. **Invert once**: `Ainv = A⁻¹` (`numpy.linalg.inv`, LAPACK LU with
   partial pivoting). On `LinAlgError`, or if `Ainv` contains any
   non-finite entry → `.on = False`.
6. Store merged `(u,v)` points, merged `z`, `Ainv`, `sill`, `N`, `P`;
   set `.on = True`.

## 7. `estimate(lat, lon)`

Returns `None` iff `.on` is false or `lat/lon` fails `float()` coercion
or is non-finite. Otherwise:

```
d_i = hypot(u_i - u, v_i - v)
k_i = P * exp(-d_i / R)                 # cov(obs_i, Z(query)) — no nugget
b   = [k_1 .. k_n, 1]ᵀ
w   = Ainv @ b                          # w_1..w_n weights, λ = w_{n+1}
µ̂   = Σ_i w_i * z_i                      # dot product in index order
σ̂²  = P - Σ_i w_i * k_i - λ
σ̂   = sqrt(max(σ̂², 1.0))
```

Returns `(µ̂, σ̂)`; if either is non-finite (should be impossible given
finite inputs + finite `Ainv`), returns `None`.

### Sign convention — read carefully

The augmented system uses the `+1` column convention:
`K w + λ·1 = k`, `1ᵀw = 1`. Under this convention the Lagrange term
enters the variance **negatively**: `σ̂² = C_Z(0) − w·k − λ`. (`λ` is
typically negative inside the field and ≈ `−(1ᵀK⁻¹1)⁻¹` far outside it.)
Writing `+λ` under-reports variance by `2|λ|` — largest exactly in
extrapolation, where honesty matters most. This was a real bug, fixed.

### What σ̂ means

σ̂ is the standard deviation of the **smooth field** estimate `Z(x)`,
not of a fresh noisy reading. Predicting what a new instrument at `x`
would measure adds the nugget: `σ̂²_new_obs = σ̂² + N`. Downstream callers
already add their own instrument-error floors (airfield/airindex add
`(0.12·µ)²` in quadrature), so the field band stays honest where σ̂
itself is small. The 1.0 µg²/m⁶ variance floor additionally guarantees
σ̂ ≥ 1 µg/m³ — sub-µg certainty claims are fake precision.

### What µ̂ means — unclamped, unbiased

`µ̂ = Σ w_i z_i` with `Σ w_i = 1` enforced by the constraint row; weights
may be negative, so `µ̂` may leave `[min z, max z]` in extrapolation and
may be negative for residual inputs. `estimate` returns it raw; callers
clamp physical quantities (`airindex` does `pm = max(0, pm)`). A former
`max(0, µ̂)` silently zeroed every negative residual — real bug, fixed.

## 8. Defined behaviors — every edge case

| input / state | behavior |
|---|---|
| numpy absent | `fit` no-ops, `.on=False`, `estimate→None` |
| 0–19 usable samples (incl. `<3`) | `.on=False` → caller's IDW path |
| ≥20 samples but all values equal | `sill=0 <2` → `.on=False` |
| field std < ~1.414 µg/m³ | `sill<2` → `.on=False` |
| exact duplicate coordinates | merged by mean before gates (§6.2) |
| near-duplicate coordinates | kept; `N·I` diagonal keeps the solve nonsingular |
| collinear / coplanar samples | fits normally — exponential covariance stays positive-definite for distinct points; the result is a 1-D field along the line |
| non-finite or uncoercible sample | skipped pre-count |
| malformed sample element | skipped pre-count |
| singular/failed/non-finite solve | `.on=False` |
| query on a sample point | `µ̂ ≈ z_i` regressed toward neighbours by O(N/sill) — the nugget treats the obs as noisy, not gospel; σ̂ small, ≥ floor |
| query inside convex hull | normal interpolation; σ̂ well below √P |
| query outside convex hull | no cutoff: `µ̂ → GLS mean`, `σ̂² → P + (1ᵀK⁻¹1)⁻¹` (bounded; see §9). Kriging is self-honest in extrapolation — the estimate reverts to the field mean and σ̂ saturates, instead of a hard fallback boundary |
| non-finite query coordinates | `estimate → None` |
| `.on` toggled manually post-fit | respected (validate_field uses this to A/B the IDW path) |

## 9. Extrapolation asymptote (proved, tested)

As `min_i d_i → ∞`, `k → 0`, and

```
w   → K⁻¹1 / (1ᵀK⁻¹1)            (GLS mean weights, NOT uniform)
µ̂   → (1ᵀK⁻¹z) / (1ᵀK⁻¹1)        (GLS estimate of the field mean)
λ   → −(1ᵀK⁻¹1)⁻¹
σ̂²  → P + (1ᵀK⁻¹1)⁻¹              (field variance + mean uncertainty)
```

So σ̂ is bounded above by construction — `σ̂² ≲ P + N/n` roughly — and
never collapses to the floor far from data. No distance cap is applied
or needed; the algebra is the cap.

## 10. Determinism & parity notes

- No randomness, no clocks, no iteration over unordered containers:
  dict/insertion order = input order everywhere.
- Results are permutation-invariant in exact arithmetic; the merged
  order fixes floating-point summation order, so the port must apply
  the same merge/order rules to be bit-close.
- `numpy.linalg.inv` ≡ any backward-stable dense solve in exact
  arithmetic. A C++ LU/QR with partial pivoting agrees to ~1e-12
  relative; spec target 1e-9.
- Python `np.var` = population variance (ddof=0). C++ must divide by
  `n`, not `n−1`.
- Float64 everywhere; the constants in §3 are literals, do not
  "recompute" them (e.g. `KX` is not `KY·cos(28.6°)`).
- `_VAR_FLOOR` applies to the VARIANCE (σ̂² ≥ 1 → σ̂ ≥ 1), not to σ̂.
- `fit` on the same object twice must give identical outputs from
  identical inputs; `estimate` has no side effects on the fitted state.

## 11. Worked check (mirrors `test_known_answer_circle_center`)

n = 20 points equally spaced on a circle of radius r = 10 km, arbitrary
values `z_i`; query at the centre. By the circulant symmetry every
weight is `1/n`, all `k_i = P·e^(−r/R) ≡ k_c`, and the row-sum of `K`
is `S = (P+N) + P·Σ_{m=1}^{19} exp(−2r·sin(πm/n)/R)`. Then

```
λ  = k_c − S/n
µ̂  = mean(z)
σ̂² = P − 2·k_c + S/n
```

The test computes `S` by direct summation (no linear solve) and asserts
agreement to 1e-9.
