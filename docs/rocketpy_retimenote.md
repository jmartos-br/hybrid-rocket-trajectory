# RocketPy comparison — retimed motors

This branch adds:

- Compact motor files (RASP `.eng`) generated from the flight reconstruction and SMT0033 extracted thrust curve:
  - `data/FlightRetimed_NoInf_compact.eng`
  - `data/FlightRetimed_HFT4Ign_compact.eng`
  - `data/SMT0033_Extracted_compact.eng`

- A reproducible RocketPy runner: `run_rocketpy_compare_motors.py`

## How to run

```bash
python run_rocketpy_compare_motors.py
```

Outputs are written to `outputs/`:

- `rocketpy_summary.csv`
- `rocketpy_summary.json`
- `altitude_*.png`
- `thrust_curves_compare.png`

## Notes

- The RocketPy configuration (environment, geometry, drag curves, parachute model) matches the parameters in `rocketpy_flight_simulation.ipynb`.
- `FlightRetimed_NoInf_compact.eng` does **not** copy the HFT4 ignition shape; it uses the reconstructed thrust from flight Pc only.
- `FlightRetimed_HFT4Ign_compact.eng` replaces only the first ~0.1 s with a scaled HFT4 ignition segment.
