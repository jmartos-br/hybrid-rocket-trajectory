"""Flight thrust reconstruction + correlation + RocketPy helpers.

Designed to be used from Colab notebooks.

Key ideas:
- Calibrate Pc_gauge -> thrust using hot-fire tests (HFTs) and/or SMT0033.
- Retime onboard flight time using Ptank correlation to a reference timebase.
- Reconstruct flight thrust from flight Pc using the calibration.
- Optionally replace only the first ~0.1 s using a high-frequency hot-fire ignition shape.

All units:
- pressures in bar
- thrust in N
- time in seconds
"""

from __future__ import annotations

import csv
import math
import os
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, List

import numpy as np


@dataclass
class Series:
    t: np.ndarray
    ptank: np.ndarray
    pc: np.ndarray


@dataclass
class SMTSeries:
    t: np.ndarray
    ptank: np.ndarray
    pc: np.ndarray
    thrust_N: np.ndarray


@dataclass
class CalibrationResult:
    slope_N_per_bar: float
    intercept_N: float
    r2: float
    fit_kind: str  # 'origin' or 'intercept'


def _median(x: np.ndarray) -> float:
    return float(np.median(x)) if len(x) else 0.0


def align_by_pc(t: np.ndarray, pc: np.ndarray, pc_thresh: float = 2.0) -> Tuple[np.ndarray, int]:
    idx = np.where(pc > pc_thresh)[0]
    if len(idx) == 0:
        raise ValueError("No ignition found: Pc never exceeds threshold")
    i0 = int(idx[0])
    return t - float(t[i0]), i0


def time_at_ptank(tr: np.ndarray, ptank: np.ndarray, pt_values: np.ndarray) -> np.ndarray:
    # monotonic-ish: sort by ptank to build inverse map
    o = np.argsort(ptank)
    return np.interp(pt_values, ptank[o], tr[o])


def origin_fit_slope(x: np.ndarray, y: np.ndarray) -> float:
    den = float(np.dot(x, x))
    return float(np.dot(x, y)) / den if den > 0 else 0.0


def linear_fit_with_intercept(x: np.ndarray, y: np.ndarray) -> Tuple[float, float, float]:
    # y = a x + b
    A = np.vstack([x, np.ones_like(x)]).T
    a, b = np.linalg.lstsq(A, y, rcond=None)[0]
    yhat = a * x + b
    ss_res = float(np.sum((y - yhat) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return float(a), float(b), float(r2)


def load_flight_onboard_semicolon(path: str) -> Series:
    # columns like: Time;...;PT_Pressure;...;PC_Pressure
    t: List[float] = []
    pt: List[float] = []
    pc: List[float] = []
    with open(path, newline="", encoding="utf-8", errors="ignore") as f:
        r = csv.reader(f, delimiter=";")
        header = next(r)
        for row in r:
            if not row:
                continue
            if row and row[-1] == "":
                row = row[:-1]
            if len(row) < 7:
                continue
            try:
                t.append(float(row[0]))
                pt.append(float(row[3]))
                pc.append(float(row[6]))
            except Exception:
                continue
    t = np.array(t)
    pt = np.array(pt)
    pc = np.array(pc)
    o = np.argsort(t)
    return Series(t=t[o], ptank=pt[o], pc=pc[o])


def load_telemetry_semicolon(path: str) -> Series:
    # columns: timestamp; pt_pressure; pc_pressure
    ts: List[float] = []
    pt: List[float] = []
    pc: List[float] = []
    with open(path, newline="", encoding="utf-8", errors="ignore") as f:
        r = csv.DictReader(f, delimiter=";")
        for row in r:
            try:
                ts.append(float(row["timestamp"]))
                pt.append(float(row["pt_pressure"]))
                pc.append(float(row["pc_pressure"]))
            except Exception:
                continue
    ts = np.array(ts)
    pt = np.array(pt)
    pc = np.array(pc)
    o = np.argsort(ts)
    # convert timestamp ms to seconds (absolute) but keep in seconds; user will align later
    return Series(t=ts[o] / 1000.0, ptank=pt[o], pc=pc[o])


def load_smt_extracted_csv(path: str) -> SMTSeries:
    # columns: time_ms, tank_pressure_bar, chamber_pressure_bar, thrust_daN
    t_ms: List[float] = []
    pt: List[float] = []
    pc: List[float] = []
    thrust_dan: List[float] = []
    with open(path, newline="", encoding="utf-8", errors="ignore") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                t_ms.append(float(row["time_ms"]))
                pt.append(float(row["tank_pressure_bar"]))
                pc.append(float(row["chamber_pressure_bar"]))
                thrust_dan.append(float(row["thrust_daN"]))
            except Exception:
                continue
    t = np.array(t_ms) / 1000.0
    pt = np.array(pt)
    pc = np.array(pc)
    thr = np.array(thrust_dan)
    o = np.argsort(t)
    t = t[o]
    pt = pt[o]
    pc = pc[o]
    thr = thr[o]

    tr, i0 = align_by_pc(t, pc, 2.0)
    pre = (tr < 0) & (tr > -0.5)
    thr0 = float(np.median(thr[pre])) if np.any(pre) else float(np.median(thr[: max(1, i0)]))
    thrust_N = np.maximum((thr - thr0) * 10.0, 0.0)

    return SMTSeries(t=tr, ptank=pt, pc=pc, thrust_N=thrust_N)


def retime_onboard_by_ptank(onboard: Series, reference: Series, pc_thresh: float = 2.0, n_anchors: int = 20) -> Tuple[np.ndarray, float]:
    """Return corrected time axis for onboard (seconds from ignition), using Ptank correlation.

    Both series must have Ptank and Pc.

    Steps:
    - Align both to ignition by Pc>pc_thresh.
    - Use overlapping Ptank range and n_anchors pt values.
    - Fit scale through origin: t_ref ~= scale * t_onboard
    - Return (t_onboard_corrected, scale)
    """
    t_on_rel, _ = align_by_pc(onboard.t, onboard.pc, pc_thresh)
    t_ref_rel, _ = align_by_pc(reference.t, reference.pc, pc_thresh)

    mask_on = t_on_rel >= 0
    mask_ref = t_ref_rel >= 0
    pt_on = onboard.ptank[mask_on]
    tr_on = t_on_rel[mask_on]
    pt_ref = reference.ptank[mask_ref]
    tr_ref = t_ref_rel[mask_ref]

    pt_min = max(float(pt_on.min()), float(pt_ref.min()))
    pt_max = min(float(pt_on.max()), float(pt_ref.max()))

    pts = np.linspace(pt_max, pt_min, n_anchors)
    tron = time_at_ptank(tr_on, pt_on, pts)
    trrf = time_at_ptank(tr_ref, pt_ref, pts)

    scale = origin_fit_slope(tron, trrf)
    return t_on_rel * scale, float(scale)


def calibrate_pc_to_thrust_origin(pcg: np.ndarray, thrust: np.ndarray) -> CalibrationResult:
    a = origin_fit_slope(pcg, thrust)
    yhat = a * pcg
    ss_res = float(np.sum((thrust - yhat) ** 2))
    ss_tot = float(np.sum((thrust - np.mean(thrust)) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return CalibrationResult(slope_N_per_bar=float(a), intercept_N=0.0, r2=float(r2), fit_kind="origin")


def calibrate_pc_to_thrust_intercept(pcg: np.ndarray, thrust: np.ndarray) -> CalibrationResult:
    a, b, r2 = linear_fit_with_intercept(pcg, thrust)
    return CalibrationResult(slope_N_per_bar=a, intercept_N=b, r2=r2, fit_kind="intercept")


def reconstruct_thrust_from_pc(pc: np.ndarray, calibration: CalibrationResult, pc0: float) -> np.ndarray:
    pcg = np.maximum(pc - pc0, 0.0)
    if calibration.fit_kind == "origin":
        f = calibration.slope_N_per_bar * pcg
    else:
        f = calibration.slope_N_per_bar * pcg + calibration.intercept_N
    return np.maximum(f, 0.0)


def export_rasp_eng(path: str, name: str, t: np.ndarray, thrust: np.ndarray,
                    diameter_mm: int = 100, length_mm: int = 1330,
                    delays: str = "0", prop_mass_kg: float = 2.300,
                    total_mass_kg: float = 9.200, manufacturer: str = "FlightRecon",
                    header: Optional[List[str]] = None) -> None:
    with open(path, "w", encoding="utf-8") as f:
        if header:
            for line in header:
                f.write(f"; {line}\n")
        f.write(f"{name} {diameter_mm} {length_mm} {delays} {prop_mass_kg:.3f} {total_mass_kg:.3f} {manufacturer}\n")
        for ti, fi in zip(t, thrust):
            f.write(f"  {ti:.4f}    {fi:.3f}\n")
