"""
process_motor_sweep.py
----------------------
Processes raw contra-rotating motor sweep CSV data.

Each test sample lasts 3 seconds. To avoid the transient at the start
of each sample, this script averages measurements between T_START and
T_END seconds after each throttle transition.

Input CSV structure (from actual data):
  timestamp   - ISO 8601 datetime string (e.g. 2026-04-04T17:08:02.824)
  throttle1   - throttle 1 setpoint
  throttle2   - throttle 2 setpoint
  loadcell1   - load cell 1 reading
  loadcell2   - load cell 2 reading
  rpm1, rpm2  - motor RPMs
  cell1_v, cell2_v, cell3_v - cell voltages
  pack_v      - pack voltage

Edit the CONFIG section below to match your file paths and preferences.
"""

import pandas as pd
import numpy as np

# ─────────────────────────── CONFIG ────────────────────────────────────────

INPUT_CSV   = "log_20260405_092906.csv"   # path to your input file
OUTPUT_CSV  = "processed_sweep_2.csv"  # path for the output file

# Column names in your CSV
TIME_COL      = "timestamp"                              # datetime column
THROTTLE1_COL = "throttle1"
THROTTLE2_COL = "throttle2"
MEAS_COLS     = ["loadcell1", "loadcell2", "rpm1", "rpm2", "pack_v",
                 "cell1_v", "cell2_v", "cell3_v"]        # columns to average

# Averaging window within each 3-second sample (seconds after transition)
SAMPLE_DURATION = 3.0   # total duration of each sample (seconds)
T_START         = 1.0   # start of averaging window (seconds after transition)
T_END           = 2.5   # end of averaging window   (seconds after transition)

# ───────────────────────────────────────────────────────────────────────────


def detect_sample_boundaries(df: pd.DataFrame) -> list:
    """
    Returns the positional indices (iloc-style) where a new throttle
    combination starts. A new sample begins whenever either throttle changes.
    """
    t1 = df[THROTTLE1_COL].values
    t2 = df[THROTTLE2_COL].values

    boundaries = [0]
    for i in range(1, len(df)):
        if t1[i] != t1[i - 1] or t2[i] != t2[i - 1]:
            boundaries.append(i)
    return boundaries


def average_window(sample_df: pd.DataFrame, t0: float) -> dict:
    """
    Given the rows for one sample and the elapsed-seconds value at the
    start of that sample (t0), return the mean of each measurement
    column within [t0 + T_START, t0 + T_END].
    """
    t_start_abs = t0 + T_START
    t_end_abs   = t0 + T_END

    window = sample_df[
        (sample_df["_elapsed_s"] >= t_start_abs) &
        (sample_df["_elapsed_s"] <= t_end_abs)
    ]

    if window.empty:
        print(f"  ⚠  No rows in averaging window for sample at t={t0:.3f}s "
              f"(throttle1={sample_df[THROTTLE1_COL].iloc[0]}, "
              f"throttle2={sample_df[THROTTLE2_COL].iloc[0]}). "
              f"Returning NaN.")
        return {col: np.nan for col in MEAS_COLS}

    return window[MEAS_COLS].mean().to_dict()


def process(input_csv: str, output_csv: str) -> pd.DataFrame:
    print(f"Reading {input_csv} ...")
    df = pd.read_csv(input_csv)

    # Basic validation
    required_cols = [TIME_COL, THROTTLE1_COL, THROTTLE2_COL] + MEAS_COLS
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(
            f"Missing columns in CSV: {missing}\n"
            f"Available columns: {list(df.columns)}\n"
            f"Edit the CONFIG section in this script to match your column names."
        )

    # Parse ISO 8601 datetime timestamps → elapsed seconds (float)
    df[TIME_COL] = pd.to_datetime(df[TIME_COL])
    t_origin = df[TIME_COL].iloc[0]
    df["_elapsed_s"] = (df[TIME_COL] - t_origin).dt.total_seconds()

    print(f"  {len(df)} rows loaded.")
    print(f"  Time range: 0 – {df['_elapsed_s'].iloc[-1]:.3f} s")
    print(f"  Averaging window: {T_START}s – {T_END}s after each transition.\n")

    boundaries = detect_sample_boundaries(df)
    print(f"  Detected {len(boundaries)} samples.")

    records = []

    for i, start_pos in enumerate(boundaries):
        end_pos = boundaries[i + 1] if i + 1 < len(boundaries) else len(df)

        sample_df = df.iloc[start_pos:end_pos].copy()
        t0 = sample_df["_elapsed_s"].iloc[0]

        throttle1 = sample_df[THROTTLE1_COL].iloc[0]
        throttle2 = sample_df[THROTTLE2_COL].iloc[0]

        avgs = average_window(sample_df, t0)

        n_in_window = int(
            ((sample_df["_elapsed_s"] >= t0 + T_START) &
             (sample_df["_elapsed_s"] <= t0 + T_END)).sum()
        )

        record = {
            THROTTLE1_COL: throttle1,
            THROTTLE2_COL: throttle2,
            "t_sample_start_s": round(t0, 3),
            "n_rows_in_window": n_in_window,
            **{f"avg_{col}": avgs[col] for col in MEAS_COLS},
        }
        records.append(record)

    out_df = pd.DataFrame(records)
    out_df.to_csv(output_csv, index=False)

    print(f"\nDone. {len(out_df)} rows written to {output_csv}")
    print(out_df.head(10).to_string(index=False))

    return out_df


if __name__ == "__main__":
    process(INPUT_CSV, OUTPUT_CSV)