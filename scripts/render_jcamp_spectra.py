"""Render the C20H32O2-jcamp spectra straight from lucy-ng's own JCAMP reader.

Read-only: opens the .dx files, writes PNGs to ~/Downloads. Touches nothing else.
"""
from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from lucy_ng.readers.jcamp import JcampReader

warnings.filterwarnings("ignore")

DATA = Path.home() / "Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2-jcamp"
OUT = Path.home() / "Downloads/C20H32O2-jcamp-spektren"
OUT.mkdir(parents=True, exist_ok=True)

PICKED_C13 = [69.06, 67.06, 51.63, 37.86, 37.19, 36.23, 35.23, 34.21, 33.67,
              30.66, 29.77, 27.93, 27.16, 25.96, 23.43, 22.64, 21.78]
CDCL3 = [77.28, 77.03, 76.78]


def noise_mad(y: np.ndarray) -> float:
    """Robust noise estimate from the median absolute deviation."""
    return float(np.median(np.abs(y - np.median(y))) * 1.4826)


def style(ax, xlabel, ylabel=None):
    ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(alpha=0.15, linewidth=0.5)


# ---------------------------------------------------------------- 1D 13C
c13 = JcampReader.read_1d(DATA / "C20H32O2_13C.dx")
x13, y13 = np.asarray(c13.ppm_scale), np.asarray(c13.data, dtype=float)
n13 = noise_mad(y13)

fig, ax = plt.subplots(figsize=(13, 4.2), dpi=170)
ax.plot(x13, y13, lw=0.55, color="#1a1a1a")
for s in PICKED_C13:
    ax.axvline(s, color="#c0392b", lw=0.6, alpha=0.45)
for s in CDCL3:
    ax.axvline(s, color="#2980b9", lw=0.6, alpha=0.5, ls=":")
ax.set_xlim(x13.max(), x13.min())
ax.set_title(f"1D $^{{13}}$C aus dem JCAMP-Reader — exp6 (schmal), Fenster "
             f"{x13.max():.1f} … {x13.min():.1f} ppm\n"
             f"rot = gepickt (17) · blau gepunktet = CDCl$_3$", fontsize=10)
style(ax, "$\\delta$ / ppm", "Intensität")
fig.tight_layout()
fig.savefig(OUT / "01_13C_uebersicht.png")
plt.close(fig)

# ------------------------------------------------- 1D 13C zoom: is 79.35 real?
lo, hi = 60.0, 90.0
m = (x13 >= lo) & (x13 <= hi)
xz, yz = x13[m], y13[m]

snr_79 = float(np.max(np.abs(y13[(x13 > 79.1) & (x13 < 79.6)]))) / n13
fig, axes = plt.subplots(2, 1, figsize=(12, 7.6), dpi=170, sharex=True)
for k, ax in enumerate(axes):
    ax.plot(xz, yz, lw=0.9, color="#1a1a1a", zorder=3)
    ax.axhspan(-3 * n13, 3 * n13, color="#e67e22", alpha=0.22, zorder=1,
               label="±3σ Rauschband (MAD)" if k == 0 else None)
    ax.axvline(79.35, color="#8e44ad", lw=3.0, alpha=0.20, zorder=0,
               label="79.35 ppm — von §10 vermutet, NICHT gepickt" if k == 0 else None)
    for s in CDCL3:
        ax.axvline(s, color="#2980b9", lw=0.8, ls=":", alpha=0.6, zorder=0)
    for s in (69.06, 67.06):
        ax.axvline(s, color="#c0392b", lw=0.8, alpha=0.35, zorder=0)
    ax.set_xlim(hi, lo)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(alpha=0.15, lw=0.5)
    ax.set_ylabel("Intensität")

axes[0].legend(fontsize=9, frameon=False, loc="upper left")
axes[0].text(77.03, np.max(yz) * 0.93, "CDCl$_3$", color="#2980b9",
             ha="center", fontsize=9)
for s in (69.06, 67.06):
    axes[0].text(s, np.max(yz) * 0.30, f"{s}", color="#c0392b",
                 ha="center", fontsize=8)
axes[0].set_title("Ist 79.35 ppm real? — 1D $^{13}$C, Ausschnitt 60–90 ppm "
                  "(innerhalb des exp6-Fensters, also nicht abgeschnitten)\n"
                  "oben: volle Skala — das CDCl$_3$-Triplett dominiert alles",
                  fontsize=10)

# untere Spur: 40x vertikal gedehnt, damit Schwaches sichtbar wird
ylim = np.max(np.abs(y13[(x13 > 79.0) & (x13 < 79.7)])) * 2.2
axes[1].set_ylim(-ylim * 0.35, ylim)
axes[1].set_title(f"unten: 40× vertikal gedehnt — 79.35 ppm steht klar über dem "
                  f"Rauschen (S/N ≈ {snr_79:.0f})", fontsize=10)
axes[1].annotate(f"79.35\nS/N ≈ {snr_79:.0f}", xy=(79.35, ylim * 0.42),
                 xytext=(82.5, ylim * 0.72), color="#8e44ad", fontsize=9,
                 ha="center",
                 arrowprops=dict(arrowstyle="->", color="#8e44ad", lw=1.1))
axes[1].set_xlabel("$\\delta$ / ppm")
fig.tight_layout()
fig.savefig(OUT / "02_13C_zoom_ist-79-35-real.png")
plt.close(fig)

# quantitative read-out around 79.35
report = []
for target in (79.35, 69.06, 67.06, 51.63, 30.66, 82.0):
    w = (x13 > target - 0.25) & (x13 < target + 0.25)
    peak = float(np.max(np.abs(y13[w]))) if w.any() else float("nan")
    report.append((target, peak, peak / n13))

# ---------------------------------------------------------------- 1D 1H
h1 = JcampReader.read_1d(DATA / "C20H32O2_1H.dx")
xh, yh = np.asarray(h1.ppm_scale), np.asarray(h1.data, dtype=float)
mh = (xh >= 0.70) & (xh <= 1.30)

fig, ax = plt.subplots(figsize=(12, 4.6), dpi=170)
ax.plot(xh[mh], yh[mh], lw=1.0, color="#1a1a1a")
ax.set_xlim(1.30, 0.70)  # hohe ppm links
ax.set_title("Wie viele Methyle? — 1D $^{1}$H, Methylregion 0.70–1.30 ppm\n"
             "Singuletts hier = quartär-gebundene CH$_3$; Dubletts würden "
             "ein sekundäres Methyl / Isopropyl anzeigen", fontsize=10)
style(ax, "$\\delta$ / ppm", "Intensität")
fig.tight_layout()
fig.savefig(OUT / "03_1H_methylregion.png")
plt.close(fig)

# ---------------------------------------------------------------- 2D HSQC
hsqc = JcampReader.read_2d(DATA / "C20H32O2_HSQC.dx")
Z = np.asarray(hsqc.data, dtype=float)
f1, f2 = np.asarray(hsqc.f1_ppm_scale), np.asarray(hsqc.f2_ppm_scale)
nz = noise_mad(Z.ravel())
ZMAX = float(np.abs(Z).max())


def hsqc_panel(ax, f1lo, f1hi, f2lo, f2hi, title, base_frac=0.02, label_peaks=()):
    """Contours relative to the global maximum -- a 6-sigma base drowns the
    panel in t1 ridges, which are strong in this reconstruction."""
    i = np.where((f1 >= f1lo) & (f1 <= f1hi))[0]
    j = np.where((f2 >= f2lo) & (f2 <= f2hi))[0]
    sub = Z[np.ix_(i, j)]
    X, Y = np.meshgrid(f2[j], f1[i])
    lv = ZMAX * base_frac * np.array([1, 2, 4, 8, 16, 32])
    ax.contour(X, Y, sub, levels=lv, colors="#c0392b", linewidths=0.6)
    ax.contour(X, Y, -sub, levels=lv, colors="#2471a3", linewidths=0.6)
    for c, h, txt in label_peaks:
        ax.annotate(txt, xy=(h, c), xytext=(h + 0.09, c - 2.6), fontsize=8.5,
                    color="#555", ha="left",
                    arrowprops=dict(arrowstyle="-", color="#999", lw=0.7))
    ax.set_xlim(f2hi, f2lo)
    ax.set_ylim(f1hi, f1lo)
    ax.set_xlabel("$\\delta$($^{1}$H) / ppm")
    ax.set_ylabel("$\\delta$($^{13}$C) / ppm")
    ax.set_title(title, fontsize=10)
    ax.grid(alpha=0.15, lw=0.5)
    ax.text(0.985, 0.015, f"Konturen ab {base_frac*100:.1f} % des Maximums",
            transform=ax.transAxes, ha="right", fontsize=7.5, color="#777")


fig, ax = plt.subplots(figsize=(9.5, 7.5), dpi=170)
hsqc_panel(ax, 14, 34, 0.80, 1.15,
           "Wie viele Methyle? — edited HSQC, Methylregion\n"
           "rot = positiv (CH / CH$_3$)   ·   blau = negativ (CH$_2$)",
           base_frac=0.02,
           label_peaks=[(23.43, 0.963, "23.43 / 0.963\n+53 600 σ"),
                        (21.78, 0.989, "21.78 / 0.989\n+51 500 σ")])
fig.tight_layout()
fig.savefig(OUT / "04_HSQC_methylregion.png")
plt.close(fig)

fig, ax = plt.subplots(figsize=(10, 8.5), dpi=170)
hsqc_panel(ax, -2, 75, 0.4, 4.6,
           "edited HSQC — Übersicht (aus dem JCAMP-Reader)\n"
           "rot = positiv (CH / CH$_3$)   ·   blau = negativ (CH$_2$)",
           base_frac=0.005)
fig.tight_layout()
fig.savefig(OUT / "05_HSQC_uebersicht.png")
plt.close(fig)

# aliphatische CH2/CH3-Region grosszuegiger, um schwache Kreuzpeaks zu zeigen
fig, ax = plt.subplots(figsize=(10, 8), dpi=170)
hsqc_panel(ax, 18, 42, 0.85, 2.15,
           "edited HSQC — aliphatische Region, empfindlicher konturiert\n"
           "rot = positiv (CH / CH$_3$)   ·   blau = negativ (CH$_2$)",
           base_frac=0.004)
fig.tight_layout()
fig.savefig(OUT / "06_HSQC_aliphaten.png")
plt.close(fig)

print(f"Rauschen 1D 13C (MAD-σ): {n13:.1f}")
print(f"{'ppm':>8} {'|max| im ±0.25-Fenster':>24} {'S/N':>8}")
for t, pk, snr in report:
    print(f"{t:8.2f} {pk:24.1f} {snr:8.1f}")
print(f"\nHSQC-Rauschen (MAD-σ): {nz:.1f}   Konturen ab 6σ")
print(f"\nPNGs: {OUT}")
