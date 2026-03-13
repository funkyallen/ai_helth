<script setup lang="ts">
import { ref } from "vue";
import { api } from "../api/client";

const props = defineProps<{ deviceMac: string }>();

const question = ref("请结合最近趋势，给出风险提示和建议动作。");
const answer = ref("等待分析...");
const loading = ref(false);

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
      mode: "local",
    });
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
      <h2>AI 健康助手</h2>
      <span>Qwen / Ollama 双模式</span>
    </div>
    <textarea v-model="question" rows="4"></textarea>
    <button class="primary-action" :disabled="loading" @click="analyze">
      {{ loading ? '分析中...' : '生成建议' }}
    </button>
    <p class="assistant-answer">{{ answer }}</p>
  </section>
</template>
