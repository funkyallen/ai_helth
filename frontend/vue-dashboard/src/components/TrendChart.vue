<script setup lang="ts">
import * as echarts from "echarts";
import { onMounted, onUnmounted, ref, watch } from "vue";
import type { HealthSample } from "../api/client";

const props = defineProps<{
  deviceMac: string;
  samples: HealthSample[];
}>();

const chartRef = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;

function renderChart() {
  if (!chartRef.value) return;
  chart ??= echarts.init(chartRef.value);
  chart.setOption({
    backgroundColor: "transparent",
    tooltip: { trigger: "axis" },
    legend: { textStyle: { color: "#e8f3f4" } },
    xAxis: {
      type: "category",
      data: props.samples.map((sample) => new Date(sample.timestamp).toLocaleTimeString()),
      axisLabel: { color: "#9fc0c3" },
    },
    yAxis: [
      { type: "value", name: "心率", axisLabel: { color: "#9fc0c3" } },
      { type: "value", name: "体温", axisLabel: { color: "#9fc0c3" } },
    ],
    series: [
      {
        name: "心率",
        type: "line",
        smooth: true,
        data: props.samples.map((sample) => sample.heart_rate),
        lineStyle: { color: "#ff8358" },
        areaStyle: { color: "rgba(255, 131, 88, 0.18)" },
      },
      {
        name: "体温",
        type: "line",
        smooth: true,
        yAxisIndex: 1,
        data: props.samples.map((sample) => sample.temperature),
        lineStyle: { color: "#5bc6a9" },
        areaStyle: { color: "rgba(91, 198, 169, 0.16)" },
      },
    ],
  });
}

onMounted(renderChart);
watch(() => props.samples, renderChart, { deep: true });
onUnmounted(() => chart?.dispose());
</script>

<template>
  <section class="panel trend-panel">
    <div class="panel-head">
      <h2>实时趋势</h2>
      <span>{{ deviceMac || '请选择设备' }}</span>
    </div>
    <div ref="chartRef" class="trend-canvas"></div>
  </section>
</template>
