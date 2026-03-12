# Hybrid Rocket Trajectory Simulator — Physics & Logic Reference

**Document purpose:** complete technical reference for the two preliminary-sizing notebooks,
written so that Claude Code (or any engineer) can understand, extend, or refactor the code
without needing to re-derive anything from scratch.

**Notebooks covered:**

| File | Mission objective | Mass model | Language |
|---|---|---|---|
| `hybrid_rocket_trajectory__2_.ipynb` | Target apogee (H_target) | Total-vehicle ε (no separate payload) | English |
| `Hybrid_traj.ipynb` | Target apogee (H_target) | Same — earlier version, fixed nozzle area | Portuguese |

---

## Table of Contents

1. [Coordinate system and state vector](#1-coordinate-system-and-state-vector)
2. [Atmosphere model — ISA](#2-atmosphere-model--isa)
3. [Propulsion model](#3-propulsion-model)
4. [Mass model and structural scaling](#4-mass-model-and-structural-scaling)
5. [Aerodynamic drag model](#5-aerodynamic-drag-model)
6. [Equations of motion](#6-equations-of-motion)
7. [Numerical integrator — Heun predictor-corrector](#7-numerical-integrator--heun-predictor-corrector)
8. [Flight phases and stopping conditions](#8-flight-phases-and-stopping-conditions)
9. [Feasibility curve — solver logic](#9-feasibility-curve--solver-logic)
10. [Design point selection and full trajectory](#10-design-point-selection-and-full-trajectory)
11. [Key parameters — complete reference table](#11-key-parameters--complete-reference-table)
12. [Differences between the two notebooks](#12-differences-between-the-two-notebooks)
13. [Known issues and fixes applied](#13-known-issues-and-fixes-applied)
14. [Extension guide for Claude Code](#14-extension-guide-for-claude-code)

---

## 1. Coordinate system and state vector

The model is **2-D point-mass** in a vertical plane. Earth is flat, non-rotating.

```
          h (altitude, y)
          │
          │    ╱ V (total velocity)
          │   ╱
          │  ╱  α (flight path angle from horizontal)
          │ ╱
          └──────────────────── x (downrange)
         launch
         point
```

**State vector** at each time step:

| Variable | Symbol | Unit | Description |
|---|---|---|---|
| Altitude | `y` (or `ya`) | m | Vertical position above launch point |
| Downrange | `x` (or `xa`) | m | Horizontal position |
| Speed | `V` (or `Va`) | m/s | Total velocity magnitude |
| Flight path angle | `alfa` (or `alfaa`) | deg | Angle of V above horizontal |

The two scalar ODEs are for `V` and `alfa`; position is integrated from those.

---

## 2. Atmosphere model — ISA

International Standard Atmosphere, implemented in **five layers** up to 47 km.
Above 47 km the model freezes temperature and sets pressure → 0 (approximation valid
for all trajectories targeting ≤ 40 km).

### Temperature profile

```
Layer 0  (0 – 11 km):    T(z) = 288.15 − 0.0065 · z          [K]
Layer 1  (11 – 20 km):   T(z) = 216.65                        isothermal
Layer 2  (20 – 32 km):   T(z) = 216.65 + 0.001  · (z−20000)
Layer 3  (32 – 47 km):   T(z) = 228.65 + 0.0028 · (z−32000)
Layer 4  (> 47 km):      T(z) = 270.65                        frozen
```

### Pressure profile

Derived by integrating the hydrostatic equation `dP/dz = −ρg` using the ideal gas law:

**Troposphere (layer 0):**
```
P(z) = P_sl · [T(z) / T_sl]^(g / R / |λ|)
     = ATM  · [T(z) / 288.15]^(9.81 / 287 / 0.0065)
```

**Isothermal layers (layer 1):**
```
P(z) = P(z_base) · exp[−g · (z − z_base) / (R · T)]
```

**Gradient layers (layers 2, 3):** same power-law form as layer 0, applied relative to layer base.

### Air density

Always from the ideal gas law:
```
ρ(z) = P(z) / (R · T(z))     R = 287 J/(kg·K)
```

**Code functions:**

```python
air_temperature(z)   →  T [K]
air_pressure(z)      →  P [Pa]
air_density(z)       →  ρ [kg/m³]
```

---

## 3. Propulsion model

### Propellant (N₂O / HDPE or HTPB hybrid)

The motor is assumed to produce **constant thrust** throughout the burn (flat mass-flow profile):

```
ṁ = Mp / tb = Tsl / c0          [kg/s]
```

where `c0` is the **effective exhaust velocity** (= Isp × g), a constant representing
the combined effect of specific impulse and combustion efficiency.

### Altitude-corrected thrust

The nozzle exit pressure differs from ambient at altitude, producing a **pressure thrust correction**:

```
T(h) = ṁ · c_eff(h)
c_eff(h) = c0 · [1 + Au · (P_sl − P_amb(h)) / F0]
```

where:
- `Au` = nozzle exit area [m²]
- `P_sl` = ATM = 101 300 Pa (sea-level pressure, reference)
- `P_amb(h)` = ISA pressure at current altitude
- `F0` = reference sea-level thrust = `C2 · Ms · c0 / tb` = `Tsl` [N]

This formulation matches the original Excel VBA exactly. At sea level, `c_eff = c0`.
At altitude, `P_amb < P_sl` so `c_eff > c0` (under-expanded nozzle contributes extra thrust).

### Nozzle geometry

**Version 1 (`Hybrid_traj.ipynb`):** nozzle exit area `Au` is a fixed user input.
This is physically inconsistent when scanning different thrust levels — the same physical
nozzle cannot serve motors of very different sizes.

**Version 2 (`hybrid_rocket_trajectory__2_.ipynb`):** `Au` is **derived from thrust**:

```
A_throat = Tsl / (Pc · CF)
Au = A_exit  = A_throat · ER
```

| Parameter | Symbol | Typical value | Unit |
|---|---|---|---|
| Chamber pressure | `Pc` | 30 × 10⁵ | Pa |
| Thrust coefficient | `CF` | 1.50 | — |
| Expansion ratio | `ER` | 4.0 | A_exit / A_throat |

This means `Au ∝ Tsl` — doubling thrust doubles all nozzle areas. This is the physically
correct approach for a scaling study.

---

## 4. Mass model and structural scaling

### Propellant mass

Derived directly from thrust and burn time:
```
Mp = Tsl · tb / c0          [kg]
```

### Structural mass — single-ε model (both notebooks)

The structural fraction `ε` (epsilon) is defined as:
```
ε = Ms / M0 = Ms / (Ms + Mp)
```

Rearranging:
```
Ms = ε · Mp / (1 − ε)
M0 = Mp + Ms = Mp / (1 − ε)
```

The **mass ratio** `C2` is constant for fixed ε:
```
C2 = Mp / Ms = (1 − ε) / ε
```

This is a critical simplification: because C2 is constant, the entire vehicle scales
proportionally with motor size. Every point on the feasibility curve has the same
structural efficiency.

**Typical ε values:**

| Application | ε |
|---|---|
| Optimistic (large vehicles) | 0.20 – 0.35 |
| Real N₂O/HTPB hardware (motor only) | 0.40 – 0.50 |
| Total vehicle with recovery/avionics | 0.54 – 0.60 |
| Value used in these notebooks | 0.54 |

### Instantaneous mass during burn

```
M(t) = Ms · [1 + C2 · (1 − t/tb)]
     = Ms · frac(t)
```

where `frac(t) = 1 + C2·(1 − t/tb)`.

At t = 0: `M(0) = Ms·(1+C2) = Ms + Mp = M0` ✓  
At t = tb: `M(tb) = Ms` (dry mass = burnout mass) ✓

### Thrust-to-weight ratio

```
T/W = Tsl / (M0 · g)
```

For T/W > 1 (liftoff condition):
```
Tsl > M0 · g = Mp / (1−ε) · g
→  Mp < Tsl · (1−ε) / g
→  tb < c0 · (1−ε) / g        ← upper bound on burn time
```

This is `tb_tw1` in the code, used as the hard ceiling when scanning the feasibility curve.

---

## 5. Aerodynamic drag model

### Drag force

```
D = ½ · ρ(h) · V² · Aref · Cd(Mach)          [N]
```

where `Aref = π/4 · d²` is the frontal cross-sectional area of the airframe.

### Drag coefficient — Cd(Mach) spline

The model uses a **39-point Mach table** from Mach 0.083 to Mach 12.42, interpolated
with a **natural cubic spline** (`scipy.interpolate.CubicSpline`, `bc_type='natural'`).

**Mach table (39 knots):**
```
Mach:  0.083  0.496  0.875  0.944  0.995  1.030  1.081  1.133 ...
Cd:    0.404  0.404  0.407  0.432  0.475  0.510  0.553  0.596 ...
          ↑ subsonic flat    ↑ transonic peak (Mach 1.37) ↓ supersonic decrease
Mach:  1.374  1.649  1.856 ...  12.0  12.42
Cd:    0.619  0.588  0.550 ...  0.162  0.160
```

The table encodes a **generic sounding rocket** aerodynamic profile:
- Flat subsonic (~0.40)
- Sharp transonic rise peaking at Mach ~1.37 (~0.62)
- Monotonic supersonic decrease to ~0.16

**Clamping:** Mach is clipped to `[_MACH_TABLE[0], _MACH_TABLE[-1]]` before spline
evaluation to prevent divergent polynomial extrapolation outside the table bounds.

> ⚠️ **This Cd table is geometry-specific.** It was derived from the original Excel
> VBA file for a specific vehicle (d ≈ 18–20 cm, finned sounding rocket). For a
> different airframe shape or diameter, the table must be replaced.

---

## 6. Equations of motion

### Boost phase (0 ≤ t ≤ tb)

Acceleration along the velocity vector (tangential):
```
dV/dt = ag · g

ag = [c_eff(h) · C2 / (tb · frac(t))] / g
   − [½ · ρ · V² · Aref · Cd / Ms / frac(t)] / g
   − sin(α)
```

Breaking this down term by term:

| Term | Physical meaning |
|---|---|
| `c_eff · C2 / (tb · frac · g)` | Thrust acceleration / g = T(h) / M(t) / g |
| `½ρV²·Aref·Cd / Ms / frac / g` | Drag deceleration / g = D / M(t) / g |
| `sin(α)` | Gravity component along trajectory |

Note: `Ms · frac(t) = M(t)` — the structural mass times frac equals instantaneous total mass.

Gravity turn (flight path angle evolution):
```
dα/dt = −cos(α) · g / V          [deg/s, converted via rad]
```

This is the **passive gravity turn** — no active guidance. The vehicle follows a natural
arc driven only by the component of gravity perpendicular to the velocity vector.

### Coast phase (t > tb)

Thrust term drops to zero. Dry mass `Ms` replaces `M(t)` (mass is now constant):
```
dV/dt = [−½ · ρ · V² · Aref · Cd / Ms / g − sin(α)] · g

dα/dt = −cos(α) · g / V
```

### Position integration

```
dy/dt = V · sin(α)    (vertical)
dx/dt = V · cos(α)    (horizontal)
```

---

## 7. Numerical integrator — Heun predictor-corrector

The **Heun method** (explicit trapezoidal, 2nd-order Runge-Kutta) is used for all integration.
It was chosen to match the original Excel VBA implementation exactly.

### Algorithm for one step Δt

**Predictor (Euler step):**
```
k1 = f(t, y_n)
y* = y_n + Δt · k1
```

**Corrector (average slopes):**
```
k2 = f(t, y*)
y_{n+1} = y_n + Δt · (k1 + k2) / 2
```

### Important VBA-matching detail

In the boost phase, the `frac(t)` in the corrector step uses the **current time** `t`,
not the predicted time `t + Δt`. This is a deliberate match to the VBA convention.
Using `frac(t + Δt)` in the corrector worsens agreement with the Excel reference by
~0.66 m at burnout. The code preserves this behavior.

### Step sizes

| Usage | Δt | Tolerance |
|---|---|---|
| Feasibility curve (fast scan) | 0.1 s | ~0.1% apogee error |
| Full trajectory (high fidelity) | 0.01 s | <0.002% vs Excel |
| Output sampling | every 50 steps | 0.5 s resolution |

---

## 8. Flight phases and stopping conditions

```
Phase 1: BOOST          0 ≤ t ≤ tb
         Motor on, mass decreasing
         Stop: t exceeds burn time tb

Phase 2: COAST          t > tb
         Motor off, mass constant = Ms (or M_bo with payload)
         Stop: V < 0  (velocity reversal = apogee)

Apogee:  Last y recorded when V crosses zero
```

The apogee stopping condition uses `V ≥ 0` (total velocity magnitude), which is valid
for nearly vertical trajectories (α ≈ 83–89°). At these angles, total V and vertical
component Vy cross zero nearly simultaneously (< 0.1% difference).

---

## 9. Feasibility curve — solver logic

### Concept

For a given mission target (apogee altitude or Mach at altitude), there is a **family
of motor solutions**: high thrust + short burn, or low thrust + long burn.  
The feasibility curve maps out all of these.

### Algorithm

For each candidate thrust level `Tsl`:

**Step 1 — Compute upper bound on tb** (T/W > 1 constraint):
```python
tb_tw1 = c0 * (1 − epsilon) / g * 0.99
```

**Step 2 — Coarse scan** over `TB_SCAN = np.linspace(0.5, 60, 60)`:
- Compute fast apogee estimate for each `(Tsl, tb)` pair
- Detect sign change: `(apo_prev − H_target) · (apo − H_target) < 0`
- Record bracket `[tb_lo, tb_hi]`

**Step 3 — Root finding** with `scipy.optimize.brentq`:
```python
tb_sol = brentq(
    lambda tb: simulate_apogee(Tsl, tb, ...) − H_target,
    tb_lo, tb_hi, xtol=0.05
)
```

Brentq converges in ~6–10 function evaluations to xtol = 0.05 s, giving apogee
accuracy better than 0.01%.

**Step 4 — Record the solution point**:
- `Mp = Tsl · tb_sol / c0`
- `Ms = ε · Mp / (1 − ε)`
- `T/W = Tsl / (M0 · g)`
- Nozzle geometry (version 2 only)

### TB_SCAN grid — known anomaly fix

The original notebook used a two-segment scan:
```python
# OLD — causes mass anomaly near Tsl ≈ 2 kN
TB_SCAN = np.concatenate([np.linspace(0.5, 10, 20),   # step = 0.50 s
                           np.linspace(10, 60, 30)])    # step = 1.72 s
```

At the join point (tb ≈ 10 s) the bracket width jumps 3.5×, causing `brentq` to converge
to different sides of the solution, producing a discontinuous bump in `Mp` and `Ms`.

**Fix (applied in version 2):**
```python
TB_SCAN = np.linspace(0.5, 60, 60)    # uniform step = 1.0 s everywhere
```

---

## 10. Design point selection and full trajectory

### Interpolation on the feasibility curve

The user selects a burn time `tb_selected`. The corresponding thrust is found by
linear interpolation on the sorted feasibility curve:

```python
_idx = np.argsort(curve_tb)
Tsl_selected = np.interp(tb_selected,
                          curve_tb[_idx],
                          curve_Tsl[_idx]) * 1000    # → [N]
```

Note: `curve_tb` must be sorted before `np.interp` because the feasibility curve is
monotonically decreasing in Tsl vs tb but the array order depends on the thrust sweep.

### Full trajectory outputs

The high-fidelity run (`dt = 0.01 s`) records every 50 steps (0.5 s resolution) and returns:

| Key | Type | Description |
|---|---|---|
| `t`, `h`, `V` | arrays | time, altitude, speed |
| `Mach`, `Cd`, `Drag` | arrays | aero quantities |
| `alfa` | array | flight path angle |
| `y_bo`, `V_bo`, `alfa_bo` | scalars | burnout state |
| `y_apo`, `x_apo` | scalars | apogee position |
| `Ms`, `Mp`, `M0`, `C2`, `TW` | scalars | mass breakdown |
| `A_throat`, `Au` | scalars | nozzle areas |

---

## 11. Key parameters — complete reference table

| Parameter | Symbol | Unit | Typical / used value | Description |
|---|---|---|---|---|
| Structural fraction | `epsilon` / `ε` | — | 0.54 | `Ms / M0` for total vehicle |
| Airframe diameter | `d_cm` | cm | 18 – 30 | Sets reference area `Aref` |
| Launch angle | `alfa0` | deg | 85 | Angle above horizontal at t=0 |
| Exhaust velocity | `c0` | m/s | 2138.58 | `Isp × g`; N₂O/HDPE: Isp ≈ 218 s |
| Chamber pressure | `Pc` | Pa | 30 × 10⁵ | 30 bar |
| Thrust coefficient | `CF` | — | 1.50 | Typical N₂O/HTPB: 1.4 – 1.6 |
| Expansion ratio | `ER` | — | 4.0 | `A_exit / A_throat` |
| Nozzle exit area | `Au` | m² | derived | Version 2: `Au = Tsl / (Pc·CF) · ER` |
| Step (fast) | `dt_fast` | s | 0.1 | For feasibility curve |
| Step (full) | `dt_full` | s | 0.01 | For full trajectory |
| Sea-level pressure | `ATM` | Pa | 101 300 | ISA reference |
| Gas constant (air) | `R` | J/(kg·K) | 287 | |
| Specific heat ratio | `GAMMA` | — | 1.4 | |
| Gravity | `g` | m/s² | 9.81 | |

---

## 12. Differences between the two notebooks

| Feature | `Hybrid_traj.ipynb` (v1) | `hybrid_rocket_trajectory__2_.ipynb` (v2) |
|---|---|---|
| Language | Portuguese | English |
| Nozzle area | Fixed user input `Au` | Derived: `Au = Tsl/(Pc·CF)·ER` |
| Cd clamping | None — spline extrapolates outside table | Clamped: `np.clip(mach, M[0], M[-1])` |
| TB_SCAN | Non-uniform (two linspaces joined) — mass anomaly near tb=10 s | Uniform — anomaly fixed |
| np.interp sort | Uses `curve_tb[::-1]` (reversed, fragile) | Uses `np.argsort` (robust) |
| Integrator structure | Monolithic functions | Modular: `_boost_slopes`, `_coast_slopes`, `_heun_boost`, `_heun_coast` |
| Output | 6 trajectory plots | 6 trajectory plots + 6 feasibility plots |
| Feasibility plots | 3 panels | 6 panels (adds nozzle geometry) |
| Validation | Not shown | Validated against 122 Excel data points, max error 0.002% |

The **physics is identical** in both. The VBA matching detail (frac at t, not t+Δt)
is present in both.

---

## 13. Known issues and fixes applied

### Issue 1 — Cd extrapolation outside table (v1 only)

**Problem:** `splineV(m)` in v1 calls `_spl(m)` without clamping. Above Mach 12.42
the cubic polynomial diverges to 0.19 (vs correct 0.16). Below Mach 0.083 it
undershoots slightly.

**Fix (v2):**
```python
def drag_coefficient(mach):
    return float(_cd_spline(np.clip(mach, _MACH_TABLE[0], _MACH_TABLE[-1])))
```

### Issue 2 — TB_SCAN discontinuity (v1 only)

Described in Section 9. Causes a visible bump in the Ms/Mp plots at Tsl ≈ 2 kN.
Fixed by using `np.linspace(0.5, 60, 60)`.

### Issue 3 — np.interp on unsorted array (v1)

**Problem:** `curve_tb` is produced by sweeping Tsl from low to high; because apogee
is a decreasing function of Tsl at fixed tb, `curve_tb` is monotonically decreasing.
`np.interp` requires increasing x. Version 1 reverses the array (`[::-1]`), which is
fragile if the curve is not perfectly monotonic.

**Fix (v2):**
```python
_idx = np.argsort(curve_tb)
Tsl_selected = np.interp(tb_selected, curve_tb[_idx], curve_Tsl[_idx])
```

### Issue 4 — Fixed nozzle area (v1)

Described in Section 3. Using a fixed `Au` when sweeping over different thrust levels
causes an error of ~1–2% in apogee across the curve because the pressure thrust
correction does not scale correctly with motor size.

---

## 14. Extension guide for Claude Code

### Architecture summary

Both notebooks follow the same cell sequence:

```
Cell 0:  Markdown — header, equations, assumptions
Cell 1:  User inputs (edit here)
Cell 2:  Physics functions (do not edit)
Cell 3:  Feasibility curve generation + plots
Cell 4:  Design point selection (one variable: tb_selected)
Cell 5:  Full trajectory + table + 6 plots
```

### How to change the mission objective

The default objective is `apogee = H_target`. The `brentq` root-finding is structured
so the objective function can be replaced:

**Apogee target (current):**
```python
brentq(lambda tb: simulate_apogee(Tsl, tb, ...) − H_target, tb_lo, tb_hi)
```

**Velocity at altitude target (Mach 2 at 8 km — implemented in v3):**
```python
brentq(lambda tb: simulate_v_at_h(Tsl, tb, ...) − V_target, tb_lo, tb_hi)
```

The integration loop needs a **crossing detector** instead of the apogee stopping
condition:
```python
if y_prev < H_cross <= y_curr:
    V_cross = V_prev + (H_cross − y_prev)/(y_curr − y_prev) * (V_curr − V_prev)
    return V_cross
```

### How to add a payload mass

When a fixed payload `M_payload` is added (implemented in v4), the mass model changes:

```python
# Motor structure scales with Mp
Ms_motor = epsilon_motor * Mp / (1 − epsilon_motor)

# Dry mass includes fixed payload
M_bo = Ms_motor + M_payload

# Effective C2 is no longer constant — varies across the curve
C2 = Mp / M_bo

# Integrator: replace Ms → M_bo everywhere
# frac(t) · M_bo = M(t)  still holds
```

### How to add a total mass constraint

When `M0 ≤ M0_max` is required (implemented in v5):

```python
def effective_payload(Tsl, tb, epsilon_motor, M_payload_nom, M0_max, c0):
    Mp     = Tsl * tb / c0
    M_motor = Mp / (1 − epsilon_motor)
    return min(M_payload_nom, max(0.0, M0_max − M_motor))
```

The hard burn-time ceiling per thrust level is:
```python
tb_hard = M0_max * c0 * (1 − epsilon_motor) / Tsl
```

`TB_SCAN` must be truncated at `tb_hard` to avoid infeasible regions.

### Validated baseline parameters

These values were validated against the reference Excel spreadsheet
(`trajectory-hybrid-16km.xlsm`) to < 0.002% error across 122 time points:

```python
epsilon   = 0.54          # total vehicle structural fraction
c0        = 2138.58       # m/s
Pc        = 30e5          # Pa
CF        = 1.50
ER        = 4.0
d_cm      = 20.0          # cm
alfa0     = 85.0          # deg
H_target  = 16000         # m
tb_sol    = 25.0          # s  (design point)
Tsl_sol   = 1800          # N  (≈ 1.8 kN)
```

Burnout state at this design point:
```
h_bo  = 8 432.5 m     (Excel: 8 432.5 m)
V_bo  = 654.1  m/s    (Excel: 654.1  m/s)
```

### Recommended next steps for Claude Code

1. **Refactor into a Python package** with modules:
   - `atmosphere.py` — ISA functions
   - `aerodynamics.py` — Cd spline
   - `propulsion.py` — nozzle geometry, c_eff
   - `mass_model.py` — epsilon, payload, M0 constraint
   - `integrator.py` — Heun steps
   - `simulator.py` — simulate_apogee, simulate_v_at_h, simulate_trajectory
   - `feasibility.py` — curve generation, brentq wrapper

2. **Add wind model** — constant horizontal wind vector as additional force term
   in the equations of motion

3. **Add variable thrust profile** — replace flat ṁ with a tabulated thrust curve
   `T(t)`, integrate numerically instead of analytic frac(t)

4. **Add parachute deployment model** — detect apogee, switch to parachute drag
   coefficient (Cd ≈ 0.8–1.0, Aref = canopy area) for descent phase

5. **Add Monte Carlo** — vary ε, c0, Cd by ±σ and plot apogee distribution

6. **Web interface** — the simulator is fast enough (< 1 s per curve) for a
   Streamlit or Gradio frontend with live parameter sliders

---

*Document generated from code inspection of `hybrid_rocket_trajectory__2_.ipynb`
and `Hybrid_traj.ipynb`. All equations verified against the original Excel VBA
reference (`trajectory-hybrid-16km.xlsm`).*