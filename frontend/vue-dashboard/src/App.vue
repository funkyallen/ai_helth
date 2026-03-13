<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import AlarmPanel from "./components/AlarmPanel.vue";
import AssistantPanel from "./components/AssistantPanel.vue";
import DeviceGrid from "./components/DeviceGrid.vue";
import TrendChart from "./components/TrendChart.vue";
import { api, type AlarmRecord, type DeviceRecord, type HealthSample } from "./api/client";

const devices = ref<DeviceRecord[]>([]);
const latest = ref<Record<string, HealthSample>>({});
const trend = ref<HealthSample[]>([]);
const alarms = ref<AlarmRecord[]>([]);
const selectedMac = ref("");

let healthSocket: WebSocket | null = null;
let alarmSocket: WebSocket | null = null;

const heroStats = computed(() => {
  const samples = Object.values(latest.value);
  if (!samples.length) {
    return { online: 0, alerts: alarms.value.length, avgScore: 0, sosCount: 0 };
  }
  const avgScore = Math.round(
    samples.reduce((sum, sample) => sum + (sample.health_score ?? 80), 0) / samples.length,
  );
  const sosCount = samples.filter((sample) => sample.sos_flag).length;
  return {
    online: samples.length,
    alerts: alarms.value.length,
    avgScore,
    sosCount,
  };
});

async function loadDashboard() {
  devices.value = await api.listDevices();
  if (!selectedMac.value && devices.value.length) {
    selectedMac.value = devices.value[0].mac_address;
  }
  await Promise.all([refreshRealtime(), refreshAlarms(), refreshTrend()]);
  connectSockets();
}

async function refreshRealtime() {
  const snapshots = await Promise.all(devices.value.map((device) => api.getRealtime(device.mac_address).catch(() => null)));
  latest.value = Object.fromEntries(
    snapshots.filter(Boolean).map((sample) => [sample!.device_mac, sample!]),
  );
}

async function refreshTrend() {
  if (!selectedMac.value) return;
  trend.value = await api.getTrend(selectedMac.value).catch(() => []);
}

async function refreshAlarms() {
  alarms.value = await api.listAlarms().catch(() => []);
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
        trend.value = [...trend.value.slice(-119), sample];
      }
    };
  }
  alarmSocket = api.alarmSocket();
  alarmSocket.onmessage = (event) => {
    const alarm = JSON.parse(event.data) as AlarmRecord;
    alarms.value = [alarm, ...alarms.value].slice(0, 20);
  };
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

onMounted(() => {
  void loadDashboard();
});

onUnmounted(() => {
  healthSocket?.close();
  alarmSocket?.close();
});
</script>

<template>
  <main class="shell">
    <section class="hero-card">
      <div>
        <p class="eyebrow">AIoT Smart Care Command Deck</p>
        <h1>智慧康养实时监测中枢</h1>
        <p class="hero-copy">
          面向比赛演示的全链路看板，覆盖设备在线、生命体征、SOS 告警与 AI 风险分析。
        </p>
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
          <span>SOS 设备</span>
          <strong>{{ heroStats.sosCount }}</strong>
        </article>
      </div>
    </section>

    <section class="dashboard-grid">
      <DeviceGrid
        :devices="devices"
        :latest="latest"
        :selected-mac="selectedMac"
        @select="handleSelect"
      />
      <AlarmPanel :alarms="alarms" @ack="handleAlarmAck" />
      <TrendChart :samples="trend" :device-mac="selectedMac" />
      <AssistantPanel :device-mac="selectedMac" />
    </section>
  </main>
</template>
