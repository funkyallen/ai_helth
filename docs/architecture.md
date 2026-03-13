# 系统架构

项目采用 AIoT 微服务化思路，但为了比赛现场可控、易演示，当前仓库将核心能力先收拢为一个可运行的 FastAPI 主进程：

1. IoT 采集层：支持 BLE、MQTT、串口和 Mock 四种输入方式。
2. 解析层：`iot/parser.py` 根据 T10 手环双包规则完成 `0x1803 / 0x0318` 合并。
3. 实时层：采样进入内存流服务后，立即触发规则引擎和动态 Z-Score 检测。
4. 智能层：`ai/anomaly_detector.py` 保留 LSTM AutoEncoder 接口，可在本地或 GPU 环境进一步训练。
5. 应用层：FastAPI 提供 REST API、WebSocket、AI 助手接口。
6. 展示层：Vue 看板 + Flutter 移动端骨架。

比赛演示建议：

- 先开后端 Mock 模式，自动生成 10 台设备实时数据。
- 再打开前端大屏，展示趋势图、告警、AI 建议。
- 最后切换到移动端模拟子女端或社区端入口。
