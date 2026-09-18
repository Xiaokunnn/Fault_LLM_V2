# 联合门控审计

只读构建集；oracle替换只定位错误，不能作为可部署成绩。

| seed | split | rows | 无候选 | 有候选教师空集 | 全部已核验为负 | 数量超过支持数 |
|---|---|---:|---:|---:|---:|---:|
| 7042027 | train | 129 | 32 | 5 | 5 | 0 |
| 7042027 | validation | 36 | 8 | 4 | 4 | 0 |
| 7042028 | train | 129 | 32 | 5 | 5 | 0 |
| 7042028 | validation | 36 | 8 | 4 | 4 | 0 |
| 7042029 | train | 129 | 32 | 5 | 5 | 0 |
| 7042029 | validation | 36 | 8 | 4 | 4 | 0 |

| seed | 诊断替换 | 原始validation F1 | 完整validation教师空集误填 |
|---|---|---:|---:|
| 7042027 | unchanged | 0.4750 | 3/12 |
| 7042027 | oracle_assessed_support | 0.6208 | 0/12 |
| 7042027 | oracle_field | 0.4750 | 0/12 |
| 7042027 | oracle_cardinality | 0.4792 | 0/12 |
| 7042028 | unchanged | 0.3333 | 0/12 |
| 7042028 | oracle_assessed_support | 0.3750 | 0/12 |
| 7042028 | oracle_field | 0.3333 | 0/12 |
| 7042028 | oracle_cardinality | 0.3542 | 0/12 |
| 7042029 | unchanged | 0.2333 | 0/12 |
| 7042029 | oracle_assessed_support | 0.3583 | 0/12 |
| 7042029 | oracle_field | 0.2333 | 0/12 |
| 7042029 | oracle_cardinality | 0.3125 | 0/12 |
