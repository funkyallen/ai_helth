<script setup lang="ts">
import * as echarts from "echarts";
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import type { HealthSample } from "../api/client";

const props = defineProps<{
  deviceMac: string;
  samples: HealthSample[];
  windowMinutes: number;
}>();

const emit = defineEmits<{
  (event: "change-window", minutes: number): void;
}>();

const chartRef = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;

const trendMetrics = computed(() => {
  const first = props.samples[0];
  const last = props.samples[props.samples.length - 1];
  if (!first || !last) {
    return [
      { label: "心率变化", value: "--" },
      { label: "血氧变化", value: "--" },
      { label: "温度变化", value: "--" },
    ];
  }
  return [
    { label: "心率变化", value: `${last.heart_rate - first.heart_rate >= 0 ? '+' : ''}${last.heart_rate - first.heart_rate} bpm` },
    { label: "血氧变化", value: `${last.blood_oxygen - first.blood_oxygen >= 0 ? '+' : ''}${last.blood_oxygen - first.blood_oxygen}%` },
    { label: "体温变化", value: `${(last.temperature - first.temperature >= 0 ? '+' : '') + (last.temperature - first.temperature).toFixed(1)}℃` },
  ];
});

function renderChart() {
  if (!chartRef.value) return;
  chart ??= echarts.init(chartRef.value);
  chart.setOption({
    backgroundColor: "transparent",
    animationDuration: 600,
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(5, 16, 22, 0.92)",
      borderColor: "rgba(123, 242, 196, 0.25)",
      textStyle: { color: "#eef8f5" },
    },
    legend: {
      top: 4,
      textStyle: { color: "#d9eceb" },
    },
    grid: { left: 42, right: 72, top: 52, bottom: 42 },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: props.samples.map((sample) =>
        new Date(sample.timestamp).toLocaleTimeString("zh-CN", {
          hour12: false,
          hour: "2-digit",
          minute: "2-digit",
        }),
      ),
      axisLine: { lineStyle: { color: "rgba(198, 224, 223, 0.16)" } },
      axisLabel: { color: "#8fb6b4" },
    },
    yAxis: [
      {
        type: "value",
        name: "心率",
        min: 40,
        max: 180,
        axisLabel: { color: "#8fb6b4" },
        splitLine: { lineStyle: { color: "rgba(255, 255, 255, 0.06)" } },
      },
      {
        type: "value",
        name: "体温",
        min: 34,
        max: 42,
        position: "right",
        axisLabel: { color: "#8fb6b4" },
      },
      {
        type: "value",
        name: "血氧/评分",
        min: 0,
        max: 100,
        position: "right",
        offset: 54,
        axisLabel: { color: "#8fb6b4" },
      },
    ],
    dataZoom: [
      { type: "inside" },
      {
        type: "slider",
        height: 18,
        bottom: 10,
        borderColor: "transparent",
        backgroundColor: "rgba(255, 255, 255, 0.04)",
        fillerColor: "rgba(116, 242, 195, 0.18)",
      },
    ],
    series: [
      {
        name: "心率",
        type: "line",
        smooth: true,
        symbol: "none",
        data: props.samples.map((sample) => sample.heart_rate),
        lineStyle: { width: 3, color: "#ff8a65" },
        areaStyle: { color: "rgba(255, 138, 101, 0.12)" },
        markLine: {
          symbol: "none",
          lineStyle: { color: "rgba(255, 138, 101, 0.4)" },
          data: [{ yAxis: 110, label: { formatter: "关注阈值" } }],
        },
      },
      {
        name: "体温",
        type: "line",
        smooth: true,
        yAxisIndex: 1,
        symbol: "none",
        data: props.samples.map((sample) => sample.temperature),
        lineStyle: { width: 2, color: "#56d7b6" },
      },
      {
        name: "血氧",
        type: "line",
        smooth: true,
        yAxisIndex: 2,
        symbol: "none",
        data: props.samples.map((sample) => sample.blood_oxygen),
        lineStyle: { width: 2, color: "#7ab8ff" },
      },
      {
        name: "健康分",
        type: "bar",
        yAxisIndex: 2,
        barMaxWidth: 10,
        data: props.samples.map((sample) => sample.health_score ?? 0),
        itemStyle: { color: "rgba(255, 203, 119, 0.75)", borderRadius: [10, 10, 0, 0] },
      },
    ],
  });
}

function handleResize() {
  chart?.resize();
}

onMounted(() => {
  renderChart();
  window.addEventListener("resize", handleResize);
});

watch(() => props.samples, renderChart, { deep: true });

onUnmounted(() => {
  window.removeEventListener("resize", handleResize);
  chart?.dispose();
});
</script>

<template>
  <section class="panel trend-panel">
    <div class="panel-head">
      <div>
        <h2>生命体征趋势</h2>
        <p class="panel-subtitle">选中设备的近时段心率、体温、血氧与健康分联动变化。</p>
      </div>
      <span>{{ deviceMac || "请选择设备" }}</span>
    </div>
    <div class="trend-toolbar">
      <div class="trend-window-row">
        <button class="filter-chip" :class="{ active: windowMinutes === 60 }" @click="emit('change-window', 60)">1 小时</button>
        <button class="filter-chip" :class="{ active: windowMinutes === 180 }" @click="emit('change-window', 180)">3 小时</button>
        <button class="filter-chip" :class="{ active: windowMinutes === 720 }" @click="emit('change-window', 720)">12 小时</button>
      </div>
      <div class="trend-kpis">
        <span v-for="item in trendMetrics" :key="item.label">{{ item.label }} {{ item.value }}</span>
      </div>
    </div>
    <div ref="chartRef" class="trend-canvas"></div>
  </section>
</template>
