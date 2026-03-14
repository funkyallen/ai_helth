<script setup lang="ts">
import * as echarts from "echarts";
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import type { CommunityOverview } from "../api/client";

const props = defineProps<{
  overview: CommunityOverview | null;
  avgScore: number;
  avgSpo2: number;
  sosCount: number;
}>();

const chartRef = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;

const clusterCounts = computed(() => ({
  healthy: props.overview?.clusters.healthy?.length ?? 0,
  attention: props.overview?.clusters.attention?.length ?? 0,
  danger: props.overview?.clusters.danger?.length ?? 0,
}));

const anomalyLabel = computed(() => {
  const score = props.overview?.intelligent_anomaly_score ?? 0;
  if (score >= 10) return "高波动";
  if (score >= 5) return "需关注";
  return "稳定";
});

function renderChart() {
  if (!chartRef.value) return;
  chart ??= echarts.init(chartRef.value);
  chart.setOption({
    backgroundColor: "transparent",
    tooltip: { trigger: "item" },
    legend: {
      bottom: 0,
      textStyle: { color: "#d5e7e6" },
      icon: "circle",
    },
    series: [
      {
        type: "pie",
        radius: ["55%", "78%"],
        center: ["50%", "42%"],
        avoidLabelOverlap: false,
        label: { show: false },
        data: [
          { value: clusterCounts.value.healthy, name: "健康群", itemStyle: { color: "#74f2c3" } },
          { value: clusterCounts.value.attention, name: "关注群", itemStyle: { color: "#ffcb77" } },
          { value: clusterCounts.value.danger, name: "危险群", itemStyle: { color: "#ff6b6b" } },
        ],
      },
    ],
    graphic: [
      {
        type: "text",
        left: "center",
        top: "32%",
        style: {
          text: `${props.overview?.device_count ?? 0}`,
          fill: "#f6fcfb",
          font: "700 34px 'Aptos Display', 'Trebuchet MS', sans-serif",
        },
      },
      {
        type: "text",
        left: "center",
        top: "47%",
        style: {
          text: "社区设备",
          fill: "rgba(214, 233, 233, 0.78)",
          font: "14px 'Aptos', 'Microsoft YaHei UI', sans-serif",
        },
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

watch(() => props.overview, renderChart, { deep: true });

onUnmounted(() => {
  window.removeEventListener("resize", handleResize);
  chart?.dispose();
});
</script>

<template>
  <section class="panel overview-panel">
    <div class="panel-head">
      <div>
        <h2>社区态势</h2>
        <p class="panel-subtitle">从群体风险分层、异常评分和设备集群状态看当前整体走势。</p>
      </div>
      <span>{{ anomalyLabel }}</span>
    </div>
    <div class="overview-layout">
      <div ref="chartRef" class="overview-canvas"></div>
      <div class="overview-content">
        <div class="summary-grid">
          <article>
            <span>平均健康分</span>
            <strong>{{ avgScore }}</strong>
          </article>
          <article>
            <span>平均血氧</span>
            <strong>{{ avgSpo2 }}%</strong>
          </article>
          <article>
            <span>SOS 台数</span>
            <strong>{{ sosCount }}</strong>
          </article>
          <article>
            <span>异常评分</span>
            <strong>{{ overview?.intelligent_anomaly_score?.toFixed(2) ?? "0.00" }}</strong>
          </article>
        </div>
        <div class="cluster-stack">
          <div class="cluster-card healthy">
            <span>健康群</span>
            <strong>{{ clusterCounts.healthy }}</strong>
            <small>{{ overview?.clusters.healthy?.slice(0, 3).join(" / ") || "暂无" }}</small>
          </div>
          <div class="cluster-card attention">
            <span>关注群</span>
            <strong>{{ clusterCounts.attention }}</strong>
            <small>{{ overview?.clusters.attention?.slice(0, 3).join(" / ") || "暂无" }}</small>
          </div>
          <div class="cluster-card danger">
            <span>危险群</span>
            <strong>{{ clusterCounts.danger }}</strong>
            <small>{{ overview?.clusters.danger?.slice(0, 3).join(" / ") || "暂无" }}</small>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
