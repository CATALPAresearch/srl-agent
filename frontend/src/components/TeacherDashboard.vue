<template>
  <div class="td-root">

    <!-- HEADER -->
    <div class="td-header">
      <h1>Teacher Dashboard</h1>
      <p>Overview of student learning behavior</p>
    </div>

    <!-- KPI SECTION -->
    <div class="td-kpi-grid">
      <div class="td-kpi" v-for="k in kpis" :key="k.label">
        <div class="td-kpi-value">{{ k.value }}</div>
        <div class="td-kpi-label">{{ k.label }}</div>
      </div>
    </div>

    <!-- CHARTS -->
    <div class="td-grid">

      <div class="td-card">
        <h3>Learning Strategies</h3>
        <canvas ref="strategyChart"></canvas>
      </div>

      <div class="td-card">
        <h3>Drop-off by Step</h3>
        <canvas ref="dropoffChart"></canvas>
      </div>

      <div class="td-card">
        <h3>Completion Funnel</h3>
        <canvas ref="funnelChart"></canvas>
      </div>

    </div>

  </div>
</template>

<script>
import Vue from "vue";
import axios from "axios";
import Chart from "chart.js";

export default Vue.extend({
  name: "TeacherDashboard",

  data() {
    return {
      stats: {},
      charts: {
        strategy: null,
        dropoff: null,
        funnel: null,
      },
    };
  },

  computed: {
    kpis() {
      return [
        { label: "Students", value: this.stats.total_students || 0 },
        { label: "Completed", value: this.stats.total_completed || 0 },
        { label: "Avg Duration (min)", value: this.stats.avg_duration_minutes || 0 },
        { label: "Messages", value: this.stats.total_messages || 0 },
      ];
    },
  },

  async mounted() {
    await this.loadData();
  },

  methods: {
    async loadData() {
      try {
        const res = await axios.get("/dashboard/stats");
        this.stats = res.data;

        this.$nextTick(() => {
          this.renderCharts();
        });

      } catch (e) {
        console.error("TeacherDashboard error:", e);
      }
    },

    renderCharts() {
      this.renderStrategy();
      this.renderDropoff();
      this.renderFunnel();
    },

    renderStrategy() {
      const el = this.$refs.strategyChart;
      if (!el || !this.stats.strategy_distribution) return;

      if (this.charts.strategy) this.charts.strategy.destroy();

      this.charts.strategy = new Chart(el, {
        type: "bar",
        data: {
          labels: this.stats.strategy_distribution.map(s => s.strategy),
          datasets: [{
            data: this.stats.strategy_distribution.map(s => s.count),
            backgroundColor: "#8b5cf6"
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false
        }
      });
    },

    renderDropoff() {
      const el = this.$refs.dropoffChart;
      if (!el || !this.stats.dropoff_distribution) return;

      if (this.charts.dropoff) this.charts.dropoff.destroy();

      this.charts.dropoff = new Chart(el, {
        type: "bar",
        data: {
          labels: this.stats.dropoff_distribution.map(d => d.step),
          datasets: [{
            data: this.stats.dropoff_distribution.map(d => d.count),
            backgroundColor: "#ef4444"
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false
        }
      });
    },

    renderFunnel() {
      const el = this.$refs.funnelChart;
      if (!el || !this.stats.completion_funnel) return;

      if (this.charts.funnel) this.charts.funnel.destroy();

      this.charts.funnel = new Chart(el, {
        type: "bar",
        data: {
          labels: this.stats.completion_funnel.map(f => f.step),
          datasets: [{
            data: this.stats.completion_funnel.map(f => f.count),
            backgroundColor: "#06b6d4"
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false
        }
      });
    },
  },
});
</script>

<style scoped>
.td-root {
  padding: 24px;
  background: #f6f7fb;
  min-height: 100vh;
  font-family: "DM Sans", sans-serif;
}

/* HEADER */
.td-header {
  margin-bottom: 20px;
}

.td-header h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
}

.td-header p {
  margin: 4px 0 0;
  color: #6b7280;
  font-size: 13px;
}

/* KPI GRID */
.td-kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}

.td-kpi {
  background: white;
  border-radius: 10px;
  padding: 14px;
  box-shadow: 0 2px 6px rgba(0,0,0,0.06);
}

.td-kpi-value {
  font-size: 22px;
  font-weight: 700;
  color: #4f46e5;
}

.td-kpi-label {
  font-size: 12px;
  color: #6b7280;
}

/* CHART GRID */
.td-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.td-card {
  background: white;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  height: 320px;
  display: flex;
  flex-direction: column;
}

.td-card h3 {
  margin: 0 0 10px;
  font-size: 14px;
  font-weight: 600;
  color: #374151;
}

canvas {
  flex: 1;
}
</style>