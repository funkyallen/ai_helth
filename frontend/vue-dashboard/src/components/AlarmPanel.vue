<script setup lang="ts">
import type { AlarmRecord } from "../api/client";

defineProps<{ alarms: AlarmRecord[] }>();

defineEmits<{
  (event: "ack", alarmId: string): void;
}>();
</script>

<template>
  <section class="panel alarm-panel">
    <div class="panel-head">
      <h2>优先级告警</h2>
      <span>Redis Sorted Set 思路</span>
    </div>
    <div class="alarm-list">
      <article v-for="alarm in alarms" :key="alarm.id" class="alarm-card">
        <div>
          <p>{{ alarm.device_mac }}</p>
          <strong>{{ alarm.message }}</strong>
        </div>
        <div class="alarm-actions">
          <span>等级 {{ alarm.alarm_level }}</span>
          <button @click="$emit('ack', alarm.id)">处置完成</button>
        </div>
      </article>
      <p v-if="!alarms.length" class="empty-copy">当前没有活动告警。</p>
    </div>
  </section>
</template>
