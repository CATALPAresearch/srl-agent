<template>
  <div class="sr-root container-fluid py-4">
    <!-- Header -->
    <div class="row justify-content-center mb-4">
      <div class="col-md-10">
        <div class="card border-0 shadow-sm sr-hero">
          <div class="card-body p-4">
            <div class="d-flex align-items-center mb-1">
              <span class="badge badge-success mr-2">
                {{ lang === "de" ? "Abgeschlossen" : "Completed" }}
              </span>
              <h2 class="mb-0">
                {{ lang === "de" ? "Ihre Ergebnisse" : "Your Results" }}
              </h2>
            </div>
            <p class="text-muted mb-0">
              <template v-if="lang === 'de'">
                Vielen Dank, dass du dir die Zeit genommen hast, uns zu
                erzÃ¤hlen, wie du lernst! Wir haben deine Antworten sorgfÃ¤ltig
                ausgewertet. Deine Ergebnisse werden nun in den beiden Grafiken
                unten dargestellt, damit du sie erkunden kannst.
              </template>
              <template v-else>
                Thank you for taking the time to share how you learn with us!
                We've carefully analysed your answers, and your results are now
                shown in the two graphs below so you can explore them.
              </template>
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- Error -->
    <div v-if="error" class="row justify-content-center">
      <div class="col-md-10">
        <div class="alert alert-danger">{{ error }}</div>
      </div>
    </div>

    <template v-else>
      <div class="row justify-content-center mb-4">
        <div class="col-md-10">
          <div class="card border-0 shadow-sm">
            <div class="card-body">
              <p>
                <template v-if="lang === 'de'">
                  Das Spinnendiagramm zeigt die Lernstrategien, die du beim
                  Beschreiben deines Lernens erwÃ¤hnt hast. HÃ¶here Werte
                  bedeuten, dass du diese Strategie hÃ¤ufiger und regelmÃ¤ÃŸiger
                  eingesetzt hast. Es ist vÃ¶llig normal, dass das Diagramm nicht
                  vollstÃ¤ndig ausgefÃ¼llt ist. Jeder lernt anders und niemand
                  nutzt alle Strategien gleich hÃ¤ufig. Das Diagramm kann dir
                  aber helfen, Strategien zu entdecken, die du seltener
                  verwendest.
                </template>
                <template v-else>
                  The spider chart shows the learning strategies you mentioned
                  when describing how you study. Higher values mean that you
                  reported using that strategy more often and more frequently.
                  It is completely normal that the whole chart is not filled.
                  Everyone learns in different ways, and no one uses all
                  strategies equally. However, the chart may help you notice
                  strategies that you use less often.
                </template>
              </p>

              <div class="row mt-3">
                <!-- Radar chart -->
                <div class="col-md-12 mb-1">
                  <div class="sr-radar-wrap">
                    <!-- Desktop: radar chart -->
                    <canvas v-show="!isMobile" ref="radarCanvas" style="max-width: 100%"></canvas>
                    <!-- Mobile: horizontal bar chart -->
                    <div v-show="isMobile" style="height: 480px; position: relative;">
                      <canvas ref="mobileBarCanvas"></canvas>
                    </div>
                    <!-- Invisible hit areas over each axis label -->
                    <span
                      v-for="o in radarLabelOverlays"
                      :key="o.idx"
                      :id="'sr-rl-' + componentId + '-' + o.idx"
                      class="sr-label-hit"
                      :style="{ left: o.x + 'px', top: o.y + 'px' }"
                    ></span>
                    <b-popover
                      v-for="o in radarLabelOverlays"
                      :key="'rp-' + o.idx"
                      :target="'sr-rl-' + componentId + '-' + o.idx"
                      triggers="hover focus"
                      placement="auto"
                      @show="
                        logInteraction('strategy_hovered', {
                          strategy: data.radar_data[o.idx].name,
                          idx: o.idx,
                        })
                      "
                    >
                      <template #title>{{
                        data.radar_data[o.idx].name
                      }}</template>
                      <p
                        v-if="
                          data.radar_data[o.idx].definition ||
                          data.radar_data[o.idx].description
                        "
                        class="mb-2 small text-muted"
                        style="margin: 0 0 8px"
                      >
                        {{
                          data.radar_data[o.idx].definition ||
                          data.radar_data[o.idx].description
                        }}
                      </p>
                      <div style="font-size: 0.875rem">
                        <div>
                          <span
                            style="
                              display: inline-block;
                              width: 10px;
                              height: 10px;
                              border-radius: 2px;
                              background: rgba(54, 162, 235, 1);
                              margin-right: 5px;
                              vertical-align: middle;
                            "
                          ></span>
                          {{ lang === "de" ? "Du" : "You" }}:
                          {{ freqLabel(data.radar_data[o.idx].frequency || 0) }}
                        </div>
                        <div>
                          <span
                            style="
                              display: inline-block;
                              width: 10px;
                              height: 10px;
                              border-radius: 2px;
                              background: rgba(255, 153, 0, 0.85);
                              margin-right: 5px;
                              vertical-align: middle;
                            "
                          ></span>
                          {{
                            lang === "de" ? "Kursdurchschnitt" : "Course avg"
                          }}:
                          {{
                            freqLabel(
                              Math.round(
                                (data.radar_data[o.idx].avg_frequency || 0) *
                                  10,
                              ) / 10,
                            )
                          }}
                        </div>
                      </div>
                    </b-popover>
                  </div>
                </div>
              </div>
              <!-- Strategies not mentioned -->
              <div class="row mt-1 mb-3">
                <div class="col-md-12 mb-2">
                  <h6 class="font-weight-600 mb-2">
                    {{
                      lang === "de"
                        ? "Noch nicht erwÃ¤hnte Strategien"
                        : "Strategies not yet mentioned"
                    }}
                  </h6>
                  <template v-if="lang === 'de'">
                    Die folgenden Strategien wurden in deinen Antworten nicht
                    erwÃ¤hnt wurden. Dennoch haben sich Strategien in der
                    Bildungsforschung fÃ¼r viele Studierende als hilfreich
                    erwiesen. Vielleicht mÃ¶chtest du erkunden, ob einige davon
                    auch fÃ¼r dich funktionieren kÃ¶nnten. Probiere sie aus:
                  </template>
                  <template v-else>
                    The following strategies were not mentioned in your answers.
                    These strategies have been shown in educational research to
                    be helpful for many students. You might want to explore
                    whether some of them could work for you too. Consider trying
                    them
                  </template>
                  <div
                    v-if="!unmentiondStrategies.length"
                    class="text-muted small mt-2"
                  >
                    {{
                      lang === "de"
                        ? "Super â€“ du hast alle Strategien erwÃ¤hnt!"
                        : "Great â€” you mentioned all strategies!"
                    }}
                  </div>
                  <div v-else class="sr-tag-cloud mt-2">
                    <span
                      v-for="(s, si) in unmentiondStrategies"
                      :key="s.id"
                      :id="'sr-tag-' + componentId + '-' + si"
                      class="sr-strategy-tag"
                      >{{ s.name }}</span
                    >
                    <b-popover
                      v-for="(s, si) in unmentiondStrategies"
                      :key="'tp-' + si"
                      :target="'sr-tag-' + componentId + '-' + si"
                      triggers="hover focus"
                      placement="top"
                      @show="
                        logInteraction('unmentioned_strategy_hovered', {
                          strategy: s.name,
                          id: s.id,
                        })
                      "
                    >
                      <template #title>{{ s.name }}</template>
                      {{ s.definition || s.description }}
                    </b-popover>
                  </div>
                </div>
              </div>

              <p>
                <template v-if="lang === 'de'">
                  Wenn du mehr Ã¼ber eine dieser Strategien erfahren, Tipps zu
                  deren Anwendung erhalten oder etwas im Diagramm unklar ist,
                  dann kannst du hier weitere Fragen stellen.
                </template>
                <template v-else>
                  If you'd like to learn more about any of these strategies, get
                  tips on how to use them, or if something in the graph isn't
                  clear, feel free to ask the agent.
                </template>
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- Motivation and Learning Beliefs section -->
      <div hidden class="row justify-content-center mb-4">
        <div class="col-md-10">
          <div class="card border-0 shadow-sm">
            <div class="card-header bg-white">
              <h5 class="mb-0 sr-section-title">
                {{
                  lang === "de"
                    ? "Deine Motivation und LernÃ¼berzeugungen"
                    : "Your Motivation and Learning Beliefs"
                }}
              </h5>
            </div>
            <div class="card-body">
              <p>
                {{
                  lang === "de"
                    ? "Die zweite Grafik zeigt deine Ãœberzeugungen zu Motivation und LernfÃ¤higkeiten."
                    : "The second graph shows your beliefs about your motivation and learning skills."
                }}
              </p>
              <ul>
                <li>
                  <template v-if="lang === 'de'">
                    <strong>So liest du diese Grafik:</strong> Die blaue Linie
                    zeigt deine Antworten und die orangefarbene Linie zeigt die
                    Durchschnittsergebnisse anderer Studierender aus einer
                    aktuellen GroÃŸstudie.
                  </template>
                  <template v-else>
                    <strong>How to read this graph:</strong> The blue line shows
                    your answers and the orange line shows the average results
                    from other students in a recent large scale study.
                  </template>
                </li>
              </ul>
              <p>
                <template v-if="lang === 'de'">
                  Dieser Vergleich kann dir helfen, Ã¼ber deine Lerngewohnheiten
                  und -Ã¼berzeugungen nachzudenken. Es gibt hier keine â€žguten"
                  oder â€žschlechten" Ergebnisse â€“ es zeigt einfach, wie deine
                  Ansichten im Vergleich zu anderen Studierenden einzuordnen
                  sind. HÃ¶here Werte korrelieren jedoch hÃ¤ufig mit besserem
                  Studienerfolg.
                </template>
                <template v-else>
                  This comparison can help you reflect on your learning habits
                  and beliefs. There are no "good" or "bad" results here â€” it
                  simply shows how your views compare with those of other
                  students. However, higher scores are often correlated with
                  better academic success.
                </template>
              </p>

              <p>
                <template v-if="lang === 'de'">
                  Wenn du konkrete Fragen hast oder Ideen suchst, wie du deine
                  Motivation stÃ¤rken oder bestimmte LernfÃ¤higkeiten (wie
                  Metakognition) verbessern kannst, frag gerne im Chat unten.
                  Wir teilen gerne praktische Tipps und hilfreiche VorschlÃ¤ge.
                </template>
                <template v-else>
                  If you have specific questions, or would like ideas on how to
                  strengthen your motivation or improve certain learning skills
                  presented here (like metacognition), please ask in the chat
                  below. We are happy to share practical tips and helpful
                  suggestions.
                </template>
              </p>
              <p class="mb-0">
                <template v-if="lang === 'de'">
                  Wir hoffen, dass dir diese Ergebnisse helfen, mehr Ã¼ber deinen
                  eigenen Lernprozess zu erfahren und Strategien zu entdecken,
                  die am besten zu dir passen.
                </template>
                <template v-else>
                  We hope these results help you learn more about your own
                  learning process and discover strategies that work best for
                  you.
                </template>
              </p>
              <h5 class="mb-0 sr-section-title">
                {{ lang === "de" ? "Eine Frage stellen" : "Ask a Question" }}
              </h5>
              <p class="text-muted small mb-0">
                {{
                  lang === "de"
                    ? "Ist etwas unklar? MÃ¶chtest du Tipps zu einer bestimmten Strategie?"
                    : "Is something unclear? Would you like tips on a specific strategy?"
                }}
              </p>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script>
import Vue from "vue";
import axios from "axios";
import Chart from "chart.js";
import { BPopover } from "bootstrap-vue";

export default Vue.extend({
  name: "StudentResults",
  components: { BPopover },

  data() {
    return {
      loading: true,
      error: null,
      data: {
        strategies: [],
        survey: null,
        interview_completed: false,
      },
      question: "",
      questionSent: false,
      radarChart: null,
      radarLabelOverlays: [],
      componentId: Math.random().toString(36).slice(2, 10),
      isMobile: false,
      mobileBarChart: null,
    };
  },

  computed: {
    host() {
      return this.$store.getters.getApiHost;
    },
    tickLabels() {
      return this.lang === "de"
        ? ["", "Selten", "Manchmal", "Oft", "Meistens"]
        : ["", "Seldom", "Sometimes", "Often", "Most of the time"];
    },
    lang() {
      return this.$store.getters.getLanguage || "de";
    },
    unmentiondStrategies() {
      if (!this.data.radar_data) return [];
      return this.data.radar_data.filter(
        (s) => !s.frequency || s.frequency === 0,
      );
    },
  },

  methods: {
    checkMobile() {
      this.isMobile = window.innerWidth <= 600;
    },

    renderMobileBarChart() {
      const radarData = this.data.radar_data;
      if (!radarData || !radarData.length) return;
      const canvas = this.$refs.mobileBarCanvas;
      if (!canvas) return;
      if (this.mobileBarChart) this.mobileBarChart.destroy();

      const truncate = (s, n) =>
        s.length > n ? s.slice(0, n - 1) + "\u2026" : s;

      this.mobileBarChart = new Chart(canvas.getContext("2d"), {
        type: "horizontalBar",
        data: {
          labels: radarData.map((s) => truncate(s.name, 28)),
          datasets: [
            {
              label: this.lang === "de" ? "Du" : "You",
              data: radarData.map((s) => s.frequency || 0),
              backgroundColor: "rgba(54, 162, 235, 0.7)",
              borderColor: "rgba(54, 162, 235, 1)",
              borderWidth: 1,
            },
            {
              label:
                this.lang === "de" ? "Kursdurchschnitt" : "Course average",
              data: radarData.map(
                (s) => Math.round((s.avg_frequency || 0) * 10) / 10
              ),
              backgroundColor: "rgba(255, 153, 0, 0.5)",
              borderColor: "rgba(255, 153, 0, 0.85)",
              borderWidth: 1,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          legend: { display: true, position: "bottom" },
          scales: {
            xAxes: [
              {
                ticks: {
                  beginAtZero: true,
                  max: 4,
                  stepSize: 1,
                  callback: (v) => {
                    const labels =
                      this.lang === "de"
                        ? ["", "Selten", "Manchmal", "Oft", "Meistens"]
                        : ["", "Seldom", "Sometimes", "Often", "Most of time"];
                    return labels[v] || v;
                  },
                },
              },
            ],
            yAxes: [
              {
                ticks: { fontSize: 10 },
              },
            ],
          },
          tooltips: {
            callbacks: {
              label: (item, chartData) => {
                const labels =
                  this.lang === "de"
                    ? ["", "Selten", "Manchmal", "Oft", "Meistens"]
                    : ["", "Seldom", "Sometimes", "Often", "Most of time"];
                const dsLabel = chartData.datasets[item.datasetIndex].label;
                const val = item.xLabel;
                const text = labels[Math.round(val)] || val;
                return ` ${dsLabel}: ${text} (${val})`;
              },
            },
          },
        },
      });
    },
    renderRadarChart() {
      if (this.isMobile) {
        this.$nextTick(() => this.renderMobileBarChart());
        return;
      }
      const radarData = this.data.radar_data;
      if (!radarData || !radarData.length) return;
      const canvas = this.$refs.radarCanvas;
      if (!canvas) return;

      if (this.radarChart) {
        this.radarChart.destroy();
      }

      const truncate = (s, n) =>
        s.length > n ? s.slice(0, n - 1) + "\u2026" : s;
      const shortLabels = radarData.map((s) => truncate(s.name, 20));
      const freqs = radarData.map((s) => s.frequency || 0);
      const avgs = radarData.map(
        (s) => Math.round((s.avg_frequency || 0) * 10) / 10,
      );

      this.radarChart = new Chart(canvas.getContext("2d"), {
        type: "radar",
        data: {
          labels: shortLabels,
          datasets: [
            {
              label: this.lang === "de" ? "Du" : "You",
              data: freqs,
              backgroundColor: "rgba(54, 162, 235, 0.15)",
              borderColor: "rgba(54, 162, 235, 1)",
              pointBackgroundColor: "rgba(54, 162, 235, 1)",
              pointBorderColor: "#fff",
              borderWidth: 2,
              pointRadius: 4,
            },
            {
              label: this.lang === "de" ? "Kursdurchschnitt" : "Course average",
              data: avgs,
              backgroundColor: "rgba(255, 153, 0, 0.12)",
              borderColor: "rgba(255, 153, 0, 0.85)",
              pointBackgroundColor: "rgba(255, 153, 0, 0.85)",
              pointBorderColor: "#fff",
              borderWidth: 2,
              borderDash: [5, 4],
              pointRadius: 3,
            },
          ],
        },
        options: {
          responsive: true,
          scale: {
            ticks: {
              beginAtZero: true,
              max: 4,
              min: 0,
              stepSize: 1,
              callback: () => "",
              backdropColor: "transparent",
            },
            pointLabels: { fontSize: 10 },
          },
          tooltips: { enabled: false },
          legend: { display: true, position: "bottom" },
        },
      });
      this._buildLabelOverlays();
    },

    freqLabel(v) {
      const i = Math.round(v);
      return this.tickLabels[i] ? this.tickLabels[i] + ` (${v})` : String(v);
    },

    _buildLabelOverlays() {
      const radarData = this.data.radar_data;
      if (!radarData || !this.radarChart) return;
      const scale = this.radarChart.scale;
      const n = radarData.length;
      const overlays = [];
      for (let i = 0; i < n; i++) {
        const pos = scale.getPointPosition(i, scale.drawingArea + 18);
        overlays.push({ x: Math.round(pos.x), y: Math.round(pos.y), idx: i });
      }
      this.radarLabelOverlays = overlays;
    },

    barClass(val) {
      if (val >= 4) return "sr-bar-high";
      if (val >= 3) return "sr-bar-mid";
      return "sr-bar-low";
    },

    logInteraction(action, value) {
      axios
        .post(`${this.host}/log/interaction`, {
          userid: this.$store.getters.getUser,
          client: "web",
          action,
          value,
          timestamp: Math.floor(Date.now() / 1000),
        })
        .catch(() => {
          /* non-critical */
        });
    },

    async loadResults() {
      this.loading = true;
      this.error = null;
      try {
        const urlUserId = new URLSearchParams(window.location.hash.split("?")[1] || "").get("userid");
        const userid = urlUserId || this.$store.getters.getUser;
        const res = await axios.get(`${this.host}/student/results`, {
          params: {
            userid,
            client: "web",
            lang: this.lang,
          },
        });
        this.data = res.data;
      } catch (e) {
        this.error =
          this.lang === "de"
            ? "Ergebnisse konnten nicht geladen werden."
            : "Failed to load results.";
      } finally {
        this.loading = false;
      }
      // Canvas is only in the DOM once loading is false, so render after.
      await this.$nextTick();
      this.renderRadarChart();
    },
  },

  watch: {
    lang() {
      this.loadResults();
    },
  },

  mounted() {
    this.checkMobile();
    this._onResize = () => {
      const wasMobile = this.isMobile;
      this.checkMobile();
      if (wasMobile !== this.isMobile) {
        this.renderRadarChart();
      }
    };
    window.addEventListener("resize", this._onResize);
    this.loadResults();
  },

  beforeDestroy() {
    if (this.radarChart) this.radarChart.destroy();
    if (this.mobileBarChart) this.mobileBarChart.destroy();
    window.removeEventListener("resize", this._onResize);
  },
});
</script>

<style scoped>
.sr-root {
  max-width: 960px;
  margin: 0 auto;
}

.sr-hero {
  background: linear-gradient(135deg, #e6f4ea 0%, #f8f9fa 100%);
}

.sr-kpi-value {
  font-size: 2rem;
  font-weight: 700;
}

.sr-kpi-label {
  font-size: 0.8rem;
  margin-top: 2px;
}

.sr-section-title {
  font-size: 1rem;
  font-weight: 600;
}

.font-weight-600 {
  font-weight: 600;
}

.sr-strategy-num {
  font-size: 1.2rem;
  min-width: 28px;
}

.sr-strategy-row {
  transition: background 0.15s;
}

.sr-strategy-row:hover {
  background: #f8f9fa;
}

/* Survey result bars */
.sr-survey-grid {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sr-survey-item {
  display: grid;
  grid-template-columns: 90px 1fr 28px;
  align-items: center;
  gap: 8px;
  font-size: 0.82rem;
}

.sr-item-id {
  font-family: monospace;
  font-size: 0.75rem;
}

.sr-item-bar-wrap {
  background: #e9ecef;
  border-radius: 4px;
  height: 10px;
  overflow: hidden;
}

.sr-item-bar {
  height: 100%;
  border-radius: 4px;
  transition: width 0.4s ease;
}

.sr-bar-high {
  background: #28a745;
}
.sr-bar-mid {
  background: #ffc107;
}
.sr-bar-low {
  background: #dc3545;
}

.sr-item-val {
  text-align: right;
}

.sr-chart-placeholder {
  background: #f1f3f5;
  border: 2px dashed #ced4da;
  border-radius: 8px;
  height: 260px;
  font-size: 1rem;
  color: #adb5bd;
}

.sr-tag-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.sr-strategy-tag {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 12px;
  background: #e8f0fe;
  color: #3367d6;
  font-size: 0.75rem;
  line-height: 1.4;
  white-space: normal;
  word-break: break-word;
  cursor: default;
}

/* â”€â”€ Radar label hit areas â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.sr-radar-wrap {
  position: relative;
}

.sr-label-hit {
  position: absolute;
  display: block;
  width: 90px;
  height: 26px;
  transform: translate(-50%, -50%);
  cursor: default;
}
<<<<<<< Updated upstream
/* ── Mobile responsive ─────────────────────────────────────── */
@media (max-width: 768px) {
  .sr-root {
    padding: 12px 8px;
    min-height: auto;
  }
  .sr-radar-wrap canvas {
    max-width: 100% !important;
    height: auto !important;
  }
  .sr-label-hit {
    display: none;
=======
@media (max-width: 600px) {
  .sr-radar-wrap {
    min-height: 480px;
>>>>>>> Stashed changes
  }
}
</style>

