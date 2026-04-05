"""
plot_sweep.py
-------------
Visualises processed contra-rotating motor sweep data as 2-D heatmaps.
X-axis = throttle1, Y-axis = throttle2, colour = measurement value.

Generates 8 PNG files:
  raw_rpm1.png, raw_rpm2.png, raw_loadcell1.png, raw_loadcell2.png
  scaled_rpm1.png, scaled_rpm2.png, scaled_loadcell1.png, scaled_loadcell2.png

The "scaled" versions correct each measurement back to what it would be
at NOMINAL_VOLTAGE by multiplying by (NOMINAL_VOLTAGE / avg_pack_v),
accounting for the proportional relationship between voltage and output.

Edit CONFIG to match your file paths and voltage reference.
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.tri as tri
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable

# ─────────────────────────── CONFIG ────────────────────────────────────────

INPUT_CSV       = "processed_sweep.csv"   # output of process_motor_sweep.py
OUTPUT_DIR      = "plots"                 # folder where PNGs are saved
NOMINAL_VOLTAGE = 12.6                    # reference voltage for scaling (V)

THROTTLE1_COL = "throttle1"
THROTTLE2_COL = "throttle2"
PACK_V_COL    = "avg_pack_v"

# Channels to plot: (column_name, display_label, colormap)
CHANNELS = [
    ("avg_rpm1",      "RPM — Motor 1",      "plasma"),
    ("avg_rpm2",      "RPM — Motor 2",      "plasma"),
    ("avg_loadcell1", "Load Cell 1 (raw units)", "coolwarm"),
    ("avg_loadcell2", "Load Cell 2 (raw units)", "coolwarm"),
]

# ───────────────────────────────────────────────────────────────────────────

STYLE = {
    "figure.facecolor":  "#0f1117",
    "axes.facecolor":    "#0f1117",
    "axes.labelcolor":   "#e0e0e0",
    "axes.titlecolor":   "#ffffff",
    "axes.edgecolor":    "#333333",
    "xtick.color":       "#a0a0a0",
    "ytick.color":       "#a0a0a0",
    "text.color":        "#e0e0e0",
    "grid.color":        "#222222",
    "grid.linestyle":    "--",
    "grid.alpha":        0.5,
    "font.family":       "monospace",
}


def make_heatmap(ax, x, y, z, title, xlabel, ylabel, cmap, vmin=None, vmax=None):
    """
    Renders a scatter-based heatmap (works for irregular grids too).
    Uses a regular grid interpolation when data is on a clean grid,
    otherwise falls back to a triangulated contour fill.
    """
    x_unique = np.sort(np.unique(x))
    y_unique = np.sort(np.unique(y))

    # Try regular grid path first
    try:
        grid_z = np.full((len(y_unique), len(x_unique)), np.nan)
        xi_map = {v: i for i, v in enumerate(x_unique)}
        yi_map = {v: i for i, v in enumerate(y_unique)}
        for xi, yi, zi in zip(x, y, z):
            if not np.isnan(zi):
                grid_z[yi_map[yi], xi_map[xi]] = zi

        vmin = vmin if vmin is not None else np.nanmin(grid_z)
        vmax = vmax if vmax is not None else np.nanmax(grid_z)

        im = ax.pcolormesh(
            x_unique, y_unique, grid_z,
            cmap=cmap, vmin=vmin, vmax=vmax,
            shading="nearest"
        )

        # Annotate each cell with its value
        for i, yv in enumerate(y_unique):
            for j, xv in enumerate(x_unique):
                val = grid_z[i, j]
                if not np.isnan(val):
                    text_color = "white" if abs(val - vmin) / (vmax - vmin + 1e-9) < 0.6 else "#111"
                    ax.text(xv, yv, f"{val:.0f}",
                            ha="center", va="center",
                            fontsize=7, color=text_color, fontweight="bold")

    except Exception:
        # Fallback: triangulated contour
        mask = ~np.isnan(z)
        triang = tri.Triangulation(x[mask], y[mask])
        vmin = vmin if vmin is not None else np.nanmin(z)
        vmax = vmax if vmax is not None else np.nanmax(z)
        im = ax.tricontourf(triang, z[mask], levels=20, cmap=cmap, vmin=vmin, vmax=vmax)

    ax.set_title(title, fontsize=13, fontweight="bold", pad=10)
    ax.set_xlabel(xlabel, fontsize=10, labelpad=6)
    ax.set_ylabel(ylabel, fontsize=10, labelpad=6)
    ax.grid(True)
    ax.set_xticks(x_unique)
    ax.set_yticks(y_unique)

    return im


def save_plot(df, col, label, cmap, filename, title, voltage_scale=None):
    """Renders one heatmap and saves it as a PNG."""
    with plt.style.context(STYLE):
        fig, ax = plt.subplots(figsize=(8, 6.5))
        fig.patch.set_facecolor(STYLE["figure.facecolor"])

        x = df[THROTTLE1_COL].values
        y = df[THROTTLE2_COL].values
        z = df[col].values.copy().astype(float)

        if voltage_scale is not None:
            # Scale: multiply by (nominal / actual) to get nominal-equivalent value
            z = z * voltage_scale

        mask = ~np.isnan(z)
        im = make_heatmap(ax, x[mask], y[mask], z[mask],
                          title=title,
                          xlabel="Throttle 1 (%)",
                          ylabel="Throttle 2 (%)",
                          cmap=cmap)

        # Colorbar
        cbar = fig.colorbar(
            ScalarMappable(norm=Normalize(vmin=np.nanmin(z), vmax=np.nanmax(z)), cmap=cmap),
            ax=ax, pad=0.02, fraction=0.046
        )
        cbar.set_label(label, fontsize=9, color="#e0e0e0")
        cbar.ax.yaxis.set_tick_params(color="#a0a0a0")
        plt.setp(cbar.ax.yaxis.get_ticklabels(), color="#a0a0a0", fontsize=8)

        fig.tight_layout()
        out_path = os.path.join(OUTPUT_DIR, filename)
        fig.savefig(out_path, dpi=150, bbox_inches="tight",
                    facecolor=STYLE["figure.facecolor"])
        plt.close(fig)
        print(f"  Saved: {out_path}")


def main():
    print(f"Reading {INPUT_CSV} ...")
    df = pd.read_csv(INPUT_CSV)

    missing = [c for c in [THROTTLE1_COL, THROTTLE2_COL, PACK_V_COL] + [ch[0] for ch in CHANNELS]
               if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}\nAvailable: {list(df.columns)}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Voltage scaling factor per row
    voltage_scale = NOMINAL_VOLTAGE / df[PACK_V_COL].values

    print(f"\nGenerating RAW plots ...")
    for col, label, cmap in CHANNELS:
        tag = col.replace("avg_", "")
        save_plot(
            df, col, label, cmap,
            filename=f"raw_{tag}.png",
            title=f"{label}\n(raw, unscaled)",
        )

    print(f"\nGenerating VOLTAGE-SCALED plots (ref = {NOMINAL_VOLTAGE} V) ...")
    for col, label, cmap in CHANNELS:
        tag = col.replace("avg_", "")
        save_plot(
            df, col, f"{label} @ {NOMINAL_VOLTAGE}V", cmap,
            filename=f"scaled_{tag}.png",
            title=f"{label}\n(scaled to {NOMINAL_VOLTAGE} V reference)",
            voltage_scale=voltage_scale,
        )

    print(f"\nDone — {len(CHANNELS) * 2} plots saved to '{OUTPUT_DIR}/'")


if __name__ == "__main__":
    main()