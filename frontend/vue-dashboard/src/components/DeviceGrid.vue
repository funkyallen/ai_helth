<script setup lang="ts">
import type { DeviceRecord, HealthSample } from "../api/client";

defineProps<{
  devices: DeviceRecord[];
  latest: Record<string, HealthSample>;
  selectedMac: string;
}>();

defineEmits<{
  (event: "select", mac: string): void;
}>();
</script>

<template>
  <section class="panel device-panel">
    <div class="panel-head">
      <h2>设备总览</h2>
      <span>10+ 手环接入</span>
    </div>
    <div class="device-list">
      <button
        v-for="device in devices"
        :key="device.mac_address"
        class="device-card"
        :class="{ active: selectedMac === device.mac_address }"
        @click="$emit('select', device.mac_address)"
      >
        <div>
          <p>{{ device.device_name }}</p>
          <strong>{{ device.mac_address }}</strong>
        </div>
        <div class="metrics" v-if="latest[device.mac_address]">
          <span>{{ latest[device.mac_address].heart_rate }} bpm</span>
          <span>{{ latest[device.mac_address].temperature.toFixed(1) }}℃</span>
          <span>{{ latest[device.mac_address].blood_oxygen }}%</span>
        </div>
        <small>健康分 {{ latest[device.mac_address]?.health_score ?? '--' }}</small>
      </button>
    </div>
  </section>
</template>
