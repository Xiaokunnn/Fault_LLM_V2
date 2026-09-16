# RP3 服务器实验执行说明（2026-09-06）

## 先看边界

本次补的是**可执行的核心实验链路**，不是已经得到实验结果。
服务器的 7B 应为冻结 RP2 实际使用的 `Qwen2.5-7B-Instruct`，还需要 `BAAI-bge-m3`。
仅有任意一个 7B 模型不足以精确复现教师；不能把另一款 7B 改目录名冒充原教师。
学生是四头 LEC，不是训练 7B。边缘工具可以由 LLM 调用，也可以直接用 JSON 调用。

本次默认可运行版本使用 256 维字符 n-gram 哈希查询特征、288 维证据特征。
该编码器不需要另下模型、没有可学习参数，能够处理新问题；它是**轻量特征基线**，不是已验证的语义编码器创新。
后续与小型语义编码器比较时，必须把编码器参数、时延与内存一并计入，不能只计算 LEC。

## 1. 上传与安装

本次检查时 `zxk / 192.168.1.107`、`wangjq / 192.168.0.199` 的 SSH 均连接超时，
因此没有完成实际上传，也未确认服务器目录或模型状态。旧文档目录是 `~/08-zxk/Fault_LLM_V2`，使用前须确认。

本地打包命令（不会包含模型、密钥、原始 PDF、论文草稿或其他无关未提交改动）：

```powershell
python scripts/package_rp3_upload.py --output .tmp/rp3_upload_20260906.tar.gz
scp .tmp/rp3_upload_20260906.tar.gz YOUR_SSH_HOST:~/rp3_upload_20260906.tar.gz
```

用实际 SSH 配置名替换 `YOUR_SSH_HOST`。确认目标目录后，在服务器执行：

```bash
RP3_STAGE=$(mktemp -d /tmp/rp3-upload.XXXXXX)
tar -xzf ~/rp3_upload_20260906.tar.gz -C "$RP3_STAGE"
python "$RP3_STAGE/scripts/install_rp3_upload.py" --target ~/08-zxk/Fault_LLM_V2
# 查看上一步列出的改动范围后，应用：
python "$RP3_STAGE/scripts/install_rp3_upload.py" --target ~/08-zxk/Fault_LLM_V2 --apply
```

安装器逐文件校验 SHA-256；覆盖前把服务器旧文件保存到
`.rp3_upload_backups/<UTC时间>/`，并保存回滚清单。不会删除远程模型、缓存、论文或实验结果。
包内少量 RP2 冻结资产是原字节副本，用来解决原冻结清单中混合 LF/CRLF 文件的校验问题，
没有改动论文数字或教师参数。不要用自动换行转换工具处理这些冻结数据。

## 2. 环境和模型

```bash
cd ~/08-zxk/Fault_LLM_V2
source .venv/bin/activate
python -m pip install -r requirements-rp3-server.txt
nvidia-smi
python -c 'import torch; print(torch.__version__, torch.cuda.is_available())'
bash scripts/run_rp3_experiments.sh preflight
python -m pytest tests/unit/test_research_point_3_*.py -q
```

必须存在：

```text
data/model/Qwen2.5-7B-Instruct/config.json + 模型权重、tokenizer 文件
data/model/BAAI-bge-m3/config.json + 模型权重、tokenizer 文件
data/kg/marine_pump/triples/KG_v1_validated/               # 208/203/281
data/interim/parsed_pages/corpus_v2/MP008.pages.v2.jsonl  # 仅校准
```

依赖文件沿用 RP2 的 torch 2.6.0 约束。已工作的 CUDA 环境不要盲目替换；若安装后 CUDA 不可用，
先按服务器驱动选择兼容的 PyTorch wheel，再继续。脚本不下载模型，也不会把教师偷偷退回 CPU。
上面的专项测试包含纯合成 CPU 训练/ONNX/INT8 联调，不会加载 7B/BGE，亦不产生正式实验结果。

## 3. 先跑两题联调

```bash
bash scripts/run_rp3_experiments.sh teacher-smoke
```

只写 `.tmp/rp3_smoke/limit_2/`。若 BGE 索引缺失则建立；若已存在则只读加载，不覆盖。
每题要求新检索的 K≤3 ID 顺序与冻结 RP2 replay 一致；不同则立即停止。
不会把两题联调输出冻结成正式 40 题实验。

## 4. 首次完整核心流程

建议在 `tmux` 或其他持久终端中执行：

```bash
tmux new -s rp3
mkdir -p logs
bash scripts/run_rp3_experiments.sh all 2>&1 | tee logs/rp3_core_20260906.log
```

或按下表分阶段运行 `bash scripts/run_rp3_experiments.sh 阶段名`：

| 阶段 | 实际工作 | 主要产物 |
|---|---|---|
| teacher | 208 图索引/精确 K3 重放；完整实际候选打分轨迹；原 K3 两阶段核验；尾候选辅助支持标签；最终冻结 | `teacher_traces/strict208_base_top32/`、主 trace/memory bundle、teacher freeze |
| mp008 | 7B 从 MP008 原页面抽取逐字证据跨度绑定的校准候选；独立重放冻结核验策略 | MP008 原始响应、拒绝原因、独立开发 trace/memory |
| features | 训练和 MP008 分开导出确定性哈希特征 | `features/*_features.json` |
| train | 构建集 train 更新参数，组隔离 validation 早停；MP008 只登记哈希 | `lec_v1/bootstrap/` |
| route | 固定非路由模块，观察当前学生与冻结教师的差异，只训练 route head | `lec_v1/routed/route_rollouts.jsonl`、新 checkpoint |
| export | 导出 FP32 ONNX 和独立 MP008 代表性输入 | `lec_v1/onnx/` |
| quantize | 真正执行静态 INT8 QDQ，检查实际 INT8 权重及输出数值 | `controller.int8.onnx`、量化清单 |
| calibrate | 在量化后的 MP008 输出上联合选择 support/route 阈值 | `calibration_manifest.json` |
| evaluate | 冻结阈值后报告构建集 validation 的教师一致性和 ORT 耗时 | `lec_v1/evaluation/` |

上述路径省略前缀：实验为 `results/experiments/research_point_3/`，bundle 为
`data/kg/marine_pump/rp3/TeacherGraph_RP3_v1/`。

教师生成和 MP008 提取保留模型响应缓存，可重新执行同阶段续跑；缓存身份不匹配时拒绝复用。
训练、量化、校准输出不静默覆盖。需要重跑学生时使用新的 `RP3_RUN_DIR`，不要删除教师缓存：

```bash
export RP3_RUN_DIR=results/experiments/research_point_3/lec_repeat2
bash scripts/run_rp3_experiments.sh train
bash scripts/run_rp3_experiments.sh route
bash scripts/run_rp3_experiments.sh export
bash scripts/run_rp3_experiments.sh quantize
bash scripts/run_rp3_experiments.sh calibrate
bash scripts/run_rp3_experiments.sh evaluate
```

如果校准找不到满足默认“至少 5 个接受答案、教师集合不一致率≤0.1”的工作点，脚本停止，不生成可部署校准证书。
这不是软件报错就可以删除的限制：应检查样本覆盖、学生质量与校准集规模，记录失败。
该阈值只是预设经验工作点，不是工程安全保证，也没有有限样本统计风险保证。

## 5. 证据集合干预实验（独立增强组）

先完成正式 teacher 冻结，再执行：

```bash
python scripts/augment_rp3_interventions.py
python scripts/build_rp3_features.py \
  --traces data/kg/marine_pump/rp3/TeacherGraph_RP3_v1/traces/augmented_training \
  --memory data/kg/marine_pump/rp3/TeacherGraph_RP3_v1/evidence_memory/training \
  --output data/kg/marine_pump/rp3/TeacherGraph_RP3_v1/features/augmented_training_features.json
```

派生样本继承原始故障场景的 train/validation 分组。干预包括移除全部证据、逐条移除已选证据、
移除首条未选证据；重新执行原 RP2 来源约束选择和真实 7B 核验，不直接复制受影响的标签。
尾部未重新选入 K3 的支持标签仍为原查询—单证据辅助标签，这不等于整图重检索干预。

复制主训练配置到新文件，仅将 `trace_bundle_dir` 和 `feature_bundle_path` 指向上述增强产物；
用 `RP3_CONFIG=新配置 RP3_RUN_DIR=新目录` 执行 train/route/export 等阶段。
原 40 题冻结 bundle 和主图不变。派生数量不能当作新增独立故障案例数量。

## 6. 边缘工具调用

```bash
python scripts/run_rp3_tool.py \
  --memory data/kg/marine_pump/rp3/TeacherGraph_RP3_v1/evidence_memory/training \
  --traces data/kg/marine_pump/rp3/TeacherGraph_RP3_v1/traces/training \
  --export-dir results/experiments/research_point_3/lec_v1/onnx
```

标准输入每行一个 JSON 请求，字段以 `select_pump_evidence_tool_schema()` 为准。
故障 ID、诊断角色从冻结查询元数据中取实际值；不要凭空填写未知故障。
该命令不加载 LLM：执行哈希编码 → LEC → ID 证据恢复 → 确定性建议卡。
默认未连接教师服务，fallback 请求降为 abstain；它不会假装已经调用服务器 7B。
工具函数具备三动作协议，但自动调用远端教师的传输/服务层仍需部署时接入。

## 7. 不能提前宣布完成的实验

- `evaluate` 当前是参与过模型选择的构建集 validation 检查，不是独立泛化成绩。
- 正式外部评价 MP009–MP013、620/1326 层迁移、语义改写/干扰扩充、系统消融矩阵仍需另行执行与审核。
- 默认 route 拟合是固定学生输出对冻结教师结果的效用学习，不是多轮 DAgger，也不把教师一致性叫作诊断准确率。
- 默认成本 1/8/12/50 是申明的无量纲效用；实测时延、能耗和成本敏感性分析是后续实验。
- ONNX 计时仅统计 ORT 控制器；完整边缘实验还要计入编码、证据访问、渲染、LLM 壳、网络/回退。
- RTX 5880 上的实验不能替代 Jetson 等目标边缘硬件的实际内存、功耗、热稳态测量。
- MP008 自动抽取候选只通过跨度/模式检查，不是 RP1 新的证据合格记录，不进入主图或梯度数据。

静态 QDQ 与量化后精度回归的接口依据：[ONNX Runtime 量化文档](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html)。
