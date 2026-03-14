<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import {
  api,
  type AlarmRecord,
  type AuthAccountPreview,
  type CareDirectory,
  type DeviceRecord,
  type HealthSample,
  type SessionUser,
} from "./api/client";
import { evaluateRisk, riskLabel, riskWeight, type RiskLevel } from "./domain/careModel";

type PageKey = "community" | "family" | "relation";

interface ElderRow {
  id: string;
  name: string;
  apartment: string;
  deviceMac: string;
  familyNames: string;
  risk: RiskLevel;
  sample: HealthSample | null;
  alarmCount: number;
  score: number;
}

const SESSION_KEY = "ai_health_demo_session_token";

const pageHash: Record<PageKey, string> = {
  community: "#/community",
  family: "#/family",
  relation: "#/relation",
};

const sessionUser = ref<SessionUser | null>(null);
const sessionToken = ref("");
const authAccounts = ref<AuthAccountPreview[]>([]);
const loginUsername = ref("");
const loginPassword = ref("123456");
const authLoading = ref(false);
const authError = ref("");

const directory = ref<CareDirectory | null>(null);
const devices = ref<DeviceRecord[]>([]);
const latest = ref<Record<string, HealthSample>>({});
const alarms = ref<AlarmRecord[]>([]);
const trendStore = ref<Record<string, HealthSample[]>>({});
const activePage = ref<PageKey>("community");
const selectedFamilyId = ref("");
const selectedDeviceMac = ref("");
const lastSyncAt = ref<Date | null>(null);
const familyAdvice = ref("点击“生成建议”可获得面向家属的今日照护建议。");
const communityAdvice = ref("点击“生成建议”可获得面向社区值守的处置建议。");
const familyAdviceLoading = ref(false);
const communityAdviceLoading = ref(false);

let refreshTimer: number | null = null;
let hashListener: (() => void) | null = null;
let healthSocket: WebSocket | null = null;

const isLoggedIn = computed(() => Boolean(sessionUser.value));
const community = computed(() => directory.value?.community ?? null);
const elders = computed(() => directory.value?.elders ?? []);
const families = computed(() => directory.value?.families ?? []);
const deviceByMac = computed(() =>
  Object.fromEntries(devices.value.map((device) => [device.mac_address, device])) as Record<string, DeviceRecord>,
);

const allowedPages = computed<PageKey[]>(() => {
  if (!sessionUser.value) return [];
  if (sessionUser.value.role === "family") return ["family", "relation"];
  return ["community", "relation"];
});

const visibleFamilies = computed(() => {
  if (sessionUser.value?.role === "family") {
    return families.value.filter((family) => family.id === sessionUser.value?.family_id);
  }
  return families.value;
});

const selectedFamily = computed(() => {
  if (!visibleFamilies.value.length) return null;
  return visibleFamilies.value.find((family) => family.id === selectedFamilyId.value) ?? visibleFamilies.value[0];
});

const elderRows = computed<ElderRow[]>(() => {
  return elders.value
    .map((elder) => {
      const sample = latest.value[elder.device_mac] ?? null;
      const status = deviceByMac.value[elder.device_mac]?.status ?? "unknown";
      const risk = evaluateRisk(sample, status);
      const alarmCount = alarms.value.filter((alarm) => !alarm.acknowledged && alarm.device_mac === elder.device_mac).length;
      const familyNames = elder.family_ids
        .map((familyId) => families.value.find((family) => family.id === familyId)?.name)
        .filter((name): name is string => Boolean(name))
        .join(" / ");
      const score =
        riskWeight(risk) * 100 +
        alarmCount * 18 +
        (sample?.sos_flag ? 36 : 0) +
        (sample ? Math.max(0, 100 - Math.round(sample.health_score ?? 80)) : 12);
      return {
        id: elder.id,
        name: elder.name,
        apartment: elder.apartment,
        deviceMac: elder.device_mac,
        familyNames,
        risk,
        sample,
        alarmCount,
        score,
      };
    })
    .sort((left, right) => right.score - left.score);
});

const visibleRows = computed(() => {
  if (sessionUser.value?.role === "family" && selectedFamily.value) {
    const own = new Set(selectedFamily.value.elder_ids);
    return elderRows.value.filter((row) => own.has(row.id));
  }
  return elderRows.value;
});

const focusRow = computed(() => visibleRows.value.find((row) => row.deviceMac === selectedDeviceMac.value) ?? null);
const focusTrend = computed(() => trendStore.value[selectedDeviceMac.value] ?? []);
const syncLabel = computed(() => (lastSyncAt.value ? lastSyncAt.value.toLocaleTimeString("zh-CN", { hour12: false }) : "等待同步"));

watch(allowedPages, (pages) => {
  if (!pages.length) return;
  if (!pages.includes(activePage.value)) activePage.value = pages[0];
});

watch(visibleFamilies, (list) => {
  if (!list.length) return;
  if (!list.some((family) => family.id === selectedFamilyId.value)) {
    selectedFamilyId.value = list[0].id;
  }
});

watch(visibleRows, (rows) => {
  if (!rows.length) return;
  if (!rows.some((row) => row.deviceMac === selectedDeviceMac.value)) {
    selectedDeviceMac.value = rows[0].deviceMac;
  }
});

watch(selectedDeviceMac, (mac) => {
  connectHealthSocket(mac);
  if (mac) void refreshTrend(mac);
});

function routeTo(page: PageKey) {
  if (!allowedPages.value.includes(page)) return;
  activePage.value = page;
  window.location.hash = pageHash[page];
}

function relationFamiliesText(familyIds: string[]) {
  return familyIds
    .map((familyId) => families.value.find((family) => family.id === familyId)?.name)
    .filter((name): name is string => Boolean(name))
    .join(" / ");
}

function riskClass(level: RiskLevel) {
  return `risk-${level}`;
}

async function refreshTrend(mac: string) {
  const trend = await api.getTrend(mac, 180, 120).catch(() => []);
  trendStore.value = { ...trendStore.value, [mac]: trend };
}

async function refreshDashboardData() {
  const snapshots = await Promise.all(
    devices.value.map((device) => api.getRealtime(device.mac_address).catch(() => null)),
  );
  const next = { ...latest.value };
  snapshots.forEach((sample) => {
    if (sample) next[sample.device_mac] = sample;
  });
  latest.value = next;
  const allAlarms = await api.listAlarms().catch(() => [] as AlarmRecord[]);
  const allowedMacs = new Set(elders.value.map((elder) => elder.device_mac));
  alarms.value = allAlarms.filter((alarm) => allowedMacs.has(alarm.device_mac));
  lastSyncAt.value = new Date();
}

function connectHealthSocket(mac: string) {
  healthSocket?.close();
  healthSocket = null;
  if (!mac) return;
  healthSocket = api.healthSocket(mac);
  healthSocket.onmessage = (event) => {
    try {
      const sample = JSON.parse(event.data) as HealthSample;
      latest.value = { ...latest.value, [sample.device_mac]: sample };
      const history = trendStore.value[sample.device_mac] ?? [];
      trendStore.value = { ...trendStore.value, [sample.device_mac]: [...history.slice(-119), sample] };
      lastSyncAt.value = new Date();
    } catch {
      // keep ui stable
    }
  };
}

function stopRuntime() {
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer);
    refreshTimer = null;
  }
  healthSocket?.close();
  healthSocket = null;
}

async function loadDirectoryForCurrentUser(user: SessionUser) {
  if (user.role === "family" && user.family_id) {
    return api.getFamilyCareDirectory(user.family_id);
  }
  return api.getCareDirectory();
}

async function loadDashboard() {
  if (!sessionUser.value) return;
  const data = await loadDirectoryForCurrentUser(sessionUser.value).catch(() => null);
  if (!data) return;
  directory.value = data;
  const allDevices = await api.listDevices().catch(() => [] as DeviceRecord[]);
  const allowed = new Set(data.elders.map((elder) => elder.device_mac));
  devices.value = allDevices.filter((device) => allowed.has(device.mac_address));
  await refreshDashboardData();
  if (selectedDeviceMac.value) await refreshTrend(selectedDeviceMac.value);
  stopRuntime();
  refreshTimer = window.setInterval(() => {
    void refreshDashboardData();
  }, 15000);
}

async function submitLogin() {
  authError.value = "";
  if (!loginUsername.value.trim()) {
    authError.value = "请选择用户名";
    return;
  }
  authLoading.value = true;
  try {
    const result = await api.loginMock({ username: loginUsername.value.trim(), password: loginPassword.value });
    sessionUser.value = result.user;
    sessionToken.value = result.token;
    localStorage.setItem(SESSION_KEY, result.token);
    routeTo(result.user.role === "family" ? "family" : "community");
  } catch {
    authError.value = "登录失败，请检查账号或密码（默认 123456）。";
  } finally {
    authLoading.value = false;
  }
}

async function restoreSession() {
  const token = localStorage.getItem(SESSION_KEY) ?? "";
  if (!token) return;
  const user = await api.me(token).catch(() => null);
  if (!user) {
    localStorage.removeItem(SESSION_KEY);
    return;
  }
  sessionToken.value = token;
  sessionUser.value = user;
}

function logout() {
  stopRuntime();
  sessionUser.value = null;
  sessionToken.value = "";
  directory.value = null;
  devices.value = [];
  latest.value = {};
  alarms.value = [];
  trendStore.value = {};
  localStorage.removeItem(SESSION_KEY);
}

async function generateCommunityAdviceText() {
  if (communityAdviceLoading.value) return;
  communityAdviceLoading.value = true;
  try {
    const deviceMacs = elderRows.value.slice(0, 6).map((row) => row.deviceMac);
    const response = await api.analyzeCommunity({
      question: "请给出社区值守今日优先处置顺序、回访建议和家属协同要点。",
      role: "community",
      mode: "auto",
      history_minutes: 720,
      per_device_limit: 240,
      device_macs: deviceMacs,
    });
    communityAdvice.value = response.answer || "暂无建议输出。";
  } catch {
    communityAdvice.value = "社区建议生成失败，请稍后重试。";
  } finally {
    communityAdviceLoading.value = false;
  }
}

async function generateFamilyAdviceText() {
  if (!selectedDeviceMac.value || familyAdviceLoading.value) return;
  familyAdviceLoading.value = true;
  try {
    const response = await api.analyze({
      device_mac: selectedDeviceMac.value,
      question: "请给出面向子女的今日照护建议和异常升级条件。",
      role: "family",
      mode: "auto",
      history_limit: 180,
      history_minutes: 720,
    });
    familyAdvice.value = response.answer || "暂无建议输出。";
  } catch {
    familyAdvice.value = "子女建议生成失败，请稍后再试。";
  } finally {
    familyAdviceLoading.value = false;
  }
}

watch(sessionUser, (user) => {
  if (user) void loadDashboard();
  else stopRuntime();
});

onMounted(async () => {
  if (window.location.hash) {
    const found = Object.entries(pageHash).find(([, hash]) => hash === window.location.hash)?.[0] as PageKey | undefined;
    if (found) activePage.value = found;
  } else {
    window.location.hash = pageHash.community;
  }
  hashListener = () => {
    const found = Object.entries(pageHash).find(([, hash]) => hash === window.location.hash)?.[0] as PageKey | undefined;
    if (found && allowedPages.value.includes(found)) activePage.value = found;
  };
  window.addEventListener("hashchange", hashListener);
  authAccounts.value = await api.listMockAccounts().catch(() => []);
  if (authAccounts.value.length) loginUsername.value = authAccounts.value[0].username;
  await restoreSession();
});

onUnmounted(() => {
  stopRuntime();
  if (hashListener) window.removeEventListener("hashchange", hashListener);
});
</script>

<template>
  <main class="app-shell">
    <section v-if="!isLoggedIn" class="login-shell">
      <article class="panel login-panel">
        <p class="kicker">AIoT Care Console</p>
        <h1>选择登录身份</h1>
        <p class="lead">社区端看全局，子女端只看自家老人。默认演示密码：123456。</p>
        <div class="login-grid">
          <label>
            用户名
            <select v-model="loginUsername" class="inline-select">
              <option v-for="account in authAccounts" :key="account.username" :value="account.username">
                {{ account.display_name }}（{{ account.role }} / {{ account.username }}）
              </option>
            </select>
          </label>
          <label>
            密码
            <input v-model="loginPassword" type="password" class="text-input" />
          </label>
          <button type="button" class="primary-btn" :disabled="authLoading" @click="submitLogin">
            {{ authLoading ? "登录中..." : "登录并进入系统" }}
          </button>
          <p v-if="authError" class="error-copy">{{ authError }}</p>
        </div>
      </article>
    </section>

    <template v-else>
      <header class="masthead">
        <div class="brand-block">
          <p class="kicker">AIoT Care Console</p>
          <h1>社区端与子女端双视图健康驾驶舱</h1>
          <p class="lead">关系模型：老人与子女绑定，且都属于同一社区。老人端不提供网页后台。</p>
        </div>
        <div class="meta-block">
          <span class="meta-pill">用户：{{ sessionUser?.name }}</span>
          <span class="meta-pill">角色：{{ sessionUser?.role }}</span>
          <span class="meta-pill">社区：{{ community?.name ?? "-" }}</span>
          <span class="meta-pill">同步：{{ syncLabel }}</span>
          <button type="button" class="ghost-btn" @click="logout">退出</button>
        </div>
      </header>

      <nav class="page-switch">
        <button v-if="allowedPages.includes('community')" type="button" class="switch-btn" :class="{ active: activePage === 'community' }" @click="routeTo('community')">社区端总览</button>
        <button v-if="allowedPages.includes('family')" type="button" class="switch-btn" :class="{ active: activePage === 'family' }" @click="routeTo('family')">子女端</button>
        <button v-if="allowedPages.includes('relation')" type="button" class="switch-btn" :class="{ active: activePage === 'relation' }" @click="routeTo('relation')">关系台账</button>
      </nav>

      <section v-if="activePage === 'community'" class="panel-grid community-grid">
        <article class="panel metric-panel">
          <h2>社区总览</h2>
          <div class="metric-row">
            <div class="metric-card"><span>老人总数</span><strong>{{ elders.length }}</strong></div>
            <div class="metric-card"><span>家庭总数</span><strong>{{ families.length }}</strong></div>
            <div class="metric-card"><span>高风险</span><strong>{{ elderRows.filter((r) => r.risk === 'high').length }}</strong></div>
            <div class="metric-card"><span>活动告警</span><strong>{{ alarms.filter((a) => !a.acknowledged).length }}</strong></div>
            <div class="metric-card"><span>重点设备</span><strong>{{ focusRow?.name ?? "-" }}</strong></div>
          </div>
        </article>

        <article class="panel table-panel">
          <h2>社区风险清单</h2>
          <div class="table-wrap">
            <table>
              <thead>
                <tr><th>老人</th><th>绑定子女</th><th>风险</th><th>心率</th><th>血氧</th><th>健康分</th></tr>
              </thead>
              <tbody>
                <tr v-for="row in elderRows.slice(0, 10)" :key="row.id" :class="{ current: row.deviceMac === selectedDeviceMac }" @click="selectedDeviceMac = row.deviceMac">
                  <td><strong>{{ row.name }}</strong><small>{{ row.apartment }}</small></td>
                  <td>{{ row.familyNames }}</td>
                  <td><span class="risk-pill" :class="riskClass(row.risk)">{{ riskLabel(row.risk) }}</span></td>
                  <td>{{ row.sample?.heart_rate ?? "-" }}</td>
                  <td>{{ row.sample?.blood_oxygen ?? "-" }}</td>
                  <td>{{ row.sample?.health_score ?? "-" }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>

        <article class="panel dispatch-panel">
          <h2>社区 AI 建议</h2>
          <button type="button" class="primary-btn" :disabled="communityAdviceLoading" @click="generateCommunityAdviceText">
            {{ communityAdviceLoading ? "生成中..." : "生成建议" }}
          </button>
          <p class="advice-copy">{{ communityAdvice }}</p>
        </article>
      </section>

      <section v-else-if="activePage === 'family'" class="panel-grid family-grid">
        <article class="panel family-header">
          <header class="panel-head">
            <h2>我的老人</h2>
            <select v-model="selectedFamilyId" class="inline-select">
              <option v-for="family in visibleFamilies" :key="family.id" :value="family.id">{{ family.name }}（{{ family.relationship }}）</option>
            </select>
          </header>
          <div class="family-cards">
            <button v-for="row in visibleRows" :key="row.id" type="button" class="family-elder-card" :class="[riskClass(row.risk), { active: row.deviceMac === selectedDeviceMac }]" @click="selectedDeviceMac = row.deviceMac">
              <div class="family-card-head"><strong>{{ row.name }}</strong><span>{{ riskLabel(row.risk) }}</span></div>
              <p>{{ row.apartment }}</p>
              <div class="family-kpis">
                <span>HR {{ row.sample?.heart_rate ?? "-" }}</span>
                <span>SpO2 {{ row.sample?.blood_oxygen ?? "-" }}</span>
                <span>健康分 {{ row.sample?.health_score ?? "-" }}</span>
              </div>
            </button>
          </div>
        </article>

        <article class="panel family-detail">
          <h2>子女建议与趋势</h2>
          <button type="button" class="primary-btn" :disabled="familyAdviceLoading" @click="generateFamilyAdviceText">
            {{ familyAdviceLoading ? "生成中..." : "生成建议" }}
          </button>
          <p class="advice-copy">{{ familyAdvice }}</p>
          <div class="trend-list">
            <div v-for="point in focusTrend.slice(-8).reverse()" :key="point.timestamp" class="trend-item">
              <span>{{ new Date(point.timestamp).toLocaleString('zh-CN', { hour12: false }) }}</span>
              <div class="trend-bars">
                <label>体温 {{ point.temperature.toFixed(1) }}℃</label>
                <progress :value="point.temperature" max="40"></progress>
                <label>健康分 {{ point.health_score ?? 0 }}</label>
                <progress :value="point.health_score ?? 0" max="100"></progress>
              </div>
            </div>
          </div>
        </article>
      </section>

      <section v-else class="panel-grid relation-grid">
        <article class="panel relation-intro">
          <h2>关系说明</h2>
          <ul class="rule-list">
            <li>老人和子女存在绑定关系。</li>
            <li>老人和子女都属于同一社区。</li>
            <li>社区端可见全局，子女端只看自家。</li>
            <li>老人端不提供网页后台。</li>
          </ul>
        </article>
        <article class="panel relation-table">
          <h2>老人-子女绑定台账</h2>
          <div class="table-wrap">
            <table>
              <thead><tr><th>老人</th><th>设备</th><th>社区</th><th>绑定子女</th></tr></thead>
              <tbody>
                <tr v-for="elder in elders" :key="elder.id">
                  <td>{{ elder.name }}</td>
                  <td>{{ elder.device_mac }}</td>
                  <td>{{ community?.name ?? '-' }}</td>
                  <td>{{ relationFamiliesText(elder.family_ids) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>
      </section>
    </template>
  </main>
</template>
