"""Inflow waveform for ladder level L3: the U-bend's half-sine systole (peak 14.6 L/min at 0.2 s, 0.4 s long)
followed by a reverse lobe in early diastole and a small forward trickle, 0.8 s period. Same peak and nearly
the same mean as the U-bend waveform, so the only change is the reverse phase (and the Womersley profile that
a reversing waveform needs). Writes the CSV in the AortaCFD-app format (Time s, Flowrate m3/s) and a check plot.
Usage: python3 make_reversing_inflow.py UBEND_CSV OUT_CSV OUT_PNG"""
import sys
import numpy as np

ubend_csv, out_csv, out_png = sys.argv[1:4]
u = np.genfromtxt(ubend_csv, delimiter=",", names=True)
t = np.round(np.arange(0, 0.8001, 0.01), 2)
Qp = u["Flowrate"].max()  # 2.43e-4 m3/s = 14.6 L/min
q = np.zeros_like(t)
sys_end, rev_end = 0.40, 0.52
m = t < sys_end
q[m] = Qp * np.sin(np.pi * t[m] / sys_end)
m = (t >= sys_end) & (t < rev_end)
q[m] = -0.25 * Qp * np.sin(np.pi * (t[m] - sys_end) / (rev_end - sys_end))
m = t >= rev_end
q[m] = 0.04 * Qp * np.sin(np.pi * (t[m] - rev_end) / (0.8 - rev_end)) ** 0.5  # a low forward trickle that returns to 0
q[-1] = 0.0  # periodic: the cycle starts and ends at zero flow
with open(out_csv, "w") as f:
    f.write("Time,Flowrate\n")
    for ti, qi in zip(t, q):
        f.write(f"{ti:.6e},{qi:.6e}\n")
mean_new, mean_u = q.mean(), u["Flowrate"].mean()
print(f"peak {q.max() * 6e4:.2f} L/min at t = {t[q.argmax()]:.2f} s; reverse peak {q.min() * 6e4:.2f} L/min at t = {t[q.argmin()]:.2f} s; "
      f"mean {mean_new * 6e4:.2f} L/min (U-bend {mean_u * 6e4:.2f}); reverse phase {sys_end}-{rev_end} s")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(8, 3.6), dpi=160)
ax.plot(u["Time"], u["Flowrate"] * 6e4, color="#6f7784", lw=2, label="U-bend (L0 to L2): half-sine")
ax.plot(t, q * 6e4, color="#b83232", lw=2, label="L3: with a reverse phase")
ax.axhline(0, color="k", lw=0.8)
ax.set_xlabel("time (s)"); ax.set_ylabel("inlet flow (L/min)"); ax.legend(frameon=False); ax.grid(alpha=0.3)
fig.tight_layout(); fig.savefig(out_png)
