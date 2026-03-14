<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import AlarmPanel from "./components/AlarmPanel.vue";
import ArchitecturePanel from "./components/ArchitecturePanel.vue";
import AssistantPanel from "./components/AssistantPanel.vue";
import CommunityAssistantPanel from "./components/CommunityAssistantPanel.vue";
import CommunityOverviewPanel from "./components/CommunityOverviewPanel.vue";
import DeviceFocusPanel from "./components/DeviceFocusPanel.vue";
import DeviceGrid from "./components/DeviceGrid.vue";
import DispatchBoard from "./components/DispatchBoard.vue";
import PriorityBoard from "./components/PriorityBoard.vue";
import TrendChart from "./components/TrendChart.vue";
import {
  api,
  type AlarmRecord,
  type CommunityOverview,
  type DeviceRecord,
  type HealthSample,
} from "./api/client";

const devices = ref<DeviceRecord[]>([]);
const latest = ref<Record<string, HealthSample>>({});
const trend = ref<HealthSample[]>([]);
const alarms = ref<AlarmRecord[]>([]);
const communityOverview = ref<CommunityOverview | null>(null);
const selectedMac = ref("");
const lastSyncAt = ref<Date | null>(null);
const trendWindowMinutes = ref(180);

let healthSocket: WebSocket | null = null;
let alarmSocket: WebSocket | null = null;
let refreshTimer: number | null = null;

const operationSteps = [
  { label: "IoT 接入", description: "手环采集与边缘网关稳定接入" },
  { label: "异常识别", description: "实时规则、评分与 SOS 联动" },
  { label: "社区调度", description: "多设备筛查与重点对象优先级排序" },
  { label: "AI 分析", description: "Qwen / Ollama 双路由解读与建议输出" },
];

const selectedDevice = computed(
  () => devices.value.find((device) => device.mac_address === selectedMac.value) ?? null,
);
const selectedSample = computed(() => latest.value[selectedMac.value] ?? null);

function riskTone(sample?: HealthSample | null) {
  if (!sample) return "idle";
  if (sample.sos_flag || sample.blood_oxygen < 90 || sample.heart_rate > 180 || sample.heart_rate < 40) {
    return "high";
  }
  if (sample.temperature > 38 || sample.heart_rate > 110 || sample.blood_oxygen < 93) {
    return "medium";
  }
  return "low";
}

function localizedRiskLabel(tone: string) {
  return {
    idle: "待同步",
    low: "低风险",
    medium: "中风险",
    high: "高风险",
  }[tone] ?? "待同步";
}

function deviceStatusLabel(status: string) {
  if (status === "warning") return "告警";
  if (status === "offline") return "离线";
  return "在线";
}

function trendLimit(minutes: number) {
  if (minutes <= 60) return 90;
  if (minutes <= 180) return 150;
  return 240;
}

const selectedRiskLabel = computed(() => localizedRiskLabel(riskTone(selectedSample.value)));

const heroStats = computed(() => {
  const samples = Object.values(latest.value);
  if (!samples.length) {
    return {
      online: devices.value.filter((device) => device.status !== "offline").length,
      alerts: alarms.value.length,
      avgScore: 0,
      avgSpo2: 0,
      sosCount: 0,
      anomalyScore: 0,
    };
  }
  const avgScore = Math.round(
    samples.reduce((sum, sample) => sum + (sample.health_score ?? 80), 0) / samples.length,
  );
  const avgSpo2 = Math.round(
    samples.reduce((sum, sample) => sum + sample.blood_oxygen, 0) / samples.length,
  );
  return {
    online: devices.value.filter((device) => device.status !== "offline").length,
    alerts: alarms.value.length,
    avgScore,
    avgSpo2,
    sosCount: samples.filter((sample) => sample.sos_flag).length,
    anomalyScore: Number((communityOverview.value?.intelligent_anomaly_score ?? 0).toFixed(2)),
  };
});

const riskSummary = computed(() => {
  const counters = { high: 0, medium: 0, low: 0, idle: 0 };
  devices.value.forEach((device) => {
    counters[riskTone(latest.value[device.mac_address]) as keyof typeof counters] += 1;
  });
  return counters;
});

const priorityBoardItems = computed(() =>
  devices.value
    .map((device) => {
      const sample = latest.value[device.mac_address] ?? null;
      const tone = riskTone(sample);
      let score = 0;

      if (sample) {
        score += Math.max(0, 100 - Math.round(sample.health_score ?? 82));
        if (sample.sos_flag) score += 42;
        if (sample.blood_oxygen < 90) score += 24;
        else if (sample.blood_oxygen < 93) score += 12;
        if (sample.temperature > 38) score += 14;
        else if (sample.temperature > 37.3) score += 6;
        if (sample.heart_rate > 120 || sample.heart_rate < 45) score += 16;
        else if (sample.heart_rate > 110) score += 8;
      } else {
        score += 12;
      }

      if (device.status === "warning") score += 10;
      if (device.status === "offline") score += 14;

      const action =
        device.status === "offline"
          ? "优先检查设备连接状态并补拉最新数据。"
          : tone === "high"
            ? "建议 10 分钟内电话确认，并准备上门复测或联动物业。"
            : tone === "medium"
              ? "建议 30 分钟内完成回访，提升今晚监测频次。"
              : tone === "low"
                ? "保持常规巡检节奏，继续观察夜间趋势。"
                : "先完成设备状态确认，再进入分析。";

      const summary = sample
        ? `HR ${sample.heart_rate} bpm / T ${sample.temperature.toFixed(1)}℃ / SpO2 ${sample.blood_oxygen}%`
        : "暂无实时样本，当前仅依据设备状态进行排序。";

      return {
        deviceMac: device.mac_address,
        deviceName: device.device_name,
        status: deviceStatusLabel(device.status),
        riskLabel: tone,
        score: Math.min(score, 99),
        action,
        summary,
        sample,
      };
    })
    .sort((left, right) => right.score - left.score)
    .slice(0, 5),
);

const dispatchTasks = computed(() => {
  const tasks: Array<{
    stage: string;
    title: string;
    summary: string;
    owner: string;
    eta: string;
    tone: "critical" | "warning" | "stable";
  }> = [];

  const highestAlarm = [...alarms.value].sort((left, right) => right.alarm_level - left.alarm_level)[0];
  const topPriority = priorityBoardItems.value[0];
  const secondPriority = priorityBoardItems.value[1];
  const attentionCount = communityOverview.value?.clusters.attention?.length ?? 0;
  const dangerCount = communityOverview.value?.clusters.danger?.length ?? 0;

  if (highestAlarm) {
    tasks.push({
      stage: "立即处置",
      title: `核查告警 ${highestAlarm.device_mac}`,
      summary: `${highestAlarm.message}，建议先电话联系，再决定是否安排到户核验。`,
      owner: "社区值守 + 家属",
      eta: "10 分钟内",
      tone: highestAlarm.alarm_level >= 4 ? "critical" : "warning",
    });
  } else if (topPriority) {
    tasks.push({
      stage: "立即处置",
      title: `关注重点设备 ${topPriority.deviceName}`,
      summary: `${topPriority.summary}。${topPriority.action}`,
      owner: "社区值守",
      eta: "10 分钟内",
      tone: topPriority.riskLabel === "high" ? "critical" : "warning",
    });
  }

  if (topPriority) {
    tasks.push({
      stage: "快速回访",
      title: `复核 ${topPriority.deviceName} 的近时段波动`,
      summary: "结合趋势图和 AI 单设备分析，确认是否需要上门测量或补测血氧。",
      owner: "护理员",
      eta: "30 分钟内",
      tone: topPriority.riskLabel === "high" ? "warning" : "stable",
    });
  }

  if (attentionCount || secondPriority) {
    tasks.push({
      stage: "分级随访",
      title: "安排关注群回访与夜间复测",
      summary: `当前关注群 ${attentionCount} 台，建议优先覆盖排名前二设备，并提高今晚随访频次。`,
      owner: "社区健康专员",
      eta: "2 小时内",
      tone: attentionCount > 2 ? "warning" : "stable",
    });
  }

  tasks.push({
    stage: "今日闭环",
    title: "输出社区健康总结",
    summary: `危险群 ${dangerCount} 台，建议将 AI 社区分析结果同步给值守人员和答辩展示页面。`,
    owner: "运营负责人",
    eta: "今日内",
    tone: dangerCount ? "warning" : "stable",
  });

  return tasks.slice(0, 4);
});

const syncLabel = computed(() => {
  if (!lastSyncAt.value) return "等待首轮同步";
  return lastSyncAt.value.toLocaleTimeString("zh-CN", { hour12: false });
});

async function refreshRealtime() {
  const snapshots = await Promise.all(
    devices.value.map((device) => api.getRealtime(device.mac_address).catch(() => null)),
  );
  latest.value = Object.fromEntries(
    snapshots.filter(Boolean).map((sample) => [sample!.device_mac, sample!]),
  );
}

async function refreshTrend() {
  if (!selectedMac.value) {
    trend.value = [];
    return;
  }
  trend.value = await api
    .getTrend(selectedMac.value, trendWindowMinutes.value, trendLimit(trendWindowMinutes.value))
    .catch(() => []);
}

async function refreshAlarms() {
  alarms.value = await api.listAlarms().catch(() => []);
}

async function refreshCommunity() {
  communityOverview.value = await api.getCommunityOverview().catch(() => communityOverview.value);
}

async function refreshAll() {
  await Promise.all([refreshRealtime(), refreshAlarms(), refreshCommunity(), refreshTrend()]);
  lastSyncAt.value = new Date();
}

function connectSockets() {
  healthSocket?.close();
  alarmSocket?.close();

  if (selectedMac.value) {
    healthSocket = api.healthSocket(selectedMac.value);
    healthSocket.onmessage = (event) => {
      const sample = JSON.parse(event.data) as HealthSample;
      latest.value = { ...latest.value, [sample.device_mac]: sample };
      if (sample.device_mac === selectedMac.value) {
        trend.value = [...trend.value.slice(-(trendLimit(trendWindowMinutes.value) - 1)), sample];
      }
      lastSyncAt.value = new Date();
    };
  }

  alarmSocket = api.alarmSocket();
  alarmSocket.onmessage = (event) => {
    const alarm = JSON.parse(event.data) as AlarmRecord;
    alarms.value = [alarm, ...alarms.value].slice(0, 20);
    lastSyncAt.value = new Date();
  };
}

function startPolling() {
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer);
  }
  refreshTimer = window.setInterval(() => {
    void refreshAll();
  }, 15000);
}

async function loadDashboard() {
  devices.value = await api.listDevices();
  if (!selectedMac.value && devices.value.length) {
    selectedMac.value = devices.value[0].mac_address;
  }
  await refreshAll();
  connectSockets();
  startPolling();
}

async function handleAlarmAck(alarmId: string) {
  await api.ackAlarm(alarmId);
  await refreshAlarms();
}

async function handleSelect(mac: string) {
  selectedMac.value = mac;
  await refreshTrend();
  connectSockets();
}

async function handleTrendWindowChange(minutes: number) {
  trendWindowMinutes.value = minutes;
  await refreshTrend();
}

onMounted(() => {
  void loadDashboard();
});

onUnmounted(() => {
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer);
  }
  healthSocket?.close();
  alarmSocket?.close();
});
</script>

<template>
  <main class="shell">
    <section class="hero-card">
      <div class="hero-grid">
        <div class="hero-copy-wrap">
          <p class="eyebrow">AIoT Health Command Deck</p>
          <h1>社区康养智能体指挥中枢</h1>
          <p class="hero-copy">
            面向社区养老和居家健康场景，将 IoT 实时采集、异常识别、群体分层、趋势分析与 Qwen / Ollama
            双路由智能体整合为一套可展示、可答辩、可持续扩展的网页中枢。
          </p>
          <div class="hero-badge-list">
            <span class="hero-badge">多设备实时总览</span>
            <span class="hero-badge">重点对象优先级排序</span>
            <span class="hero-badge">Chroma RAG</span>
            <span class="hero-badge">云端 / 离线双路由</span>
          </div>
        </div>
        <div class="hero-status-card">
          <span class="status-kicker">系统心跳</span>
          <strong>{{ syncLabel }}</strong>
          <p>
            页面每 15 秒同步一次社区快照，并对当前主设备保持 WebSocket 实时订阅，方便现场连续演示趋势变化与告警联动。
          </p>
          <div class="hero-status-grid">
            <article>
              <span>当前主设备</span>
              <strong>{{ selectedDevice?.device_name ?? "未选择" }}</strong>
            </article>
            <article>
              <span>风险等级</span>
              <strong>{{ selectedRiskLabel }}</strong>
            </article>
          </div>
          <div class="hero-badge-list">
            <span class="hero-badge">高风险 {{ riskSummary.high }}</span>
            <span class="hero-badge">需关注 {{ riskSummary.medium }}</span>
            <span class="hero-badge">稳定 {{ riskSummary.low }}</span>
          </div>
        </div>
      </div>

      <div class="stat-strip">
        <article>
          <span>在线设备</span>
          <strong>{{ heroStats.online }}</strong>
        </article>
        <article>
          <span>活动告警</span>
          <strong>{{ heroStats.alerts }}</strong>
        </article>
        <article>
          <span>平均健康分</span>
          <strong>{{ heroStats.avgScore }}</strong>
        </article>
        <article>
          <span>平均血氧</span>
          <strong>{{ heroStats.avgSpo2 }}%</strong>
        </article>
        <article>
          <span>社区异常评分</span>
          <strong>{{ heroStats.anomalyScore }}</strong>
        </article>
      </div>
    </section>

    <section class="command-rail">
      <article v-for="item in operationSteps" :key="item.label" class="rail-item">
        <span>{{ item.label }}</span>
        <strong>{{ item.description }}</strong>
      </article>
    </section>

    <section class="dashboard-grid">
      <ArchitecturePanel
        :device-count="devices.length"
        :anomaly-score="heroStats.anomalyScore"
        :selected-mac="selectedMac"
      />
      <DispatchBoard :tasks="dispatchTasks" />
      <DeviceGrid
        :devices="devices"
        :latest="latest"
        :selected-mac="selectedMac"
        @select="handleSelect"
      />
      <DeviceFocusPanel
        :device="selectedDevice"
        :sample="selectedSample"
        :trend="trend"
        :risk-label="selectedRiskLabel"
      />
      <PriorityBoard :items="priorityBoardItems" />
      <TrendChart
        :samples="trend"
        :device-mac="selectedMac"
        :window-minutes="trendWindowMinutes"
        @change-window="handleTrendWindowChange"
      />
      <CommunityOverviewPanel
        :overview="communityOverview"
        :avg-score="heroStats.avgScore"
        :avg-spo2="heroStats.avgSpo2"
        :sos-count="heroStats.sosCount"
      />
      <AlarmPanel :alarms="alarms" @ack="handleAlarmAck" />
      <AssistantPanel
        :device-mac="selectedMac"
        :sample="selectedSample"
        :risk-label="selectedRiskLabel"
      />
      <CommunityAssistantPanel :overview="communityOverview" />
    </section>
  </main>
</template>
