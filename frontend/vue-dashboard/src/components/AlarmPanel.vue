<script setup lang="ts">
import type { AlarmRecord } from "../api/client";

defineProps<{ alarms: AlarmRecord[] }>();

defineEmits<{
  (event: "ack", alarmId: string): void;
}>();

function alarmTone(level: number) {
  if (level >= 4) return "sos";
  if (level >= 3) return "critical";
  if (level >= 2) return "warning";
  return "notice";
}

function alarmLabel(level: number) {
  if (level >= 4) return "SOS";
  if (level >= 3) return "严重";
  if (level >= 2) return "预警";
  return "提醒";
}
</script>

<template>
  <section class="panel alarm-panel">
    <div class="panel-head">
      <div>
        <h2>优先级告警</h2>
        <p class="panel-subtitle">按处置优先级聚合实时报警，适合值守人员快速分派动作。</p>
      </div>
      <span>{{ alarms.length }} 条活动告警</span>
    </div>
    <div class="alarm-list">
      <article
        v-for="alarm in alarms"
        :key="alarm.id"
        class="alarm-card"
        :class="`alarm-${alarmTone(alarm.alarm_level)}`"
      >
        <div class="alarm-copy">
          <div class="alarm-title-row">
            <p>{{ alarm.device_mac }}</p>
            <span class="alarm-tag">{{ alarmLabel(alarm.alarm_level) }}</span>
          </div>
          <strong>{{ alarm.message }}</strong>
          <small>{{ new Date(alarm.created_at).toLocaleString("zh-CN", { hour12: false }) }}</small>
        </div>
        <div class="alarm-actions">
          <span>等级 {{ alarm.alarm_level }}</span>
          <button @click="$emit('ack', alarm.id)">处置完成</button>
        </div>
      </article>
      <p v-if="!alarms.length" class="empty-copy">当前没有活动告警，系统处于平稳巡检状态。</p>
    </div>
  </section>
</template>
