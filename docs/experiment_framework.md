# FMI 单案例与批量入口

在项目根目录激活 `radar-nowcasting`。第一版保持所有算法参数、计算顺序和指标定义。
不要求 `configs/pystepsrc`：各任务继续读取 PySTEPS 当前 `rcparams.data_sources["fmi"]`
中的文件规则、时间步长及 importer。数据根目录统一为项目内
`data/sample/pysteps-data/radar/fmi/pgm`，不会修改全局 rcparams 或系统环境。

## 运行

```bash
conda activate radar-nowcasting
python scripts/run_case.py --start-time 201609281600 --dry-run
python scripts/run_case.py --start-time 201609281600
python scripts/run_case.py --start-time 201609281600 --tasks 09,10 --overwrite
python scripts/run_cases.py --cases configs/cases.json --dry-run
```

时间必须是 UTC `YYYYMMDDHHMM`，且位于 5 分钟边界；案例编号自动生成。
`configs/cases.json` 只有 `start_times` 字符串列表，初始仅包含原参考案例。
以后移除批量命令的 `--dry-run` 才会真正运行该清单；本次未执行真实多案例实验。
入口使用当前 Python 解释器启动子进程，工作目录固定为项目根目录，串行运行。

`--dry-run` 只查输入、任务依赖和输出冲突，不创建案例目录、不读取雷达数组或运行算法。
完整流程要求起报前 10 分钟至后 60 分钟共 15 帧；选定任务按其实际需要检查。
缺帧直接失败，不填充、不插值、不缩短时效。绘图任务不要求雷达文件。

## 输出与覆盖

```text
outputs/cases/fmi_20160928T160000Z/
  forecasts/       # persistence / optical_flow / sprog / steps_mean.npy
  steps/           # 原始 dB ensemble 和成员图
  metrics/         # 原有 CSV
  evaluation/      # 原有对比与概率评估图
  persistence/     # 保留原算法图的子目录
  optical_flow/
  sprog/
  logs/            # 每个任务一个编号日志
  run_manifest.json
```

默认拒绝已有案例目录。`--overwrite` 只重跑所选任务、覆盖它们的日志和产物，不删除整个目录。
已有目录必须带有相同 case_id 和 start_time 的有效 manifest。运行记录仅保存案例、任务、
状态、UTC 起止时间和必要错误信息，不包含产物校验和、环境版本追踪或 stale 管理。
记录保留未选任务的上次状态；顶层状态表示本次选定任务的执行结果，不代表所有历史任务一致。
若重跑上游预测，应显式同时选择相关下游任务，或默认重跑全流程；框架不会自动判断旧评估是否过期。
不要同时运行写入同一案例的两个进程。

原脚本无参数时仍使用 `201609281600`、原 `outputs/`，包括原有覆盖行为及部分图表的
cwd 相对路径；应像以前一样从项目根目录运行。可配置运行请使用 `run_case.py`，不要直接使用
旧脚本内部的 `--case-run` 标志。旧 `outputs/` 基准不迁移。

## 任务选择与依赖

`--tasks` 接收不重复的两位任务编号，以固定依赖顺序执行，不以参数输入顺序执行。
默认顺序：`01,02,04,05,06,03,07,08,09,10,11,12,13,14`。

| 任务 | 作用 | 前置任务 |
| --- | --- | --- |
| 01、02、04、05 | 四种预测及脚本自带的诊断/评估 | 无 |
| 06 | STEPS 均值、RMSE、成员图 | 05 |
| 03 | 四方法 RMSE 图 | 01、02、04、06 |
| 07 | CSI / POD / FAR | 01、02、04、06 |
| 08 | 多阈值指标图 | 07 |
| 09、11、13、14 | Brier、CRPS、可靠性、Spread-Skill | 05 |
| 10、12 | Brier、CRPS 曲线 | 09、11（分别） |

未选中的前置任务必须在同一案例 manifest 中成功，且所需文件存在且非空。
否则停止该案例并报告缺少的依赖；不自动补跑模型。
13、14 的计算与绘图仍是同一任务，保留不同指标的有效值掩码和统计方式。
任务失败后保留日志与部分产物，后续任务不执行；批量入口继续其他案例并输出 JSON 汇总，
有任一失败时返回非零退出码。人工 Ctrl+C 中断则停止整个批次。

## 验证

```bash
python -m unittest discover -s tests -v
python -m compileall -q scripts tests
```

单元测试使用临时目录和模拟任务，不调用模型。
重构回归只运行参考案例，逐元素比较预测数组与原结果，比较 CSV 数值与图表。
旧基准仅做只读检查。`configs/pystepsrc`、数据、结果、日志不加入 Git。

首次重构验收（2026-10-04）：17 项模拟任务测试通过，14 个原脚本的计算 AST
在排除时间/路径接入后保持一致。只对 `201609281600` 完成一次真实全流程回归：
5 个预测数组逐元素一致（含 NaN），10 份 CSV 字节一致，23 张 PNG 像素一致；
旧 outputs 的全部文件校验值未变化。新案例约占 1.2 GB，14 项任务均成功。
批量入口仅预检了单条参考清单，未运行真实多案例。
