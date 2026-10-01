import numpy as np
import matplotlib.pyplot as plt
import os


lead_minutes = np.arange(5, 65, 5)

persistence_rmse = [
    0.5476,
    0.6250,
    0.6587,
    0.6956,
    0.7175,
    0.7321,
    0.7536,
    0.7552,
    0.7645,
    0.7752,
    0.7829,
    0.8000,
]

optical_flow_rmse = [
    0.3449,
    0.4189,
    0.4773,
    0.5202,
    0.5604,
    0.5778,
    0.6009,
    0.6175,
    0.6361,
    0.6510,
    0.6548,
    0.6765,
]


os.makedirs("outputs/evaluation", exist_ok=True)

plt.figure(figsize=(8, 5))

plt.plot(
    lead_minutes,
    persistence_rmse,
    marker="o",
    label="Persistence"
)

plt.plot(
    lead_minutes,
    optical_flow_rmse,
    marker="o",
    label="Optical Flow"
)

plt.xlabel("Lead Time (min)")
plt.ylabel("RMSE (mm/h)")
plt.title("Persistence vs Optical Flow")
plt.grid(True)
plt.legend()

plt.tight_layout()

plt.savefig(
    "outputs/evaluation/persistence_vs_optical_flow_rmse.png",
    dpi=150
)

plt.close()

print("对比曲线已保存：")
print("outputs/evaluation/persistence_vs_optical_flow_rmse.png")