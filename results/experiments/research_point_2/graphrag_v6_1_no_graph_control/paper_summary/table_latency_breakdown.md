| Method | K | Stage | N | Mean ms | p50 ms | p95 ms |
|---|---|---|---|---|---|---|
| Full K3 | 3 | retrieval | 40 | 29.391 | 29.949 | 30.77 |
| Full K3 | 3 | prompt_build | 40 | 1.505 | 1.513 | 1.881 |
| Full K3 | 3 | stage1_verifier | 40 | 297.362 | 348.713 | 441.852 |
| Full K3 | 3 | stage2_review | 40 | 196.205 | 205.891 | 437.946 |
| Full K3 | 3 | render | 40 | 0.066 | 0.073 | 0.094 |
| Full K3 | 3 | input_preparation | 40 | 2.455 | 2.635 | 4.415 |
| Full K3 | 3 | model_inference | 40 | 504.086 | 551.082 | 867.424 |
| Full K3 | 3 | generation_pipeline | 40 | 513.178 | 555.426 | 873.414 |
| Full K3 | 3 | end_to_end | 40 | 544.397 | 585.559 | 903.128 |
| Full-NoGraph K3 | 3 | retrieval | 40 | 29.341 | 29.65 | 30.675 |
| Full-NoGraph K3 | 3 | prompt_build | 40 | 1.512 | 1.501 | 1.92 |
| Full-NoGraph K3 | 3 | stage1_verifier | 40 | 283.157 | 345.152 | 367.569 |
| Full-NoGraph K3 | 3 | stage2_review | 40 | 199.323 | 206.182 | 515.174 |
| Full-NoGraph K3 | 3 | render | 40 | 0.065 | 0.073 | 0.09 |
| Full-NoGraph K3 | 3 | input_preparation | 40 | 2.439 | 2.645 | 4.392 |
| Full-NoGraph K3 | 3 | model_inference | 40 | 492.043 | 556.7 | 869.912 |
| Full-NoGraph K3 | 3 | generation_pipeline | 40 | 496.384 | 560.946 | 877.512 |
| Full-NoGraph K3 | 3 | end_to_end | 40 | 530.228 | 593.535 | 907.756 |
