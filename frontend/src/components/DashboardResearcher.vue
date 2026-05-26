<template>
  <div class="rd-root">
    <!-- Header -->
    <div class="rd-header">
      <div class="rd-header-left">
        <span class="rd-badge">RESEARCH</span>
        <h1 class="rd-title">Analytics Dashboard</h1>
      </div>
      <div class="rd-header-right">
        <div class="rd-filter-group">
          <div class="rd-date-field">
            <label>COURSE</label>
            <select
              v-model="selectedCourse"
              class="rd-select"
              @change="loadStats"
            >
              <option value="">All Courses</option>
              <option v-for="c in courseList" :key="c.id" :value="c.id">
                {{ c.name }}
              </option>
            </select>
          </div>
          <div class="rd-date-field">
            <label>FROM</label>
            <input type="date" v-model="dateFrom" />
          </div>
          <div class="rd-date-field">
            <label>TO</label>
            <input type="date" v-model="dateTo" />
          </div>
          <button class="rd-btn rd-btn-primary" @click="loadStats">
            Apply
          </button>
          <button class="rd-btn rd-btn-ghost" @click="clearFilter">
            Clear
          </button>
        </div>
        <div class="rd-download-wrap">
          <button
            class="rd-btn rd-btn-primary"
            @click="showDownload = !showDownload"
          >
            &#8595; Download
          </button>
          <div v-if="showDownload" class="rd-dropdown">
            <button
              @click="
                downloadCSV();
                showDownload = false;
              "
            >
              CSV
            </button>
            <button
              @click="
                downloadExcel();
                showDownload = false;
              "
            >
              Excel
            </button>
            <button
              @click="
                downloadPDF();
                showDownload = false;
              "
            >
              PDF
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="isLoading" class="rd-loading">
      <div class="rd-spinner"></div>
      <p>Loading analytics&#8230;</p>
    </div>
    <div v-else-if="error" class="rd-error">{{ error }}</div>

    <div v-else id="dashboard-content">
      <!-- KPI Grid -->
      <div class="rd-kpi-grid">
        <div
          class="rd-kpi"
          v-for="kpi in kpiCards"
          :key="kpi.label"
          :style="`--accent: ${kpi.color}`"
        >
          <div class="rd-kpi-value">{{ kpi.value }}</div>
          <div class="rd-kpi-label">{{ kpi.label }}</div>
          <div class="rd-kpi-sub" v-if="kpi.sub">{{ kpi.sub }}</div>
          <div class="rd-kpi-bar"></div>
        </div>
      </div>

      <!-- Course Share — only when no course filter -->
      <div v-if="!selectedCourse" class="rd-charts-row">
        <div class="rd-chart-card" style="flex: 1">
          <div class="rd-chart-header">
            <span class="rd-chart-title">Course Share</span>
            <span class="rd-chart-sub"
              >student distribution across courses &middot; populated from LTI
              <code>context_id</code> / <code>context_title</code></span
            >
          </div>
          <div class="rd-canvas-wrap" v-if="courseList && courseList.length">
            <canvas ref="courseChart"></canvas>
          </div>
          <div v-else class="rd-empty-explain">
            No course data yet.<br />
            <span
              >Will populate once students launch via LTI from Moodle or
              ILIAS.<br />
              Source: <code>context_id</code> and <code>context_title</code> LTI
              launch parameters &rarr; stored in <code>users</code> table.</span
            >
          </div>
        </div>
      </div>

      <!-- Charts Row 1: Drop-off + Language -->
      <div class="rd-charts-row">
        <div class="rd-chart-card rd-chart-wide">
          <div class="rd-chart-header rd-chart-header-row">
            <div>
              <span class="rd-chart-title">Drop-off by Interview Step</span>
              <span class="rd-chart-sub">where students leave</span>
            </div>
            <button class="rd-toggle-btn" @click="toggle('dropoff')">
              {{ showTable.dropoff ? "Show Chart" : "Show Table" }}
            </button>
          </div>
          <div class="rd-canvas-wrap" v-if="!showTable.dropoff">
            <canvas ref="dropoffChart"></canvas>
            <div
              v-if="
                !stats.dropoff_distribution ||
                !stats.dropoff_distribution.length
              "
              class="rd-empty"
            >
              No data yet
            </div>
          </div>
          <table v-else class="rd-table rd-table-mt">
            <thead>
              <tr>
                <th>Step</th>
                <th>Students</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-if="
                  !stats.dropoff_distribution ||
                  !stats.dropoff_distribution.length
                "
              >
                <td colspan="2" class="rd-empty-row">No data yet</td>
              </tr>
              <tr v-for="r in stats.dropoff_distribution" :key="r.step">
                <td>{{ r.step }}</td>
                <td>{{ r.count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="rd-chart-card rd-chart-narrow">
          <div class="rd-chart-header rd-chart-header-row">
            <div>
              <span class="rd-chart-title">Language Split</span>
              <span class="rd-chart-sub">DE vs EN</span>
            </div>
            <button class="rd-toggle-btn" @click="toggle('language')">
              {{ showTable.language ? "Show Chart" : "Show Table" }}
            </button>
          </div>
          <div class="rd-canvas-wrap" v-if="!showTable.language">
            <canvas ref="languageChart"></canvas>
            <div
              v-if="
                !stats.language_distribution ||
                !stats.language_distribution.length
              "
              class="rd-empty"
            >
              No data yet
            </div>
          </div>
          <table v-else class="rd-table rd-table-mt">
            <thead>
              <tr>
                <th>Language</th>
                <th>Students</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-if="
                  !stats.language_distribution ||
                  !stats.language_distribution.length
                "
              >
                <td colspan="2" class="rd-empty-row">No data yet</td>
              </tr>
              <tr v-for="r in stats.language_distribution" :key="r.language">
                <td>{{ r.language }}</td>
                <td>{{ r.count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Charts Row 2: Funnel + Turns + Response Time -->
      <div class="rd-charts-row">
        <div class="rd-chart-card rd-chart-narrow">
          <div class="rd-chart-header rd-chart-header-row">
            <div>
              <span class="rd-chart-title">Completion Funnel</span>
              <span class="rd-chart-sub">students per step</span>
            </div>
            <button class="rd-toggle-btn" @click="toggle('funnel')">
              {{ showTable.funnel ? "Show Chart" : "Show Table" }}
            </button>
          </div>
          <div class="rd-canvas-wrap" v-if="!showTable.funnel">
            <canvas ref="funnelChart"></canvas>
            <div
              v-if="!stats.completion_funnel || !stats.completion_funnel.length"
              class="rd-empty"
            >
              No data yet
            </div>
          </div>
          <table v-else class="rd-table rd-table-mt">
            <thead>
              <tr>
                <th>Step</th>
                <th>Reached</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-if="
                  !stats.completion_funnel || !stats.completion_funnel.length
                "
              >
                <td colspan="2" class="rd-empty-row">No data yet</td>
              </tr>
              <tr v-for="r in stats.completion_funnel" :key="r.step">
                <td>{{ r.step }}</td>
                <td>{{ r.count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="rd-chart-card rd-chart-narrow">
          <div class="rd-chart-header rd-chart-header-row">
            <div>
              <span class="rd-chart-title">Avg Turns</span>
              <span class="rd-chart-sub">completed vs incomplete</span>
            </div>
            <button class="rd-toggle-btn" @click="toggle('turns')">
              {{ showTable.turns ? "Show Chart" : "Show Table" }}
            </button>
          </div>
          <div class="rd-canvas-wrap" v-if="!showTable.turns">
            <canvas ref="turnsChart"></canvas>
          </div>
          <table v-else class="rd-table rd-table-mt">
            <thead>
              <tr>
                <th>Group</th>
                <th>Avg Turns</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Completed</td>
                <td>{{ (+stats.avg_turns_completed || 0).toFixed(2) }}</td>
              </tr>
              <tr>
                <td>Incomplete</td>
                <td>{{ (+stats.avg_turns_incomplete || 0).toFixed(2) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="rd-chart-card rd-chart-narrow">
          <div class="rd-chart-header rd-chart-header-row">
            <div>
              <span class="rd-chart-title">LLM Response Time</span>
              <span class="rd-chart-sub">seconds by step</span>
            </div>
            <button class="rd-toggle-btn" @click="toggle('responseTime')">
              {{ showTable.responseTime ? "Show Chart" : "Show Table" }}
            </button>
          </div>
          <div class="rd-canvas-wrap" v-if="!showTable.responseTime">
            <canvas ref="responseTimeChart"></canvas>
            <div
              v-if="
                !stats.response_time_by_step ||
                !stats.response_time_by_step.length
              "
              class="rd-empty"
            >
              No data yet
            </div>
          </div>
          <table v-else class="rd-table rd-table-mt">
            <thead>
              <tr>
                <th>Step</th>
                <th>Avg (s)</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-if="
                  !stats.response_time_by_step ||
                  !stats.response_time_by_step.length
                "
              >
                <td colspan="2" class="rd-empty-row">No data yet</td>
              </tr>
              <tr v-for="r in stats.response_time_by_step" :key="r.step">
                <td>{{ r.step }}</td>
                <td>{{ (+r.avg_seconds || 0).toFixed(2) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Charts Row 3: Weekly + Strategy -->
      <div class="rd-charts-row">
        <div class="rd-chart-card rd-chart-wide">
          <div class="rd-chart-header rd-chart-header-row">
            <div>
              <span class="rd-chart-title">Weekly Activity</span>
              <span class="rd-chart-sub"
                >responses &amp; unique users per week</span
              >
            </div>
            <button class="rd-toggle-btn" @click="toggle('weekly')">
              {{ showTable.weekly ? "Show Chart" : "Show Table" }}
            </button>
          </div>
          <div class="rd-canvas-wrap" v-if="!showTable.weekly">
            <canvas ref="weeklyChart"></canvas>
            <div
              v-if="!stats.weekly_activity || !stats.weekly_activity.length"
              class="rd-empty"
            >
              No data yet
            </div>
          </div>
          <table v-else class="rd-table rd-table-mt">
            <thead>
              <tr>
                <th>Week</th>
                <th>Responses</th>
                <th>Users</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-if="!stats.weekly_activity || !stats.weekly_activity.length"
              >
                <td colspan="3" class="rd-empty-row">No data yet</td>
              </tr>
              <tr v-for="r in stats.weekly_activity" :key="r.week">
                <td>{{ r.week }}</td>
                <td>{{ r.messages }}</td>
                <td>{{ r.users }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="rd-chart-card rd-chart-narrow">
          <div class="rd-chart-header rd-chart-header-row">
            <div>
              <span class="rd-chart-title">Strategy Distribution</span>
              <span class="rd-chart-sub">absolute counts &middot; RAG detected</span>
            </div>
            <button class="rd-toggle-btn" @click="toggle('strategy')">
              {{ showTable.strategy ? "Show Chart" : "Show Table" }}
            </button>
          </div>
          <div class="rd-canvas-wrap" v-if="!showTable.strategy">
            <canvas ref="strategyChart"></canvas>
            <div
              v-if="
                !stats.strategy_distribution ||
                !stats.strategy_distribution.length
              "
              class="rd-empty"
            >
              No data yet
            </div>
          </div>
          <table v-else class="rd-table rd-table-mt">
            <thead>
              <tr>
                <th>Strategy</th>
                <th>Count</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-if="
                  !stats.strategy_distribution ||
                  !stats.strategy_distribution.length
                "
              >
                <td colspan="2" class="rd-empty-row">No data yet</td>
              </tr>
              <tr v-for="r in stats.strategy_distribution" :key="r.strategy">
                <td>{{ r.name || r.strategy }}</td>
                <td>{{ r.count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Info Row: Completion Rate + Survey Rate + Last Activity + Response Gap -->
      <div class="rd-charts-row">
        <div class="rd-chart-card rd-chart-narrow rd-info-card">
          <div class="rd-chart-title">Interview Completion Rate</div>
          <div class="rd-big-stat">{{ completionRate }}%</div>
          <div class="rd-chart-sub">
            {{ stats.total_completed }} of {{ stats.total_students }} students
            completed
          </div>
          <div class="rd-progress-bar-wrap">
            <div
              class="rd-progress-bar"
              :style="`width: ${completionRate}%`"
            ></div>
          </div>
        </div>
        <div class="rd-chart-card rd-chart-narrow rd-info-card">
          <div class="rd-chart-title">Survey Completion Rate</div>
          <div class="rd-big-stat">{{ surveyCompletionRate }}%</div>
          <div class="rd-chart-sub">
            {{ stats.survey_count }} of {{ stats.total_completed }} who finished
            also submitted survey
          </div>
          <div class="rd-progress-bar-wrap">
            <div
              class="rd-progress-bar"
              :style="`width: ${surveyCompletionRate}%`"
            ></div>
          </div>
        </div>
        <div class="rd-chart-card rd-chart-narrow rd-info-card">
          <div class="rd-chart-title">Last Activity</div>
          <div class="rd-big-stat rd-big-stat-sm">
            {{ stats.last_activity || "&mdash;" }}
          </div>
          <div class="rd-chart-sub">
            most recent interview started<br /><code
              >interview_answer.message_time</code
            >
          </div>
        </div>
        <div class="rd-chart-card rd-chart-narrow rd-info-card">
          <div class="rd-chart-title">Avg Turn Duration</div>
          <div class="rd-big-stat">
            {{
              stats.avg_response_gap_seconds != null
                ? (+stats.avg_response_gap_seconds).toFixed(2) + "s"
                : "&mdash;"
            }}
          </div>
          <div class="rd-chart-sub">
            avg seconds per turn &middot; includes LLM response time + student reading
            &amp; typing time
          </div>
        </div>
      </div>

      <!-- Survey -->
      <div class="rd-survey-card">
        <div class="rd-chart-header-row" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
          <div class="rd-table-title" style="margin-bottom:0;">
            Self-Report Survey Results
            <span class="rd-badge-sm">{{ stats.survey_count }} responses</span>
          </div>
          <button
            v-if="stats.survey_avg_scores && stats.survey_avg_scores.length"
            class="rd-toggle-btn"
            @click="toggle('survey')"
          >
            {{ showTable.survey ? "Show Chart" : "Show Table" }}
          </button>
        </div>
        <p
          v-if="!stats.survey_count"
          style="color: #d1d5db; font-size: 0.82rem"
        >
          No survey responses yet.
        </p>
        <template v-else-if="stats.survey_avg_scores && stats.survey_avg_scores.length">
          <!-- Chart view (default) -->
          <div v-if="!showTable.survey" class="rd-survey-chart-outer">
            <!-- Fixed axis header -->
            <div class="rd-survey-axis-header">
              <div class="rd-survey-axis-label">Avg Score</div>
              <canvas ref="surveyAxisChart" height="36"></canvas>
            </div>
            <!-- Scrollable bars -->
            <div class="rd-survey-chart-scroll">
              <div :style="{ height: (stats.survey_avg_scores ? stats.survey_avg_scores.length * 36 + 20 : 400) + 'px', position: 'relative' }">
                <canvas ref="surveyChart"></canvas>
              </div>
            </div>
          </div>
          <!-- Table view -->
          <table v-else class="rd-table rd-table-mt">
            <thead>
              <tr>
                <th>Question</th>
                <th>Avg Score</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in stats.survey_avg_scores" :key="r.question">
                <td :title="r.question">{{ surveyQuestionLabel(r.question) }}</td>
                <td>{{ Number(r.avg).toFixed(2) }}</td>
              </tr>
            </tbody>
          </table>
        </template>
      </div>
    </div>
  </div>
</template>

<script>
import axios from "axios";
import Chart from "chart.js";

const BLUE = "#2563b0";
const BLUE_MID = "rgba(37,99,176,0.5)";
const BLUE_PIE = [
  "#2563b0",
  "rgba(37,99,176,0.7)",
  "rgba(37,99,176,0.45)",
  "rgba(37,99,176,0.2)",
];
const LABEL_STYLE = { display: true, fontColor: "#9ca3af", fontSize: 11 };

export default {
  name: "DashboardResearcher",
  data() {
    return {
      isLoading: true,
      error: null,
      stats: {},
      dateFrom: "",
      dateTo: "",
      selectedCourse: "",
      courseList: [],
      showDownload: false,
      showTable: {
        dropoff: false,
        language: false,
        funnel: false,
        turns: false,
        responseTime: false,
        weekly: false,
        strategy: false,
        survey: false,
      },
      charts: {
        dropoff: null,
        strategy: null,
        language: null,
        turns: null,
        funnel: null,
        weekly: null,
        responseTime: null,
        course: null,
        survey: null,
        surveyAxis: null,
      },
    };
  },
  computed: {
    completionRate() {
      if (!this.stats.total_students) return 0;
      return Math.round(
        (this.stats.total_completed / this.stats.total_students) * 100,
      );
    },
    surveyCompletionRate() {
      if (!this.stats.total_completed) return 0;
      return Math.round(
        ((this.stats.survey_count || 0) / this.stats.total_completed) * 100,
      );
    },
    kpiCards() {
      return [
        {
          label: "Total Students",
          value: this.stats.total_students,
          color: "#2563b0",
        },
        {
          label: "Completed Interviews",
          value: this.stats.total_completed,
          color: "#2563b0",
        },
        {
          label: "Avg Duration",
          value: `${(+this.stats.avg_duration_minutes || 0).toFixed(2)} min`,
          sub: `\u03c3 ${(+this.stats.std_duration_minutes || 0).toFixed(2)} min \u00b7 var ${(+this.stats.var_duration_minutes || 0).toFixed(2)}`,
          color: "#2563b0",
        },
        {
          label: "Avg LLM Response",
          value: `${(+this.stats.avg_response_time_seconds || 0).toFixed(2)}s`,
          color: "#2563b0",
        },
        {
          label: "Survey Responses",
          value: this.stats.survey_count,
          color: "#2563b0",
        },
        {
          label: "Repeated Interviews",
          value: this.stats.reattempts,
          color: "#2563b0",
        },
        {
          label: "Avg Turns (Done)",
          value: (+this.stats.avg_turns_completed || 0).toFixed(2),
          color: "#2563b0",
        },
        {
          label: "Avg Turns (Drop)",
          value: (+this.stats.avg_turns_incomplete || 0).toFixed(2),
          color: "#2563b0",
        },
        {
          label: "Avg Responses",
          value: (+this.stats.avg_messages_per_interview || 0).toFixed(2),
          color: "#2563b0",
        },
        {
          label: "Total Responses",
          value: this.stats.total_messages,
          color: "#2563b0",
        },
      ];
    },
  },
  async mounted() {
    await this.loadStats();
  },
  methods: {
    surveyQuestionLabel(id) {
      const map = {
        "oase_1": "I am confident that I will be able to master the content and assignments in this class.",
        "oase_2": "I am confident in my ability to successfully persist in this class, even if I find the content difficult.",
        "oase_3": "I am confident I can put in the effort required to get a high grade in this class.",
        "oase_4": "I am confident that I can accurately work out what the task is requiring me to do.",
        "oim_1": "I always find aspects of the content that arouse my curiosity.",
        "oim_2": "I love learning new things in this class.",
        "oim_3": "I find studying for this class enjoyable.",
        "oim_4": "I find it very satisfying when I learn new material in this course.",
        "oim_5": "I get a sense of achievement when I learn new skills or information.",
        "oem_1": "I want to do well in this course so I can show off to my friends and family.",
        "oem_2": "I want to do well because of others real or perceived expectations of me.",
        "oem_3": "I want to get a better grade than others in my class.",
        "onae_1": "I feel so helpless that I cannot dedicate all my effort to my studies.",
        "onae_2": "I consider dropping out because I feel overwhelmed by my studies.",
        "onae_3": "While studying, I want to distract myself to lower my anxiety level.",
        "onae_4": "I get so anxious that I don't even want to start studying.",
        "onae_5": "When I have to study, I start to feel bad.",
        "ptm_1": "I set short-term (daily or weekly) goals.",
        "ptm_2": "I set realistic deadlines for learning.",
        "ptm_3": "I break larger goals into smaller actionable goals.",
        "ptm_4": "I make a list of detailed actions that I need to complete.",
        "ptm_5": "I plan out my schedule each week so I have the appropriate amount of time available for study.",
        "mc_1": "I think about what learning strategies have worked for me in the past when doing similar assignments/types of study.",
        "mc_2": "I spend time trying to interpret the task to ensure I understand accurately what I need to do.",
        "mc_3": "I usually self-assess my performance once I finish.",
        "mc_4": "I look over past feedback I have received and check that I have made improvements in my current learning.",
        "mc_5": "I think about how I might improve my work by evaluating it against the marking criteria provided by the teacher.",
        "se_1": "I am able to study for my course without distraction.",
        "se_2": "I have access to a quiet and distraction-free place to study.",
        "se_3": "I know where I can study most efficiently for this course.",
        "oer_1": "I work hard in my study, even when there are more interesting things to do.",
        "oer_2": "When my study gets difficult, I remain committed to reaching my study goals.",
        "oer_3": "When my mind begins to wander during a learning session for this course, I make a special effort to keep concentrating.",
        "oer_4": "No matter how I am feeling, I persevere with my study.",
        "oss_1": "I try to help other students when they ask a question I can answer.",
        "oss_2": "I ask for help from knowledgeable others through channels when I am not sure what to do in my class.",
        "oss_3": "I ask the teacher and/or my peers to clarify information in my course.",
        "oss_4": "When I have difficulties with my class, I seek assistance from others through means (discussion boards, social media, email, instant messaging etc.).",
        "oss_5": "I use email, discussion boards, social media, etc., to connect with the teacher and other students when I need help.",
        "ots_1": "When studying, I create my own examples of the content to make it more meaningful.",
        "ots_2": "When studying, I organise my thoughts by making summaries of what I am learning.",
        "ots_3": "When studying, I try and relate the content to what I already know.",
        "ots_4": "When learning the content, I try and develop my own ideas about it.",
        "ots_5": "I try and improve my understanding by doing additional work beyond the core content (e.g., doing extra problem-solving activities or extra readings).",
        "demo_age": "Age group",
        "demo_years_education": "Years in postsecondary education",
        "demo_course_importance": "Course importance for career",
        "demo_course_confidence": "Confidence in course success",
      };
      return map[id] || id;
    },

    toggle(key) {
      this.showTable[key] = !this.showTable[key];
      if (!this.showTable[key]) this.$nextTick(() => this.renderCharts());
    },

    async loadStats() {
      this.isLoading = true;
      this.showDownload = false;
      try {
        const base = window.SRL_BACKEND_URL || "";
        let url = `${base}/dashboard/stats`;
        const params = [];
        if (this.dateFrom)
          params.push(
            `date_from=${Math.floor(new Date(this.dateFrom).getTime() / 1000)}`,
          );
        if (this.dateTo)
          params.push(
            `date_to=${Math.floor(new Date(this.dateTo).getTime() / 1000)}`,
          );
        if (this.selectedCourse)
          params.push(`course_id=${this.selectedCourse}`);
        if (params.length) url += "?" + params.join("&");
        const res = await axios.get(url);
        this.stats = res.data;

        if (this.courseList.length === 0) {
          try {
            const courseRes = await axios.get(`${base}/dashboard/courses`);
            this.courseList = courseRes.data || [];
          } catch (e) {
            this.courseList = [];
          }
        }

        setTimeout(() => this.renderCharts(), 150);
      } catch (e) {
        this.error = "Failed to load: " + e.message;
      } finally {
        this.isLoading = false;
      }
    },

    clearFilter() {
      this.dateFrom = "";
      this.dateTo = "";
      this.selectedCourse = "";
      this.loadStats();
    },

    renderCharts() {
      this.destroyCharts();
      const intTicks = {
        beginAtZero: true,
        stepSize: 1,
        callback: (v) => (Number.isInteger(v) ? v : null),
      };
      const noGrid = { gridLines: { display: false } };
      const opts = (extra) => ({
        responsive: true,
        maintainAspectRatio: false,
        legend: { display: false },
        ...extra,
      });

      // Course share
      const cCtx = this.$refs.courseChart;
      if (cCtx && !this.selectedCourse && this.courseList.length) {
        const sorted = [...this.courseList]
          .sort((a, b) => b.students - a.students)
          .slice(0, 20);
        this.charts.course = new Chart(cCtx, {
          type: "bar",
          data: {
            labels: sorted.map((c) => c.name),
            datasets: [
              {
                data: sorted.map((c) => c.students),
                backgroundColor: BLUE,
                borderRadius: 4,
              },
            ],
          },
          options: opts({
            scales: {
              yAxes: [
                {
                  ticks: intTicks,
                  scaleLabel: { ...LABEL_STYLE, labelString: "Students" },
                },
              ],
              xAxes: [
                {
                  ...noGrid,
                  scaleLabel: { ...LABEL_STYLE, labelString: "Course" },
                },
              ],
            },
          }),
        });
      }

      // Drop-off
      const dCtx = this.$refs.dropoffChart;
      if (
        dCtx &&
        !this.showTable.dropoff &&
        this.stats.dropoff_distribution &&
        this.stats.dropoff_distribution.length
      ) {
        this.charts.dropoff = new Chart(dCtx, {
          type: "bar",
          data: {
            labels: this.stats.dropoff_distribution.map((s) => s.step),
            datasets: [
              {
                data: this.stats.dropoff_distribution.map((s) => s.count),
                backgroundColor: BLUE,
                borderRadius: 6,
              },
            ],
          },
          options: opts({
            scales: {
              yAxes: [
                {
                  ticks: intTicks,
                  scaleLabel: {
                    ...LABEL_STYLE,
                    labelString: "Students who left",
                  },
                },
              ],
              xAxes: [
                {
                  ...noGrid,
                  scaleLabel: { ...LABEL_STYLE, labelString: "Interview Step" },
                },
              ],
            },
          }),
        });
      }

      // Language
      const lCtx = this.$refs.languageChart;
      if (
        lCtx &&
        !this.showTable.language &&
        this.stats.language_distribution &&
        this.stats.language_distribution.length
      ) {
        this.charts.language = new Chart(lCtx, {
          type: "doughnut",
          data: {
            labels: this.stats.language_distribution.map((l) => l.language),
            datasets: [
              {
                data: this.stats.language_distribution.map((l) => l.count),
                backgroundColor: BLUE_PIE,
                borderWidth: 3,
                borderColor: "#fff",
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            legend: { position: "bottom" },
          },
        });
      }

      // Funnel
      const fCtx = this.$refs.funnelChart;
      if (
        fCtx &&
        !this.showTable.funnel &&
        this.stats.completion_funnel &&
        this.stats.completion_funnel.length
      ) {
        this.charts.funnel = new Chart(fCtx, {
          type: "bar",
          data: {
            labels: this.stats.completion_funnel.map((f) => f.step),
            datasets: [
              {
                data: this.stats.completion_funnel.map((f) => f.count),
                backgroundColor: BLUE,
              },
            ],
          },
          options: opts({
            scales: {
              yAxes: [
                {
                  ticks: intTicks,
                  scaleLabel: {
                    ...LABEL_STYLE,
                    labelString: "Students Reached",
                  },
                },
              ],
              xAxes: [
                {
                  ...noGrid,
                  scaleLabel: { ...LABEL_STYLE, labelString: "Step" },
                },
              ],
            },
          }),
        });
      }

      // Turns
      const tCtx = this.$refs.turnsChart;
      if (tCtx && !this.showTable.turns) {
        this.charts.turns = new Chart(tCtx, {
          type: "bar",
          data: {
            labels: ["Completed", "Incomplete"],
            datasets: [
              {
                data: [
                  this.stats.avg_turns_completed,
                  this.stats.avg_turns_incomplete,
                ],
                backgroundColor: [BLUE, BLUE_MID],
              },
            ],
          },
          options: opts({
            scales: {
              yAxes: [
                {
                  ticks: intTicks,
                  scaleLabel: { ...LABEL_STYLE, labelString: "Avg Turns" },
                },
              ],
              xAxes: [
                {
                  ...noGrid,
                  scaleLabel: {
                    ...LABEL_STYLE,
                    labelString: "Interview Outcome",
                  },
                },
              ],
            },
          }),
        });
      }

      // Response time
      const rCtx = this.$refs.responseTimeChart;
      if (
        rCtx &&
        !this.showTable.responseTime &&
        this.stats.response_time_by_step &&
        this.stats.response_time_by_step.length
      ) {
        this.charts.responseTime = new Chart(rCtx, {
          type: "bar",
          data: {
            labels: this.stats.response_time_by_step.map((r) => r.step),
            datasets: [
              {
                data: this.stats.response_time_by_step.map(
                  (r) => r.avg_seconds,
                ),
                backgroundColor: BLUE,
              },
            ],
          },
          options: opts({
            scales: {
              yAxes: [
                {
                  ticks: { beginAtZero: true },
                  scaleLabel: { ...LABEL_STYLE, labelString: "Seconds" },
                },
              ],
              xAxes: [
                {
                  ...noGrid,
                  scaleLabel: { ...LABEL_STYLE, labelString: "Interview Step" },
                },
              ],
            },
          }),
        });
      }

      // Weekly
      const wCtx = this.$refs.weeklyChart;
      if (
        wCtx &&
        !this.showTable.weekly &&
        this.stats.weekly_activity &&
        this.stats.weekly_activity.length
      ) {
        this.charts.weekly = new Chart(wCtx, {
          type: "line",
          data: {
            labels: this.stats.weekly_activity.map((w) => w.week),
            datasets: [
              {
                label: "Responses",
                data: this.stats.weekly_activity.map((w) => w.messages),
                borderColor: BLUE,
                backgroundColor: "rgba(37,99,176,0.08)",
                fill: true,
                tension: 0.4,
                yAxisID: "y-responses",
              },
              {
                label: "Users",
                data: this.stats.weekly_activity.map((w) => w.users),
                borderColor: BLUE_MID,
                backgroundColor: "rgba(37,99,176,0.04)",
                fill: true,
                tension: 0.4,
                yAxisID: "y-users",
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            legend: { position: "bottom" },
            scales: {
              yAxes: [
                {
                  id: "y-responses",
                  position: "left",
                  ticks: intTicks,
                  scaleLabel: { ...LABEL_STYLE, labelString: "Responses" },
                },
                {
                  id: "y-users",
                  position: "right",
                  ticks: intTicks,
                  gridLines: { drawOnChartArea: false },
                  scaleLabel: { ...LABEL_STYLE, labelString: "Users" },
                },
              ],
              xAxes: [{ scaleLabel: { ...LABEL_STYLE, labelString: "Week" } }],
            },
          },
        });
      }

      // Strategy — show names not codes
      const sCtx = this.$refs.strategyChart;
      if (
        sCtx &&
        !this.showTable.strategy &&
        this.stats.strategy_distribution &&
        this.stats.strategy_distribution.length
      ) {
        this.charts.strategy = new Chart(sCtx, {
          type: "horizontalBar",
          data: {
            labels: this.stats.strategy_distribution.map(
              (s) => s.name || s.strategy,
            ),
            datasets: [
              {
                data: this.stats.strategy_distribution.map((s) => s.count),
                backgroundColor: BLUE,
              },
            ],
          },
          options: opts({
            scales: {
              xAxes: [
                {
                  ticks: intTicks,
                  scaleLabel: {
                    ...LABEL_STYLE,
                    labelString: "Number of Students",
                  },
                },
              ],
              yAxes: [{ scaleLabel: { display: false } }],
            },
          }),
        });
      }

      // Survey avg scores — fixed axis chart + scrollable bars chart
      const svCtx = this.$refs.surveyChart;
      const svAxisCtx = this.$refs.surveyAxisChart;
      if (
        svCtx &&
        this.stats.survey_avg_scores &&
        this.stats.survey_avg_scores.length
      ) {
        const LABEL_WIDTH = 320;
        const truncate = (s, n) =>
          s.length > n ? s.slice(0, n - 1) + "\u2026" : s;
        const labels = this.stats.survey_avg_scores.map((r) =>
          truncate(this.surveyQuestionLabel(r.question), 52)
        );
        const values = this.stats.survey_avg_scores.map((r) =>
          parseFloat(r.avg)
        );

        const sharedXAxis = {
          position: "top",
          ticks: { beginAtZero: true, max: 5, fontSize: 11, fontColor: "#6b7280" },
          gridLines: { color: "#f3f4f6" },
        };

        // Axis-only chart (no data, just draws the x axis)
        if (svAxisCtx && !this.showTable.survey) {
          this.charts.surveyAxis = new Chart(svAxisCtx, {
            type: "horizontalBar",
            data: {
              labels: [""],
              datasets: [{ data: [null], backgroundColor: "transparent" }],
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              legend: { display: false },
              animation: { duration: 0 },
              scales: {
                xAxes: [{ ...sharedXAxis }],
                yAxes: [
                  {
                    ticks: { fontSize: 12 },
                    gridLines: { display: false },
                    afterFit(s) { s.width = LABEL_WIDTH; },
                  },
                ],
              },
              tooltips: { enabled: false },
            },
          });
        }

        // Bars-only chart (no x axis shown, scrolls)
        if (svCtx && !this.showTable.survey) {
          this.charts.survey = new Chart(svCtx, {
            type: "horizontalBar",
            data: {
              labels,
              datasets: [
                {
                  data: values,
                  backgroundColor: BLUE,
                  borderWidth: 0,
                  barThickness: 18,
                },
              ],
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              legend: { display: false },
              scales: {
                xAxes: [
                  {
                    display: false,
                    ticks: { beginAtZero: true, max: 5 },
                  },
                ],
                yAxes: [
                  {
                    ticks: {
                      fontSize: 12,
                      fontColor: "#374151",
                      padding: 8,
                    },
                    gridLines: { display: false },
                    afterFit(s) { s.width = LABEL_WIDTH; },
                  },
                ],
              },
              tooltips: {
                callbacks: {
                  title: (items) => {
                    const r = this.stats.survey_avg_scores[items[0].index];
                    return this.surveyQuestionLabel(r.question);
                  },
                  label: (item) =>
                    ` Avg Score: ${parseFloat(item.xLabel).toFixed(2)}`,
                },
              },
            },
          });
        }
      }
    },

    destroyCharts() {
      Object.values(this.charts).forEach((c) => {
        if (c) c.destroy();
      });
      this.charts = {
        dropoff: null,
        strategy: null,
        language: null,
        turns: null,
        funnel: null,
        weekly: null,
        responseTime: null,
        course: null,
        survey: null,
        surveyAxis: null,
      };
    },

    downloadCSV() {
      const rows = [
        ["Metric", "Value"],
        ["Total Students", this.stats.total_students],
        ["Completed Interviews", this.stats.total_completed],
        ["Completion Rate %", this.completionRate],
        ["Avg Duration (min)", this.stats.avg_duration_minutes],
        ["Std Deviation (min)", this.stats.std_duration_minutes],
        ["Variance", this.stats.var_duration_minutes],
        ["Avg LLM Response (s)", this.stats.avg_response_time_seconds],
        ["Survey Responses", this.stats.survey_count],
        ["Survey Completion Rate %", this.surveyCompletionRate],
        ["Repeated Interviews", this.stats.reattempts],
        ["Avg Turns Completed", this.stats.avg_turns_completed],
        ["Avg Turns Incomplete", this.stats.avg_turns_incomplete],
        ["Avg Responses", this.stats.avg_messages_per_interview],
        ["Total Responses", this.stats.total_messages],
        ["Last Activity", this.stats.last_activity || ""],
        ["Avg Response Gap (s)", this.stats.avg_response_gap_seconds || ""],
        [],
        ["Drop-off Step", "Count"],
        ...(this.stats.dropoff_distribution || []).map((s) => [s.step, s.count]),
        [],
        ["Strategy", "Count"],
        ...(this.stats.strategy_distribution || []).map((s) => [s.name || s.strategy, s.count]),
        [],
        ["Funnel Step", "Count"],
        ...(this.stats.completion_funnel || []).map((f) => [f.step, f.count]),
        [],
        ["Week", "Responses", "Users"],
        ...(this.stats.weekly_activity || []).map((w) => [w.week, w.messages, w.users]),
      ];
      const a = document.createElement("a");
      a.href = URL.createObjectURL(
        new Blob([rows.map((r) => r.join(",")).join("\n")], { type: "text/csv" }),
      );
      a.download = "srl_dashboard.csv";
      a.click();
    },

    downloadExcel() {
      let html = "<html><head><meta charset='UTF-8'></head><body><table border='1'>";
      html += "<tr><th>Metric</th><th>Value</th></tr>";
      [
        ["Total Students", this.stats.total_students],
        ["Completed", this.stats.total_completed],
        ["Completion Rate %", this.completionRate],
        ["Avg Duration", this.stats.avg_duration_minutes],
        ["Std Dev", this.stats.std_duration_minutes],
        ["Variance", this.stats.var_duration_minutes],
        ["Avg LLM Response", this.stats.avg_response_time_seconds],
        ["Survey Responses", this.stats.survey_count],
        ["Survey Completion Rate %", this.surveyCompletionRate],
        ["Repeated Interviews", this.stats.reattempts],
        ["Total Responses", this.stats.total_messages],
        ["Last Activity", this.stats.last_activity || ""],
        ["Avg Response Gap (s)", this.stats.avg_response_gap_seconds || ""],
      ].forEach(([k, v]) => {
        html += `<tr><td>${k}</td><td>${v}</td></tr>`;
      });
      html += "</table><br><table border='1'><tr><th>Strategy</th><th>Count</th></tr>";
      (this.stats.strategy_distribution || []).forEach((s) => {
        html += `<tr><td>${s.name || s.strategy}</td><td>${s.count}</td></tr>`;
      });
      html += "</table></body></html>";
      const a = document.createElement("a");
      a.href = URL.createObjectURL(
        new Blob([html], { type: "application/vnd.ms-excel;charset=utf-8" }),
      );
      a.download = "srl_dashboard.xls";
      a.click();
    },

    downloadPDF() {
      const style = document.createElement("style");
      style.innerHTML = `@media print { body * { visibility: hidden; } #dashboard-content, #dashboard-content * { visibility: visible; } #dashboard-content { position: absolute; left: 0; top: 0; width: 100%; } }`;
      document.head.appendChild(style);
      window.print();
      setTimeout(() => document.head.removeChild(style), 1000);
    },

    beforeUnmount() {
      this.destroyCharts();
    },
  },
};
</script>

<style scoped>
@import url("https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap");

.rd-root {
  font-family: "DM Sans", sans-serif;
  background: #f0f4fa;
  min-height: 100vh;
  padding: 24px 32px;
  color: #1a1d2e;
  overflow-y: auto;
}

.rd-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 28px;
  flex-wrap: wrap;
  gap: 16px;
}
.rd-header-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.rd-badge {
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
.rd-title {
  font-size: 1.75rem;
  font-weight: 600;
  margin: 0;
  letter-spacing: -0.02em;
}
.rd-header-right {
  display: flex;
  flex-direction: row;
  gap: 16px;
  align-items: flex-end;
  flex-wrap: wrap;
}
.rd-filter-group {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}
.rd-date-field {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.rd-date-field label {
  font-size: 0.6rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  color: #9ca3af;
}
.rd-date-field input,
.rd-select {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 5px 8px;
  font-size: 0.8rem;
  font-family: "DM Sans", sans-serif;
  background: white;
}
.rd-select {
  min-width: 160px;
  max-width: 200px;
}

.rd-download-wrap {
  position: relative;
}
.rd-dropdown {
  position: absolute;
  right: 0;
  top: calc(100% + 4px);
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  z-index: 100;
  min-width: 120px;
}
.rd-dropdown button {
  display: block;
  width: 100%;
  padding: 8px 16px;
  text-align: left;
  background: none;
  border: none;
  font-size: 0.85rem;
  cursor: pointer;
  font-family: "DM Sans", sans-serif;
  color: #374151;
}
.rd-dropdown button:hover {
  background: #f3f4f6;
}

.rd-btn {
  font-family: "DM Sans", sans-serif;
  font-size: 0.8rem;
  font-weight: 500;
  padding: 6px 14px;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  transition: all 0.15s;
}
.rd-btn-primary {
  background: #2563b0;
  color: white;
}
.rd-btn-primary:hover {
  background: #1a4f9a;
}
.rd-btn-ghost {
  background: white;
  color: #374151;
  border: 1px solid #e5e7eb;
}
.rd-btn-ghost:hover {
  background: #f9fafb;
}
.rd-toggle-btn {
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
.rd-toggle-btn:hover {
  background: #dbeafe;
}

.rd-loading {
  text-align: center;
  padding: 60px;
  color: #9ca3af;
}
.rd-spinner {
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
.rd-error {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #2563b0;
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 20px;
}

.rd-kpi-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  margin-bottom: 24px;
}
.rd-kpi {
  background: white;
  border-radius: 10px;
  padding: 16px 18px;
  position: relative;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}
.rd-kpi-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: var(--accent);
}
.rd-kpi-value {
  font-size: 1.6rem;
  font-weight: 600;
  color: var(--accent);
  line-height: 1;
  margin-bottom: 4px;
  font-family: "DM Mono", monospace;
}
.rd-kpi-label {
  font-size: 0.75rem;
  color: #6b7280;
  font-weight: 500;
}
.rd-kpi-sub {
  font-size: 0.68rem;
  color: #9ca3af;
  margin-top: 3px;
}

.rd-charts-row {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}
.rd-chart-card {
  background: white;
  border-radius: 10px;
  padding: 18px 20px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
}
.rd-chart-wide {
  flex: 2;
}
.rd-chart-narrow {
  flex: 1;
}
.rd-chart-header {
  margin-bottom: 12px;
}
.rd-chart-header-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}
.rd-chart-title {
  font-size: 0.9rem;
  font-weight: 600;
  display: block;
}
.rd-chart-sub {
  font-size: 0.72rem;
  color: #9ca3af;
}
.rd-chart-sub code {
  background: #eff6ff;
  color: #2563b0;
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 0.68rem;
}
.rd-canvas-wrap {
  position: relative;
  height: 200px;
}
.rd-canvas-wrap canvas {
  height: 200px !important;
}
.rd-empty {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: #d1d5db;
  font-size: 0.82rem;
  white-space: nowrap;
}
.rd-empty-explain {
  text-align: center;
  color: #9ca3af;
  font-size: 0.78rem;
  padding: 24px 16px;
  line-height: 1.8;
}
.rd-empty-explain span {
  font-size: 0.72rem;
  color: #93c5fd;
}
.rd-empty-explain code {
  background: #eff6ff;
  color: #2563b0;
  padding: 1px 5px;
  border-radius: 3px;
}

.rd-info-card {
  justify-content: center;
}
.rd-big-stat {
  font-size: 2.2rem;
  font-weight: 700;
  font-family: "DM Mono", monospace;
  margin: 8px 0 4px;
  color: #2563b0;
}
.rd-big-stat-sm {
  font-size: 1.1rem;
  margin-top: 12px;
}
.rd-progress-bar-wrap {
  background: #dbeafe;
  border-radius: 99px;
  height: 6px;
  margin-top: 10px;
  overflow: hidden;
}
.rd-progress-bar {
  background: #2563b0;
  height: 6px;
  border-radius: 99px;
  transition: width 0.6s ease;
}

.rd-table-mt {
  margin-top: 4px;
}
.rd-table-title {
  font-size: 0.82rem;
  font-weight: 600;
  color: #374151;
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.rd-badge-sm {
  font-size: 0.65rem;
  background: #dbeafe;
  color: #2563b0;
  padding: 2px 7px;
  border-radius: 99px;
  font-weight: 500;
}
.rd-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.78rem;
}
.rd-table th {
  padding: 5px 8px;
  text-align: left;
  color: #9ca3af;
  font-weight: 600;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid #f3f4f6;
}
.rd-table td {
  padding: 6px 8px;
  border-bottom: 1px solid #f9fafb;
  color: #374151;
}
.rd-table tr:last-child td {
  border-bottom: none;
}
.rd-empty-row {
  color: #d1d5db;
  text-align: center;
  padding: 12px;
}

.rd-survey-card {
  background: white;
  border-radius: 10px;
  padding: 18px 20px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
  margin-bottom: 16px;
}

.rd-survey-chart-outer {
  display: flex;
  flex-direction: column;
  border: 1px solid #f3f4f6;
  border-radius: 6px;
  overflow: hidden;
}

.rd-survey-axis-header {
  flex-shrink: 0;
  background: #fff;
  border-bottom: 1px solid #f3f4f6;
  height: 56px;
  position: relative;
}

.rd-survey-axis-label {
  font-size: 0.7rem;
  font-weight: 600;
  color: #9ca3af;
  letter-spacing: 0.05em;
  text-align: center;
  padding-top: 4px;
  margin-left: 320px;
}

.rd-survey-chart-scroll {
  max-height: 480px;
  overflow-y: auto;
  overflow-x: hidden;
  border: none;
  border-radius: 0;
}

/* ── Mobile responsive ─────────────────────────────────────── */
@media (max-width: 768px) {
  .rd-root {
    padding: 12px 8px;
  }
  .rd-kpi {
    min-width: 100% !important;
  }
  .rd-chart-card {
    padding: 12px 8px;
  }
}
@media (max-width: 480px) {
  .rd-header-right {
    flex-direction: column;
    align-items: flex-start;
    gap: 6px;
  }
}

/* ── Mobile KPI grid fix ───────────────────────────────────── */
@media (max-width: 480px) {
  .rd-kpi-grid {
    display: grid !important;
    grid-template-columns: 1fr 1fr !important;
    gap: 8px !important;
  }
  .rd-kpi {
    min-width: unset !important;
    width: 100% !important;
  }
  .rd-root {
    padding: 8px 6px !important;
  }
}

@media print {
  .rd-header-right {
    display: none;
  }
  .rd-root {
    background: white;
    padding: 16px;
  }
  .rd-chart-card,
  .rd-kpi {
    box-shadow: none;
    border: 1px solid #e5e7eb;
  }
}
</style>