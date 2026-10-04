import csv
from pathlib import Path

import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CSV_PATH = (
    PROJECT_ROOT
    / "outputs"
    / "metrics"
    / "steps_crps.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "evaluation"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


lead_times = []
crps_values = []

with open(
    CSV_PATH,
    "r",
    encoding="utf-8",
) as f:

    reader = csv.DictReader(f)

    for row in reader:
        lead_times.append(
            int(row["lead_time_min"])
        )

        crps_values.append(
            float(row["crps"])
        )


plt.figure(figsize=(8, 5))

plt.plot(
    lead_times,
    crps_values,
    marker="o",
)

plt.xlabel("Lead Time (min)")
plt.ylabel("CRPS (mm/h)")
plt.title("STEPS CRPS")
plt.xticks(range(5, 65, 5))
plt.grid(True)
plt.tight_layout()

output_path = (
    OUTPUT_DIR
    / "steps_crps.png"
)

plt.savefig(
    output_path,
    dpi=150,
)

plt.close()

print("CRPS 曲线已保存：")
print(output_path)