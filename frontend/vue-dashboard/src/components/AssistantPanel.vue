<script setup lang="ts">
import { computed, ref } from "vue";
import { api, type AgentResponse, type HealthSample } from "../api/client";

const props = defineProps<{
  deviceMac: string;
  sample: HealthSample | null;
  riskLabel: string;
}>();

const quickPrompts = [
  "请结合最近一段时间的监测趋势，给出完整风险判断、观察重点和建议动作。",
  "请站在家属角度，说明当前最需要关注的指标和今晚的照护建议。",
  "请解释最近波动最明显的两项指标，并给出复测顺序。",
];

const question = ref(quickPrompts[0]);
const answer = ref("等待单设备分析...");
const loading = ref(false);
const mode = ref("auto");
const resultMeta = ref<AgentResponse | null>(null);

const recommendations = computed(() => {
  const rows = resultMeta.value?.analysis?.recommendations;
  return Array.isArray(rows) ? rows.map((item) => String(item)) : [];
});

const riskFlags = computed(() => {
  const rows = resultMeta.value?.analysis?.risk_flags;
  return Array.isArray(rows) ? rows.map((item) => String(item)) : [];
});

const references = computed(() => resultMeta.value?.references ?? []);

async function analyze() {
  if (!props.deviceMac) {
    answer.value = "请先选择一个设备。";
    return;
  }
  loading.value = true;
  try {
    const result = await api.analyze({
      device_mac: props.deviceMac,
      question: question.value,
      role: "family",
      mode: mode.value,
      history_limit: 240,
      history_minutes: 1440,
    });
    resultMeta.value = result;
    answer.value = result.answer;
  } catch (error) {
    answer.value = `分析失败：${String(error)}`;
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <section class="panel assistant-panel">
    <div class="panel-head">
      <div>
        <h2>单设备 AI 助手</h2>
        <p class="panel-subtitle">面向家属或医护解读单台设备近时段数据，输出完整可执行建议。</p>
      </div>
      <span>{{ riskLabel }}</span>
    </div>
    <div class="assistant-toolbar">
      <span class="context-chip">{{ deviceMac || "未选择设备" }}</span>
      <span v-if="sample?.sos_flag" class="context-chip danger">SOS 触发</span>
      <span v-if="sample" class="context-chip">SpO2 {{ sample.blood_oxygen }}%</span>
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
    <button class="primary-action" :disabled="loading" @click="analyze">
      {{ loading ? "分析中..." : "生成设备分析" }}
    </button>
    <div v-if="resultMeta" class="assistant-meta">
      <span>模型模式：{{ resultMeta.mode }}</span>
      <span>网络状态：{{ resultMeta.network_online ? "在线" : "离线" }}</span>
      <span>知识命中：{{ resultMeta.references.length }}</span>
    </div>
    <p class="assistant-answer">{{ answer }}</p>
    <div v-if="riskFlags.length" class="assistant-chip-row">
      <span v-for="flag in riskFlags" :key="flag" class="analysis-chip">{{ flag }}</span>
    </div>
    <ul v-if="recommendations.length" class="assistant-list">
      <li v-for="item in recommendations" :key="item">{{ item }}</li>
    </ul>
    <div v-if="references.length" class="reference-block">
      <span>知识补充</span>
      <small>{{ references[0] }}</small>
    </div>
  </section>
</template>
