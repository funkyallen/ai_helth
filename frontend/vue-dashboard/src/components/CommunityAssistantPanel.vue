<script setup lang="ts">
import { computed, ref } from "vue";
import { api, type AgentResponse, type CommunityOverview } from "../api/client";

const props = defineProps<{
  overview: CommunityOverview | null;
}>();

const quickPrompts = [
  "请根据最近24小时社区内多台设备的监测数据，给出总体态势、重点关注对象和调度建议。",
  "请面向社区值守人员，生成一段适合现场答辩展示的社区健康态势解读。",
  "请重点分析当前高风险设备的共性问题，并给出分级随访安排。",
];

const question = ref(quickPrompts[0]);
const answer = ref("等待社区汇总分析...");
const loading = ref(false);
const mode = ref("auto");
const resultMeta = ref<AgentResponse | null>(null);

const riskDistribution = computed(() => {
  const value = resultMeta.value?.analysis?.risk_distribution;
  return value && typeof value === "object" ? (value as Record<string, number>) : null;
});

const priorityDevices = computed(() => {
  const rows = resultMeta.value?.analysis?.priority_devices;
  return Array.isArray(rows) ? rows : [];
});

const references = computed(() => resultMeta.value?.references ?? []);

async function analyzeCommunity() {
  loading.value = true;
  try {
    const result = await api.analyzeCommunity({
      question: question.value,
      role: "community",
      mode: mode.value,
      history_minutes: 1440,
      per_device_limit: 240,
    });
    resultMeta.value = result;
    answer.value = result.answer;
  } catch (error) {
    answer.value = `分析失败：${String(error)}`;
  } finally {
    loading.value = false;
  }
}

function priorityLabel(item: unknown) {
  if (!item || typeof item !== "object") {
    return "--";
  }
  const row = item as Record<string, unknown>;
  return String(row.device_name ?? row.device_mac ?? "--");
}

function prioritySummary(item: unknown) {
  if (!item || typeof item !== "object") {
    return "等待分析结果补充。";
  }
  const row = item as Record<string, unknown>;
  return String(
    row.summary ??
      row.reason ??
      row.action ??
      row.risk_level ??
      "建议优先电话回访并结合历史趋势复核。",
  );
}
</script>

<template>
  <section class="panel community-panel">
    <div class="panel-head">
      <div>
        <h2>社区汇总助手</h2>
        <p class="panel-subtitle">站在社区值守与答辩演示视角，输出群体态势、重点对象和资源调度建议。</p>
      </div>
      <span>社区级分析</span>
    </div>
    <div class="assistant-toolbar">
      <span class="context-chip">健康群 {{ props.overview?.clusters.healthy?.length ?? 0 }}</span>
      <span class="context-chip warning">关注群 {{ props.overview?.clusters.attention?.length ?? 0 }}</span>
      <span class="context-chip danger">危险群 {{ props.overview?.clusters.danger?.length ?? 0 }}</span>
      <select v-model="mode" class="mode-select">
        <option value="auto">自动路由</option>
        <option value="cloud">云端 Qwen</option>
        <option value="local">本地 Ollama</option>
      </select>
    </div>
    <div class="prompt-chip-row">
      <button v-for="item in quickPrompts" :key="item" class="prompt-chip" @click="question = item">{{ item }}</button>
    </div>
    <textarea v-model="question" rows="5"></textarea>
    <button class="primary-action" :disabled="loading" @click="analyzeCommunity">
      {{ loading ? "汇总中..." : "生成社区分析" }}
    </button>
    <div v-if="resultMeta" class="assistant-meta">
      <span>模型模式：{{ resultMeta.mode }}</span>
      <span>网络状态：{{ resultMeta.network_online ? "在线" : "离线" }}</span>
      <span>知识命中：{{ resultMeta.references.length }}</span>
    </div>
    <p class="assistant-answer">{{ answer }}</p>
    <div v-if="riskDistribution" class="distribution-row">
      <span>高风险 {{ riskDistribution.high ?? 0 }}</span>
      <span>中风险 {{ riskDistribution.medium ?? 0 }}</span>
      <span>低风险 {{ riskDistribution.low ?? 0 }}</span>
    </div>
    <div v-if="priorityDevices.length" class="community-priority-row">
      <article
        v-for="(item, index) in priorityDevices.slice(0, 4)"
        :key="`${priorityLabel(item)}-${index}`"
        class="mini-priority-card"
      >
        <span>重点 {{ index + 1 }}</span>
        <strong>{{ priorityLabel(item) }}</strong>
        <small>{{ prioritySummary(item) }}</small>
      </article>
    </div>
    <div v-if="references.length" class="reference-block">
      <span>知识补充</span>
      <small>{{ references[0] }}</small>
    </div>
  </section>
</template>
