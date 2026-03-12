# Hybrid Rocket Trajectory Simulator

2-D point-mass trajectory simulator for hybrid sounding rockets.
Given a target apogee altitude, it finds all viable **(thrust, burn time)** design points and runs a full high-fidelity trajectory for the selected one.

## Features

- **ISA atmosphere** (5 layers, 0-47 km)
- **Altitude-corrected thrust** with nozzle pressure correction
- **39-point Cd(Mach)** cubic spline (clamped to table bounds)
- **Heun predictor-corrector** integrator (2nd-order Runge-Kutta)
- **Feasibility curve** via coarse scan + brentq root-finding
- **Nozzle geometry** derived from thrust (scales with motor size)
- **12 publication-quality plots** (6 feasibility + 6 trajectory)

## Notebooks

| File | Description |
|------|-------------|
| hybrid_rocket_trajectory.ipynb | **Main notebook** (English, corrected v2) |
| hybrid_rocket_trajectory_v1.ipynb | Original version (Portuguese, preserved as-is) |

## Quick Start

1. Open hybrid_rocket_trajectory.ipynb in Jupyter or Google Colab
2. Edit the **User Inputs** cell with your vehicle parameters
3. Run all cells
4. Select a design point by setting tb_selected (burn time in seconds)
5. Re-run the trajectory cell to get full results

### Default Parameters

    epsilon     = 0.54      # structural fraction Ms/M0
    d_cm        = 20.0      # airframe diameter [cm]
    alfa0       = 85.0      # launch angle [deg]
    c0          = 2138.58   # exhaust velocity [m/s] (= Isp x g)
    Pc          = 30e5      # chamber pressure [Pa]
    CF          = 1.50      # thrust coefficient
    ER          = 4.0       # nozzle expansion ratio
    H_target_km = 20.0      # apogee target [km]

## Physics Reference

See [docs/physics_reference.md](docs/physics_reference.md) for:
- Complete equation derivations
- Parameter reference table
- Differences between v1 and v2
- Extension guide (payload, mass constraints, wind model, etc.)

## Dependencies

- numpy
- scipy
- matplotlib

## Validated Against

Excel VBA reference (trajectory-hybrid-16km.xlsm) -- 122 data points, max error < 0.002%.
