# 请求字段归一化：三种子配对构建集结果

预声明判断：`improvement_not_established_under_prespecified_rule`。仅内部诊断，不可部署。

## 原始validation（每种子8条、2个场景）

| 臂 | 种子 | 最佳epoch | 非空目标raw零预测 | 请求基数准确率 | Pointer F1 | 教师空集误填 | 零可用证据误填 |
|---|---:|---:|---:|---:|---:|---:|---:|
| all_fields | 7042027 | 1 | 7/7 | 0.1250 | 0.0000 | 0/1 | 0/0 |
| requested_balanced | 7042027 | 2 | 1/7 | 0.5000 | 0.4750 | 1/1 | 0/0 |
| all_fields | 7042028 | 1 | 6/7 | 0.1250 | 0.0833 | 0/1 | 0/0 |
| requested_balanced | 7042028 | 1 | 4/7 | 0.3750 | 0.3333 | 0/1 | 0/0 |
| all_fields | 7042029 | 1 | 6/7 | 0.2500 | 0.0833 | 0/1 | 0/0 |
| requested_balanced | 7042029 | 1 | 3/7 | 0.2500 | 0.2333 | 0/1 | 0/0 |

## 预声明判断条件

- pointer_f1_increased: True
- nonempty_raw_zero_decreased: True
- requested_cardinality_not_lower: True
- all_seed_false_fill_safeguards: False

全字段控制复用既有A3，无重训；新臂只改请求/非请求两组的CE归一化（各0.5），审计开关不参与更新或早停。
0/0为无样本，不等于零风险。完整original/derived/all、train/validation、逐场景、三种子均值/SD/描述性区间见JSON/CSV。
既有控制只保存epoch1最佳模型，不能据新臂逐epoch日志反推控制后续epoch的任务表现；新臂仍仅按预声明总validation loss选checkpoint。
