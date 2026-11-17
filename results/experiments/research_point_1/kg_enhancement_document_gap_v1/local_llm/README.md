# 可选本机AI源文分析工具

本次研究未启用、未调用外部LLM。主实验不导入本目录，也不需要任何API Key。

`run_optional.py`默认关闭，并硬性拒绝本次模型服务器主机`hengshan10`、SSH和作业环境。没有服务器调用的参数开关。仅检查路径不会加载网络客户端：

```bash
.venv/bin/python results/experiments/research_point_1/kg_enhancement_document_gap_v1/local_llm/run_optional.py --check-only
```

未来若确有必要，应把获得授权的少量结构化包复制到本机桌面环境，先取得具体数据/服务/模型的外传授权，再准备权限文件。不要把完整手册自动打包上传。即使不含源文，也不自动继承历史任务对其他页面的授权。

每行输入包须有`input_id`、`contains_source_text`及待核查内容。权限文件须明确`enabled:true`、`local_hostname`、`user_authorization_reference`、完整HTTPS `endpoint`、`model`、`api_key_env`、`allow_source_text_export`，并用`allowed_inputs`逐ID绑定规范JSON的SHA256。规范JSON使用`ensure_ascii=False, sort_keys=True, separators=(',', ':')`。权限文件禁止存储Key，Key只从指定环境变量读取。

只有同时传入`--enable-external-llm --confirm-local-machine --permission ... --packets ...`才可能执行。默认最多3次请求、失败重试1次，重试计入总请求上限；上限分别为20次和2次。输入ID、模型、提示词版本、输入哈希、输出/失败状态都保存，命中成功缓存不再发送。禁止HTTP重定向，错误日志不保存可能包含密钥的异常字符串。

所有返回只属于AI评价。当前支持不足的推断、待检查的范围和检索未命中均不可因此自动发布成正式知识。该工具没有图谱写入功能。
