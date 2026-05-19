<template>
  <div class="td-root">
    <!-- Header -->
    <div class="td-header">
      <div class="td-header-left">
        <span class="td-badge">TEACHER</span>
        <h1 class="td-title">{{ t("title") }}</h1>
      </div>
      <div class="td-header-right">
        <div class="td-filter-group">
          <div class="td-date-field">
            <label>{{ t("from") }}</label>
            <input type="date" v-model="dateFrom" />
          </div>
          <div class="td-date-field">
            <label>{{ t("to") }}</label>
            <input type="date" v-model="dateTo" />
          </div>
          <button class="td-btn td-btn-primary" @click="loadStats">
            {{ t("apply") }}
          </button>
          <button class="td-btn td-btn-ghost" @click="clearFilter">
            {{ t("clear") }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="isLoading" class="td-loading">
      <div class="td-spinner"></div>
      <p>{{ t("loading") }}</p>
    </div>
    <div v-else-if="error" class="td-error">{{ error }}</div>

    <div v-else>
      <!-- KPI Grid -->
      <div class="td-kpi-grid">
        <div
          class="td-kpi"
          v-for="kpi in kpiCards"
          :key="kpi.label"
          :style="'--accent: ' + kpi.color"
          @mouseenter="
            logInteraction('dashboard_kpi_hovered', { kpi: kpi.label })
          "
        >
          <div class="td-kpi-value">{{ kpi.value }}</div>
          <div class="td-kpi-label">{{ kpi.label }}</div>
          <div class="td-kpi-sub" v-if="kpi.sub">{{ kpi.sub }}</div>
          <div class="td-kpi-bar"></div>
        </div>
      </div>

      <!-- Info Row: Completion Rate -->
      <div class="td-charts-row">
        <div class="td-chart-card td-chart-narrow td-info-card">
          <div class="td-chart-title">{{ t("completionRate") }}</div>
          <div class="td-big-stat">{{ completionRate }}%</div>
          <div class="td-chart-sub">
            {{ stats.total_completed }} {{ t("of") }}
            {{ stats.total_students }} {{ t("studentsCompleted") }}
          </div>
          <div class="td-progress-bar-wrap">
            <div
              class="td-progress-bar"
              :style="'width: ' + completionRate + '%'"
            ></div>
          </div>
        </div>
      </div>

      <!-- Charts Row 1: Drop-off + Funnel -->
      <div class="td-charts-row">
        <div class="td-chart-card td-chart-wide">
          <div class="td-chart-header-row">
            <div>
              <span class="td-chart-title">{{ t("dropoffTitle") }}</span>
              <span class="td-chart-sub">{{ t("dropoffSub") }}</span>
            </div>
            <button class="td-toggle-btn" @click="toggle('dropoff')">
              {{ showTable.dropoff ? t("showChart") : t("showTable") }}
            </button>
          </div>
          <div class="td-canvas-wrap" v-if="!showTable.dropoff">
            <canvas ref="dropoffChart"></canvas>
            <div
              v-if="
                !stats.dropoff_distribution ||
                !stats.dropoff_distribution.length
              "
              class="td-empty"
            >
              {{ t("noData") }}
            </div>
          </div>
          <table v-else class="td-table td-table-mt">
            <thead>
              <tr>
                <th>{{ t("step") }}</th>
                <th>{{ t("students") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-if="
                  !stats.dropoff_distribution ||
                  !stats.dropoff_distribution.length
                "
              >
                <td colspan="2" class="td-empty-row">{{ t("noData") }}</td>
              </tr>
              <tr
                v-for="r in stats.dropoff_distribution"
                :key="r.step"
                @mouseenter="
                  logInteraction('dashboard_table_row_hovered', {
                    chart: 'dropoff',
                    step: r.step,
                    count: r.count,
                  })
                "
              >
                <td>{{ r.step }}</td>
                <td>{{ r.count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="td-chart-card td-chart-narrow">
          <div class="td-chart-header-row">
            <div>
              <span class="td-chart-title">{{ t("funnelTitle") }}</span>
              <span class="td-chart-sub">{{ t("funnelSub") }}</span>
            </div>
            <button class="td-toggle-btn" @click="toggle('funnel')">
              {{ showTable.funnel ? t("showChart") : t("showTable") }}
            </button>
          </div>
          <div class="td-canvas-wrap" v-if="!showTable.funnel">
            <canvas ref="funnelChart"></canvas>
            <div
              v-if="!stats.completion_funnel || !stats.completion_funnel.length"
              class="td-empty"
            >
              {{ t("noData") }}
            </div>
          </div>
          <table v-else class="td-table td-table-mt">
            <thead>
              <tr>
                <th>{{ t("step") }}</th>
                <th>{{ t("reached") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-if="
                  !stats.completion_funnel || !stats.completion_funnel.length
                "
              >
                <td colspan="2" class="td-empty-row">{{ t("noData") }}</td>
              </tr>
              <tr
                v-for="r in stats.completion_funnel"
                :key="r.step"
                @mouseenter="
                  logInteraction('dashboard_table_row_hovered', {
                    chart: 'funnel',
                    step: r.step,
                    count: r.count,
                  })
                "
              >
                <td>{{ r.step }}</td>
                <td>{{ r.count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Charts Row 2: Weekly Activity -->
      <div class="td-charts-row">
        <div class="td-chart-card" style="flex: 1">
          <div class="td-chart-header-row">
            <div>
              <span class="td-chart-title">{{ t("weeklyTitle") }}</span>
              <span class="td-chart-sub">{{ t("weeklySub") }}</span>
            </div>
            <button class="td-toggle-btn" @click="toggle('weekly')">
              {{ showTable.weekly ? t("showChart") : t("showTable") }}
            </button>
          </div>
          <div class="td-weekly-scroll" v-if="!showTable.weekly">
            <div class="td-canvas-wrap">
              <canvas ref="weeklyChart"></canvas>
              <div
                v-if="!stats.weekly_activity || !stats.weekly_activity.length"
                class="td-empty"
              >
                {{ t("noData") }}
              </div>
            </div>
          </div>
          <table v-else class="td-table td-table-mt">
            <thead>
              <tr>
                <th>{{ t("week") }}</th>
                <th>{{ t("responses") }}</th>
                <th>{{ t("users") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-if="!stats.weekly_activity || !stats.weekly_activity.length"
              >
                <td colspan="3" class="td-empty-row">{{ t("noData") }}</td>
              </tr>
              <tr
                v-for="r in stats.weekly_activity"
                :key="r.week"
                @mouseenter="
                  logInteraction('dashboard_table_row_hovered', {
                    chart: 'weekly',
                    week: r.week,
                    responses: r.messages,
                    users: r.users,
                  })
                "
              >
                <td>{{ r.week }}</td>
                <td>{{ r.messages }}</td>
                <td>{{ r.users }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from "axios";
import Chart from "chart.js";

var GREEN = "#2563b0";
var GREEN_MID = "rgba(37,99,176,0.5)";

var TRANSLATIONS = {
  de: {
    title: "Analyse-Dashboard",
    from: "VON",
    to: "BIS",
    apply: "Anwenden",
    clear: "ZurÃ¼cksetzen",
    loading: "Lade Daten\u2026",
    noData: "Noch keine Daten",
    showChart: "Diagramm",
    showTable: "Tabelle",
    // KPI labels
    totalStudents: "Studierende gesamt",
    completedInterviews: "Abgeschlossene Interviews",
    avgDuration: "Ã˜ Dauer",
    surveyResponses: "Umfrage-Antworten",
    repeatedInterviews: "Wiederholte Interviews",
    // Info card
    completionRate: "Interview-Abschlussquote",
    of: "von",
    studentsCompleted: "Studierenden abgeschlossen",
    // Charts
    dropoffTitle: "Abbruch nach Interview-Schritt",
    dropoffSub: "wo Studierende aussteigen",
    funnelTitle: "Abschluss-Trichter",
    funnelSub: "Studierende pro Schritt",
    weeklyTitle: "WÃ¶chentliche AktivitÃ¤t",
    weeklySub: "Antworten & aktive Nutzer pro Woche",
    // Table headers
    step: "Schritt",
    students: "Studierende",
    reached: "Erreicht",
    week: "Woche",
    responses: "Antworten",
    users: "Nutzer",
    // Chart axis labels
    axisStudentsLeft: "Ausgestiegene Studierende",
    axisInterviewStep: "Interview-Schritt",
    axisStudentsReached: "Erreichte Studierende",
    axisStep: "Schritt",
    axisResponses: "Antworten",
    axisUsers: "Nutzer",
    axisWeek: "Woche",
    // Duration sub
    variance: "Var",
  },
  en: {
    title: "Analytics Dashboard",
    from: "FROM",
    to: "TO",
    apply: "Apply",
    clear: "Clear",
    loading: "Loading analytics\u2026",
    noData: "No data yet",
    showChart: "Show Chart",
    showTable: "Show Table",
    // KPI labels
    totalStudents: "Total Students",
    completedInterviews: "Completed Interviews",
    avgDuration: "Avg Duration",
    surveyResponses: "Survey Responses",
    repeatedInterviews: "Repeated Interviews",
    // Info card
    completionRate: "Interview Completion Rate",
    of: "of",
    studentsCompleted: "students completed",
    // Charts
    dropoffTitle: "Drop-off by Interview Step",
    dropoffSub: "where students leave",
    funnelTitle: "Completion Funnel",
    funnelSub: "students per step",
    weeklyTitle: "Weekly Activity",
    weeklySub: "responses & unique users per week",
    // Table headers
    step: "Step",
    students: "Students",
    reached: "Reached",
    week: "Week",
    responses: "Responses",
    users: "Users",
    // Chart axis labels
    axisStudentsLeft: "Students who left",
    axisInterviewStep: "Interview Step",
    axisStudentsReached: "Students Reached",
    axisStep: "Step",
    axisResponses: "Responses",
    axisUsers: "Users",
    axisWeek: "Week",
    // Duration sub
    variance: "var",
  },
};

export default {
  name: "DashboardTeacher",
  props: {
    lang: {
      type: String,
      default: "de",
    },
  },
  data: function () {
    return {
      isLoading: true,
      error: null,
      stats: {},
      dateFrom: "",
      dateTo: "",
      selectedCourse: "",
      courseList: [],
      showTable: {
        dropoff: false,
        funnel: false,
        weekly: false,
      },
      charts: {
        dropoff: null,
        funnel: null,
        weekly: null,
      },
    };
  },
  computed: {
    completionRate: function () {
      if (!this.stats.total_students) return 0;
      return Math.round(
        (this.stats.total_completed / this.stats.total_students) * 100,
      );
    },
    kpiCards: function () {
      var tr = TRANSLATIONS[this.lang] || TRANSLATIONS["de"];
      return [
        {
          label: tr.totalStudents,
          value: this.stats.total_students,
          color: GREEN,
        },
        {
          label: tr.completedInterviews,
          value: this.stats.total_completed,
          color: GREEN,
        },
        {
          label: tr.avgDuration,
          value: this.stats.avg_duration_minutes + " min",
          sub:
            "\u03C3 " +
            this.stats.std_duration_minutes +
            " min \u00B7 " +
            tr.variance +
            " " +
            this.stats.var_duration_minutes,
          color: GREEN,
        },
        {
          label: tr.surveyResponses,
          value: this.stats.survey_count,
          color: GREEN,
        },
        {
          label: tr.repeatedInterviews,
          value: this.stats.reattempts,
          color: GREEN,
        },
      ];
    },
  },
  mounted: function () {
    this.loadStats();
  },
  watch: {
    lang: function () {
      var self = this;
      this.$nextTick(function () {
        self.renderCharts();
      });
    },
  },
  methods: {
    t: function (key) {
      var tr = TRANSLATIONS[this.lang] || TRANSLATIONS["de"];
      return tr[key] || key;
    },
    logInteraction: function (action, value) {
      var base = window.SRL_BACKEND_URL || "";
      var userid =
        (window.SRL_CONFIG && window.SRL_CONFIG.userId) ||
        new URLSearchParams(window.location.search).get("userid") ||
        localStorage.getItem("srl_userid");
      axios
        .post(base + "/log/interaction", {
          userid: userid,
          client: "web",
          action: action,
          value: value || {},
          timestamp: Math.floor(Date.now() / 1000),
        })
        .catch(function () {
          /* non-critical */
        });
    },
    toggle: function (key) {
      this.showTable[key] = !this.showTable[key];
      this.logInteraction("dashboard_chart_toggled", {
        chart: key,
        show_table: this.showTable[key],
      });
      if (!this.showTable[key]) {
        var self = this;
        this.$nextTick(function () {
          self.renderCharts();
        });
      }
    },
    loadStats: function (fromUserAction) {
      var self = this;
      if (fromUserAction) {
        self.logInteraction("dashboard_filter_applied", {
          date_from: self.dateFrom,
          date_to: self.dateTo,
          course: self.selectedCourse,
        });
      }
      self.isLoading = true;
      var base = window.SRL_BACKEND_URL || "";
      var url = base + "/dashboard/stats";
      var params = [];
      if (self.dateFrom) {
        params.push(
          "date_from=" + Math.floor(new Date(self.dateFrom).getTime() / 1000),
        );
      }
      if (self.dateTo) {
        params.push(
          "date_to=" + Math.floor(new Date(self.dateTo).getTime() / 1000),
        );
      }
      if (self.selectedCourse) {
        params.push("course_id=" + self.selectedCourse);
      }
      if (params.length) {
        url += "?" + params.join("&");
      }
      axios
        .get(url)
        .then(function (res) {
          self.stats = res.data;
          if (self.courseList.length === 0) {
            axios
              .get(base + "/dashboard/courses")
              .then(function (cr) {
                self.courseList = cr.data || [];
              })
              .catch(function () {
                self.courseList = [];
              });
          }
          setTimeout(function () {
            self.renderCharts();
          }, 150);
        })
        .catch(function (e) {
          self.error = "Failed to load: " + e.message;
        })
        .finally(function () {
          self.isLoading = false;
        });
    },
    clearFilter: function () {
      this.dateFrom = "";
      this.dateTo = "";
      this.selectedCourse = "";
      this.logInteraction("dashboard_filter_cleared", {});
      this.loadStats();
    },
    renderCharts: function () {
      this.destroyCharts();
      var tr = TRANSLATIONS[this.lang] || TRANSLATIONS["de"];
      var intTicks = {
        beginAtZero: true,
        stepSize: 1,
        callback: function (v) {
          return Number.isInteger(v) ? v : null;
        },
      };

      // Drop-off
      var dCtx = this.$refs.dropoffChart;
      if (
        dCtx &&
        !this.showTable.dropoff &&
        this.stats.dropoff_distribution &&
        this.stats.dropoff_distribution.length
      ) {
        this.charts.dropoff = new Chart(dCtx, {
          type: "bar",
          data: {
            labels: this.stats.dropoff_distribution.map(function (s) {
              return s.step;
            }),
            datasets: [
              {
                data: this.stats.dropoff_distribution.map(function (s) {
                  return s.count;
                }),
                backgroundColor: GREEN,
                borderRadius: 6,
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            legend: { display: false },
            scales: {
              yAxes: [
                {
                  ticks: intTicks,
                  scaleLabel: {
                    display: true,
                    fontColor: "#9ca3af",
                    fontSize: 11,
                    labelString: tr.axisStudentsLeft,
                  },
                },
              ],
              xAxes: [
                {
                  gridLines: { display: false },
                  scaleLabel: {
                    display: true,
                    fontColor: "#9ca3af",
                    fontSize: 11,
                    labelString: tr.axisInterviewStep,
                  },
                },
              ],
            },
          },
        });
      }

      // Funnel
      var fCtx = this.$refs.funnelChart;
      if (
        fCtx &&
        !this.showTable.funnel &&
        this.stats.completion_funnel &&
        this.stats.completion_funnel.length
      ) {
        this.charts.funnel = new Chart(fCtx, {
          type: "bar",
          data: {
            labels: this.stats.completion_funnel.map(function (f) {
              return f.step;
            }),
            datasets: [
              {
                data: this.stats.completion_funnel.map(function (f) {
                  return f.count;
                }),
                backgroundColor: GREEN,
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            legend: { display: false },
            scales: {
              yAxes: [
                {
                  ticks: intTicks,
                  scaleLabel: {
                    display: true,
                    fontColor: "#9ca3af",
                    fontSize: 11,
                    labelString: tr.axisStudentsReached,
                  },
                },
              ],
              xAxes: [
                {
                  gridLines: { display: false },
                  scaleLabel: {
                    display: true,
                    fontColor: "#9ca3af",
                    fontSize: 11,
                    labelString: tr.axisStep,
                  },
                },
              ],
            },
          },
        });
      }

      // Weekly
      var wCtx = this.$refs.weeklyChart;
      if (
        wCtx &&
        !this.showTable.weekly &&
        this.stats.weekly_activity &&
        this.stats.weekly_activity.length
      ) {
        this.charts.weekly = new Chart(wCtx, {
          type: "line",
          data: {
            labels: this.stats.weekly_activity.map(function (w) {
              return w.week;
            }),
            datasets: [
              {
                label: tr.axisResponses,
                data: this.stats.weekly_activity.map(function (w) {
                  return w.messages;
                }),
                borderColor: GREEN,
                backgroundColor: "rgba(37,99,176,0.08)",
                fill: true,
                tension: 0.4,
              },
              {
                label: tr.axisUsers,
                data: this.stats.weekly_activity.map(function (w) {
                  return w.users;
                }),
                borderColor: GREEN_MID,
                backgroundColor: "rgba(37,99,176,0.04)",
                fill: true,
                tension: 0.4,
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            legend: { position: "bottom" },
            tooltips: {
              mode: "index",
              intersect: false,
            },
            scales: {
              yAxes: [
                {
                  ticks: Object.assign({}, intTicks, { maxTicksLimit: 6 }),
                  scaleLabel: {
                    display: true,
                    fontColor: "#9ca3af",
                    fontSize: 11,
                    labelString: tr.axisResponses + " / " + tr.axisUsers,
                  },
                },
              ],
              xAxes: [
                {
                  scaleLabel: {
                    display: true,
                    fontColor: "#9ca3af",
                    fontSize: 11,
                    labelString: tr.axisWeek,
                  },
                },
              ],
            },
          },
        });
      }
    },
    destroyCharts: function () {
      Object.values(this.charts).forEach(function (c) {
        if (c) c.destroy();
      });
      this.charts = { dropoff: null, funnel: null, weekly: null };
    },
    beforeUnmount: function () {
      this.destroyCharts();
    },
  },
};
</script>

<style scoped>
@import url("https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap");

.td-root {
  font-family: "DM Sans", sans-serif;
  background: #f0f4fa;
  min-height: 100vh;
  padding: 24px 32px;
  color: #1a1d2e;
  overflow-y: auto;
}

.td-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 28px;
  flex-wrap: wrap;
  gap: 16px;
}
.td-header-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.td-badge {
  font-family: "DM Mono", monospace;
  font-size: 0.65rem;
  font-weight: 500;
  letter-spacing: 0.15em;
  color: #2563b0;
  background: #dbeafe;
  padding: 3px 8px;
  border-radius: 4px;
  width: fit-content;
}
.td-title {
  font-size: 1.75rem;
  font-weight: 600;
  margin: 0;
  letter-spacing: -0.02em;
}
.td-header-right {
  display: flex;
  flex-direction: row;
  gap: 16px;
  align-items: flex-end;
  flex-wrap: wrap;
}
.td-filter-group {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}
.td-date-field {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.td-date-field label {
  font-size: 0.6rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  color: #9ca3af;
}
.td-date-field input,
.td-select {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 5px 8px;
  font-size: 0.8rem;
  font-family: "DM Sans", sans-serif;
  background: white;
}
.td-select {
  min-width: 160px;
  max-width: 200px;
}

.td-btn {
  font-family: "DM Sans", sans-serif;
  font-size: 0.8rem;
  font-weight: 500;
  padding: 6px 14px;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  transition: all 0.15s;
}
.td-btn-primary {
  background: #2563b0;
  color: white;
}
.td-btn-primary:hover {
  background: #1a4f9a;
}
.td-btn-ghost {
  background: white;
  color: #374151;
  border: 1px solid #e5e7eb;
}
.td-btn-ghost:hover {
  background: #f9fafb;
}
.td-toggle-btn {
  font-size: 0.72rem;
  padding: 3px 10px;
  border-radius: 99px;
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #2563b0;
  cursor: pointer;
  font-family: "DM Sans", sans-serif;
  white-space: nowrap;
}
.td-toggle-btn:hover {
  background: #dbeafe;
}

.td-loading {
  text-align: center;
  padding: 60px;
  color: #9ca3af;
}
.td-spinner {
  width: 36px;
  height: 36px;
  border: 3px solid #e5e7eb;
  border-top-color: #2563b0;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 16px;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.td-error {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #2563b0;
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 20px;
}

.td-kpi-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  margin-bottom: 24px;
}
.td-kpi {
  background: white;
  border-radius: 10px;
  padding: 16px 18px;
  position: relative;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}
.td-kpi-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: var(--accent);
}
.td-kpi-value {
  font-size: 1.6rem;
  font-weight: 600;
  color: var(--accent);
  line-height: 1;
  margin-bottom: 4px;
  font-family: "DM Mono", monospace;
}
.td-kpi-label {
  font-size: 0.75rem;
  color: #6b7280;
  font-weight: 500;
}
.td-kpi-sub {
  font-size: 0.68rem;
  color: #9ca3af;
  margin-top: 3px;
}

.td-charts-row {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}
.td-chart-card {
  background: white;
  border-radius: 10px;
  padding: 18px 20px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
}
.td-chart-wide {
  flex: 2;
}
.td-chart-narrow {
  flex: 1;
}
.td-chart-header-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}
.td-chart-title {
  font-size: 0.9rem;
  font-weight: 600;
  display: block;
}
.td-chart-sub {
  font-size: 0.72rem;
  color: #9ca3af;
}
.td-canvas-wrap {
  position: relative;
  height: 200px;
}
.td-canvas-wrap canvas {
  height: 200px !important;
}
.td-weekly-scroll .td-canvas-wrap {
  height: 320px;
}
.td-weekly-scroll .td-canvas-wrap canvas {
  height: 320px !important;
}
.td-empty {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: #d1d5db;
  font-size: 0.82rem;
  white-space: nowrap;
}

.td-info-card {
  justify-content: center;
}
.td-big-stat {
  font-size: 2.2rem;
  font-weight: 700;
  font-family: "DM Mono", monospace;
  margin: 8px 0 4px;
  color: #2563b0;
}
.td-progress-bar-wrap {
  background: #dbeafe;
  border-radius: 99px;
  height: 6px;
  margin-top: 10px;
  overflow: hidden;
}
.td-progress-bar {
  background: #2563b0;
  height: 6px;
  border-radius: 99px;
  transition: width 0.6s ease;
}

.td-table-mt {
  margin-top: 4px;
}
.td-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.78rem;
}
.td-table th {
  padding: 5px 8px;
  text-align: left;
  color: #9ca3af;
  font-weight: 600;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid #f3f4f6;
}
.td-table td {
  padding: 6px 8px;
  border-bottom: 1px solid #f9fafb;
  color: #374151;
}
.td-table tr:last-child td {
  border-bottom: none;
}
.td-empty-row {
  color: #d1d5db;
  text-align: center;
  padding: 12px;
}

@media print {
  .td-header-right {
    display: none;
  }
  .td-root {
    background: white;
    padding: 16px;
  }
  .td-chart-card,
  .td-kpi {
    box-shadow: none;
    border: 1px solid #e5e7eb;
  }
}
/* ── Mobile responsive ─────────────────────────────────────── */
@media (max-width: 480px) {
  .td-kpis-row {
    flex-wrap: wrap !important;
  }
  .td-kpi {
    min-width: calc(50% - 8px) !important;
    flex: 1 1 calc(50% - 8px) !important;
  }
}
@media (max-width: 768px) {
  .td-root {
    padding: 12px 8px;
  }
  .td-kpi {
    min-width: 100% !important;
  }
  .td-chart-card {
    padding: 12px 8px;
  }
  .td-table {
    font-size: 0.72rem;
  }
  .td-table th,
  .td-table td {
    padding: 4px 4px;
  }
}
@media (max-width: 480px) {
  .td-header-right {
    display: none;
  }
}
/* ── Mobile KPI grid fix ───────────────────────────────────── */
@media (max-width: 480px) {
  .td-kpi-grid {
    display: grid !important;
    grid-template-columns: 1fr 1fr !important;
    gap: 8px !important;
  }
  .td-kpi {
    min-width: unset !important;
    width: 100% !important;
  }
  .td-root {
    padding: 8px 6px !important;
  }
}
/* ── Mobile chart layout — stack vertically, no horizontal scroll ── */
@media (max-width: 768px) {
  .td-root {
    overflow-x: hidden;
  }

  /* Stack all chart rows vertically */
  .td-charts-row {
    flex-direction: column;
    gap: 12px;
  }

  /* All cards take full width */
  .td-chart-card,
  .td-chart-wide,
  .td-chart-narrow {
    flex: unset !important;
    width: 100% !important;
  }

  /* KPI grid: 2 columns */
  .td-kpi-grid {
    grid-template-columns: 1fr 1fr !important;
    gap: 8px !important;
  }

  /* Bar charts — fixed height, no scroll needed */
  .td-canvas-wrap {
    height: 220px;
    overflow: hidden;
  }

  .td-canvas-wrap canvas {
    height: 220px !important;
  }
}

/* ── Weekly line chart — horizontal scroll on very small screens ── */
@media (max-width: 480px) {
  .td-weekly-scroll {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }

  .td-weekly-scroll .td-canvas-wrap {
    min-width: 480px;
    overflow: visible;
  }

  .td-weekly-scroll .td-canvas-wrap canvas {
    min-width: 480px;
  }
}
</style>



