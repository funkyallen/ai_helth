# AIoT 智慧康养健康监测系统

基于比赛规程、T10 手环协议和 `ai_health_iot_full_prompt.md` 生成的全栈演示项目，覆盖后端 API、IoT 解析、异常检测、AI 助手、Vue 大屏和 Flutter 移动端骨架。

## 项目结构

- `backend/`: FastAPI 主程序、REST API、WebSocket 和核心服务
- `iot/`: T10 双包解析器、BLE/MQTT/串口接入适配器
- `ai/`: 实时异常检测、智能评分、模拟数据生成器
- `agent/`: 本地/云端 LLM 统一调用与轻量 RAG
- `frontend/vue-dashboard/`: Vue3 + ECharts 大屏
- `mobile/flutter_app/`: Flutter 移动端骨架
- `mobile/android-snippets/`: Kotlin 关键页面示例
- `database/schema.sql`: PostgreSQL / TimescaleDB 建表脚本
- `docker/docker-compose.yml`: 比赛演示部署编排
- `environment/conda-environment.yml`: 参考赛项规程整理的 conda 环境
- `scripts/setup_env.ps1`: Windows 下一键安装 conda 环境脚本
- `docs/`: 架构说明、环境对照、比赛演示脚本

## 赛项环境对齐

依据规程提取的关键基线：

- `Anaconda 22.9.0`
- `Python 3.9+`
- `Docker 28.5.1`
- `Ollama 0.12.9`
- `Qwen3:1.7B`
- `PostgreSQL 15`
- `CUDA 12.6`
- `cuDNN 8.9.7`
- `torch 2.0.1 + cu117`

当前环境文件已尽量向规程靠齐，尤其是：

- `python=3.9`
- `numpy=1.24.4`
- `pandas=2.0.3`
- `scipy=1.10.1`
- `scikit-learn=1.0.2`
- `pytorch=2.0.1`
- `torchvision=0.15.2`
- `torchaudio=2.0.2`
- `pytorch-cuda=11.7`

如果某些旧版本在你的机器上装不上，再小范围升级，不建议一开始就全部升到最新。

## 环境配置流程

这部分是推荐流程，适合你当前这种“Windows + conda + 梯子/代理”的安装环境。

### 1. 准备工作

建议先确认三件事：

- 梯子已开启，并尽量使用 `TUN 模式` 或 `全局模式`
- `conda` 可以在 PowerShell 里直接调用
- 不要把 conda 环境装在当前项目目录里，因为当前路径有空格，容易导致部分包报错

推荐环境安装路径：

```powershell
D:\conda-envs\ai-health-iot
```

### 2. 推荐方式：使用一键脚本安装

项目已经提供了环境安装脚本 [scripts/setup_env.ps1](D:/OneDrive/文档/1-课程资料/4- 人工智能+/2026/演示项目/scripts/setup_env.ps1)。

它会自动做这些事情：

- 强制 `conda` 使用 `classic solver`
- 临时关闭 `conda` 插件，绕开常见的权限和缓存问题
- 默认把环境装到无空格路径 `D:\conda-envs\ai-health-iot`
- 优先单独安装 `torch 2.0.1 + pytorch-cuda 11.7`
- 再安装其余业务依赖
- 最后自动验证 `torch.cuda.is_available()`

直接运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_env.ps1
```

如果你的梯子提供本地 HTTP 代理，例如 `127.0.0.1:7890`，推荐这样运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_env.ps1 -ProxyUrl http://127.0.0.1:7890
```

如果你已经确认代理是全局生效的，可以不传 `-ProxyUrl`。

### 3. 脚本可选参数

- `-EnvPath`: 指定新的环境目录
- `-ProxyUrl`: 设置终端代理
- `-SkipConnectivityCheck`: 跳过联网测试
- `-UseYamlInstall`: 直接按 `environment/conda-environment.yml` 一次性创建环境

例如：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_env.ps1 -EnvPath D:\envs\ai-health-iot -ProxyUrl http://127.0.0.1:7890
```

### 4. 如果你不想用脚本，手动安装流程如下

先修正 conda 自身配置：

```powershell
conda config --set solver classic
conda config --set report_errors false
$env:CONDA_NO_PLUGINS = "true"
```

如果代理软件提供本地端口，手动给终端设置代理：

```powershell
$env:HTTP_PROXY = "http://127.0.0.1:7890"
$env:HTTPS_PROXY = "http://127.0.0.1:7890"
```

先测试 conda 源是否能访问：

```powershell
curl https://repo.anaconda.com/pkgs/main/win-64/repodata.json -I
```

创建基础环境：

```powershell
conda create --solver classic -p D:\conda-envs\ai-health-iot python=3.9 pip nodejs=20 -y
conda activate D:\conda-envs\ai-health-iot
```

优先安装 CUDA 版 torch：

```powershell
conda install --solver classic -p D:\conda-envs\ai-health-iot pytorch=2.0.1 torchvision=0.15.2 torchaudio=2.0.2 pytorch-cuda=11.7 -c pytorch -c nvidia -y
```

再安装其余主要依赖：

```powershell
conda install --solver classic -p D:\conda-envs\ai-health-iot numpy=1.24.4 pandas=2.0.3 scipy=1.10.1 scikit-learn=1.0.2 matplotlib=3.7.5 seaborn=0.13.2 pyyaml=6.0.2 lxml=4.9.3 pillow=10.4.0 requests=2.32.3 beautifulsoup4=4.12.3 pyparsing=3.1.4 certifi=2025.1.31 charset-normalizer=3.4.1 jinja2=3.1.6 psutil=7 tqdm=4.67.1 fastapi=0.115.8 uvicorn=0.34.0 sqlalchemy=2.0.37 aiosqlite=0.21 pydantic=2.11.3 pytest=8.3.4 pytest-asyncio=0.25.2 -c conda-forge -y
```

最后补 pip 包：

```powershell
conda run -p D:\conda-envs\ai-health-iot python -m pip install --upgrade pip
conda run -p D:\conda-envs\ai-health-iot python -m pip install chromadb==0.5.23 pydantic-settings==2.8.1 "bleak>=0.22,<0.24" "paho-mqtt>=2.1,<3" "pyserial>=3.5,<4" "ollama>=0.4.5,<1" "langchain>=0.3.14,<0.4" "langgraph>=0.2.61,<0.3"
```

### 5. 验证 CUDA 版 torch 是否安装成功

安装完成后，执行：

```powershell
conda run -p D:\conda-envs\ai-health-iot python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.version.cuda)"
```

理想输出应接近：

```text
2.0.1
True
11.7
```

如果 `torch.cuda.is_available()` 是 `False`，优先检查：

- NVIDIA 驱动是否正确安装
- 当前机器是否真的有可用 NVIDIA GPU
- `nvidia-smi` 是否能正常输出

### 6. 激活环境

```powershell
conda activate D:\conda-envs\ai-health-iot
```

## 项目启动流程

### 1. 启动后端

```powershell
conda activate D:\conda-envs\ai-health-iot
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

默认开启 `USE_MOCK_DATA=true`，后端会持续生成 10 台 T10 设备的模拟数据，方便现场直接演示。

### 2. 启动前端

```powershell
cd frontend\vue-dashboard
npm install
npm run dev
```

如果 PowerShell 报 `npm.ps1` 执行策略错误，可改用：

```powershell
npm.cmd install
npm.cmd run dev
```

### 3. 启动 Docker 依赖

```powershell
cd docker
docker compose up -d
```

### 4. 启动 Flutter 客户端

```powershell
cd mobile\flutter_app
flutter pub get
flutter run
```

## API 亮点

- `POST /api/v1/health/ingest`: 注入实时生命体征
- `GET /api/v1/health/realtime/{device_mac}`: 最新样本
- `GET /api/v1/health/trend/{device_mac}`: 趋势数据
- `GET /api/v1/health/community/overview`: 社区聚类态势
- `POST /api/v1/chat/analyze`: AI 健康建议
- `WS /ws/health/{device_mac}`: 实时指标流
- `WS /ws/alarms`: 告警流

## T10 解析说明

已按手册保留以下硬约束：

- 设备名前缀：`T10-WATCH`
- MAC 前缀：`53:57:08`
- 默认 UUID：`52616469-6F6C-616E-642D-541000000000`
- 服务 UUID：`00001803-494c-4f47-4943-544543480000`
- 双包区分：第 13-14 字节 `0x1803 / 0x0318`
- SOS 特征：长按 5 秒触发，持续广播约 15 秒

当前 `iot/parser.py` 做了可配置布局封装：合并规则严格对齐说明书，字段偏移支持按现场固件再微调。

## 测试

```powershell
pytest
```

当前内置测试覆盖：

- 双包解析
- 实时告警触发
- FastAPI 健康检查

## 常见问题

### 1. conda 安装时报插件或缓存权限错误

先执行：

```powershell
conda config --set solver classic
$env:CONDA_NO_PLUGINS = "true"
```

### 2. conda 连不上外网源

优先切换梯子到 `TUN` 或 `全局模式`，或者给终端显式设置：

```powershell
$env:HTTP_PROXY = "http://127.0.0.1:7890"
$env:HTTPS_PROXY = "http://127.0.0.1:7890"
```

### 3. torch 装好了但 CUDA 不可用

检查：

```powershell
nvidia-smi
```

如果这里都不通，说明不是 Python 依赖问题，而是显卡驱动或 CUDA 运行环境没有准备好。

## 后续建议

- 若现场允许 GPU，继续训练 `ai/anomaly_detector.py` 中的时间序列自编码器。
- 若需要答辩加分，可把 `community/overview` 扩成社区热力图和风险地图。
- 若接入真实网关，优先启用 `iot/mqtt_listener.py` 或 `iot/serial_reader.py`。
