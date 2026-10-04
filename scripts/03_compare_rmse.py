import csv
from pathlib import Path

import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parents[1]
METRICS_DIR = PROJECT_ROOT / "outputs" / "metrics"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "evaluation"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_rmse(filename):
    lead_times = []
    rmse_values = []

    with open(METRICS_DIR / filename, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            lead_times.append(int(row["lead_time_min"]))
            rmse_values.append(float(row["rmse"]))

    return lead_times, rmse_values


persistence_x, persistence_y = load_rmse("persistence_rmse.csv")
optical_flow_x, optical_flow_y = load_rmse("optical_flow_rmse.csv")
sprog_x, sprog_y = load_rmse("sprog_rmse.csv")
steps_x, steps_y = load_rmse("steps_rmse.csv")


plt.figure(figsize=(8, 5))

plt.plot(
    persistence_x,
    persistence_y,
    marker="o",
    label="Persistence",
)

plt.plot(
    optical_flow_x,
    optical_flow_y,
    marker="o",
    label="Optical Flow",
)

plt.plot(
    sprog_x,
    sprog_y,
    marker="o",
    label="S-PROG",
)

plt.plot(
    steps_x,
    steps_y,
    marker="o",
    label="STEPS Ensemble Mean",
)

plt.xlabel("Lead Time (min)")
plt.ylabel("RMSE (mm/h)")
plt.title("Nowcasting Method Comparison")
plt.grid(True)
plt.legend()

plt.tight_layout()

output_path = OUTPUT_DIR / "rmse_method_comparison.png"

plt.savefig(output_path, dpi=150)
plt.close()

print("对比曲线已保存：")
print(output_path)