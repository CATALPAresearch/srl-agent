<template>
  <div class="landing-student container-fluid py-4">
    <!-- Progress stats -->
    <div class="row justify-content-center mb-4">
      <div class="col-md-10">
        <div class="row d-none d-sm-flex">
          <!-- Interview progress -->
          <div class="col-sm-4 mb-3">
            <div class="card text-center border-0 shadow-sm h-100">
              <div class="card-body py-3">
                <div class="stat-value text-primary">
                  {{ progressStats[0].value }}
                </div>
                <div class="stat-label text-muted small">
                  {{
                    lang === "de"
                      ? progressStats[0].labelDe
                      : progressStats[0].labelEn
                  }}
                </div>
              </div>
            </div>
          </div>
          <!-- Survey progress -->
          <div class="col-sm-4 mb-3">
            <div class="card text-center border-0 shadow-sm h-100">
              <div class="card-body py-3">
                <div class="stat-value text-primary">
                  {{ progressStats[1].value }}
                </div>
                <div class="stat-label text-muted small">
                  {{
                    lang === "de"
                      ? progressStats[1].labelDe
                      : progressStats[1].labelEn
                  }}
                </div>
              </div>
            </div>
          </div>
          <!-- Strategies â€” direct link to results -->
          <div class="col-sm-4 mb-3">
            <component
              :is="interviewState === 'completed' ? 'router-link' : 'div'"
              to="/results"
              class="text-decoration-none"
            >
              <div
                class="card text-center border-0 shadow-sm h-100"
                :class="
                  interviewState === 'completed' ? 'stat-card-clickable' : ''
                "
                :title="
                  interviewState === 'completed'
                    ? lang === 'de'
                      ? 'Ergebnisse anzeigen'
                      : 'View results'
                    : ''
                "
              >
                <div class="card-body py-3">
                  <div class="stat-value text-primary">
                    {{ progressStats[2].value }}
                  </div>
                  <div class="stat-label text-muted small">
                    {{
                      lang === "de"
                        ? progressStats[2].labelDe
                        : progressStats[2].labelEn
                    }}
                  </div>
                </div>
              </div>
            </component>
          </div>
        </div>
      </div>
    </div>

    <!-- Welcome card -->
    <div class="row justify-content-center mb-4">
      <div class="col-md-10">
        <div class="card border-0 shadow-sm">
          <div class="card-body p-4">
            <h3 class="mb-3">
              {{ lang === "de" ? "Willkommen!" : "Welcome!" }}
            </h3>
            <p v-if="lang === 'de'">
              Gemeinsam mit Studierenden, Forschenden und Lehrenden haben wir
              ein System entwickelt, das Erkenntnisse aus der Lernwissenschaft
              und der KÃ¼nstlichen Intelligenz nutzt, um Ihnen zu helfen, Ihre
              Lernstrategien und Studienkompetenzen besser zu verstehen.
            </p>
            <p v-else>
              Together with students, researchers, and instructors we have
              developed a system that uses insights from learning science and
              artificial intelligence to help you better understand your
              learning strategies and study skills.
            </p>
            <p v-if="lang === 'de'">
              Im nÃ¤chsten Schritt werden Sie etwa
              <strong>10 Minuten</strong> mit dem System chatten und einige
              Fragen dazu beantworten, wie Sie Ã¼blicherweise in dieser
              Lehrveranstaltung lernen. Kurz nach diesem Interview analysiert
              das System Ihre Antworten und gibt Ihnen
              <strong>personalisiertes Feedback</strong>.
            </p>
            <p v-else>
              In the next step, you will spend about
              <strong>10 minutes</strong> chatting with the system and answering
              a few questions about how you usually study in your course.
              Shortly after the conversation, the system will analyze your
              responses and provide you with
              <strong>personalized feedback</strong>.
            </p>
            <p class="mb-3" v-if="lang === 'de'">
              Unser Ziel ist es, Ihnen zu helfen, besser zu verstehen, wie Sie
              lernen, und neue Strategien zu entdecken, die das Lernen leichter
              oder effektiver machen kÃ¶nnten. Sie werden entdecken:
            </p>
            <p class="mb-3" v-else>
              Our goal is to help you better understand how you study and
              explore new strategies that might make learning easier or more
              effective for you. You will discover:
            </p>
            <ul class="discover-list list-unstyled mb-4" v-if="lang === 'de'">
              <li>
                ðŸ§  Die Lernstrategien, die Sie bereits am hÃ¤ufigsten nutzen
              </li>
              <li>
                ðŸ” Weitere effektive Strategien, von denen Forschende zeigen,
                dass sie Studierenden beim Lernen helfen kÃ¶nnen
              </li>
              <li>
                ðŸ“Š Wie Ihr Lernansatz mit Mustern verglichen wird, die in
                Studien mit anderen Studierenden gefunden wurden
              </li>
              <li>
                ðŸ’¡ Praktische Ideen und einfache Tipps, die Sie ausprobieren
                kÃ¶nnen, um Ihre Lernstrategien zu verbessern oder zu erweitern
              </li>
            </ul>
            <ul class="discover-list list-unstyled mb-4" v-else>
              <li>ðŸ§  The learning strategies you already use most often</li>
              <li>
                ðŸ” Other effective strategies that research shows can help
                students learn
              </li>
              <li>
                ðŸ“Š How your learning approach compares with patterns found in
                studies of other students
              </li>
              <li>
                ðŸ’¡ Practical ideas and simple tips you can try to improve or
                expand your learning strategies
              </li>
            </ul>

            <hr />

            <!-- Consent not yet given: show prompt + button to open modal -->
            <div v-if="!consentGiven" class="mb-4">
              <p class="mb-3">
                {{
                  lang === "de"
                    ? "Um fortzufahren bitten wir Sie um Ihre Einwilligung zur Erhebung und Auswertung Ihrer Antworten. Die Teilnahme ist freiwillig und Sie kÃ¶nnen jederzeit aufhÃ¶ren."
                    : "To continue, we ask for your informed consent to collect and analyze your responses. Participation is completely voluntary, and you can stop at any time."
                }}
              </p>
              <button class="btn btn-primary" @click="openConsentModal">
                {{
                  lang === "de"
                    ? "EinwilligungserklÃ¤rung lesen &amp; zustimmen"
                    : "Read &amp; give consent"
                }}
              </button>
            </div>

            <!-- Consent modal -->
            <div
              v-if="showConsentModal"
              class="consent-modal-overlay"
              @click.self="showConsentModal = false"
            >
              <div class="consent-modal-box">
                <button
                  class="consent-modal-close"
                  @click="showConsentModal = false"
                  aria-label="Close"
                >
                  &times;
                </button>
                <ChatInformedConsent :lang="lang" />
              </div>
            </div>

            <!-- Interview action block (shown only after consent) -->
            <div v-if="consentGiven">
              <!-- State: not started -->
              <div v-if="interviewState === 'not_started'">
                <p class="text-muted mb-3">
                  {{
                    lang === "de"
                      ? "Sie haben das Interview noch nicht begonnen. Starten Sie jetzt â€“ es dauert ca. 10 Minuten."
                      : "You have not started the interview yet. Begin now â€“ it takes about 10 minutes."
                  }}
                </p>
                <router-link to="/agent-chat">
                  <button class="btn btn-primary btn-lg">
                    {{
                      lang === "de" ? "Interview starten" : "Start Interview"
                    }}
                  </button>
                </router-link>
              </div>

              <!-- State: in progress -->
              <div v-else-if="interviewState === 'in_progress'">
                <div class="alert alert-warning d-flex align-items-center mb-3">
                  <span class="mr-2">â³</span>
                  <span>{{
                    lang === "de"
                      ? "Sie haben ein Interview begonnen, aber noch nicht abgeschlossen."
                      : "You have started an interview but have not finished it yet."
                  }}</span>
                </div>
                <router-link to="/agent-chat">
                  <button class="btn btn-warning btn-lg mr-3">
                    {{
                      lang === "de"
                        ? "Interview fortsetzen"
                        : "Continue Interview"
                    }}
                  </button>
                </router-link>
              </div>

              <!-- State: completed -->
              <div v-else-if="interviewState === 'completed'">
                <div class="alert alert-success d-flex align-items-center mb-3">
                  <span class="mr-2">âœ…</span>
                  <span>{{
                    lang === "de"
                      ? "Sie haben ein Interview bereits abgeschlossen."
                      : "You have already completed an interview."
                  }}</span>
                </div>
                <router-link to="/results" class="mr-3">
                  <button class="btn btn-success btn-lg">
                    {{ lang === "de" ? "Ergebnisse ansehen" : "View Results" }}
                  </button>
                </router-link>
                <button
                  class="btn btn-secondary btn-lg"
                  @click="redoInterview"
                >
                  {{
                    lang === "de" ? "Interview wiederholen" : "Redo Interview"
                  }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import Vue from "vue";
import axios from "axios";
import ChatInformedConsent from "./ChatInformedConsent.vue";

const CONSENT_KEY = "srl_informed_consent";

export default Vue.extend({
  name: "LandingStudent",

  components: { ChatInformedConsent },

  data() {
    return {
      // 'not_started' | 'in_progress' | 'completed'
      interviewState: "not_started",
      showConsentModal: false,
      progressStats: [
        {
          value: "0",
          labelDe: "Abgeschlossene Interviews",
          labelEn: "Completed interviews",
        },
        {
          value: "0 / 0",
          labelDe: "Fortschritt letztes Interview",
          labelEn: "Last interview progress",
        },
        {
          value: "â€“",
          labelDe: "Fragebogen abgeschlossen",
          labelEn: "Survey completed",
        },
      ],
    };
  },

  computed: {
    host() {
      return this.$store.getters.getApiHost;
    },
    lang() {
      return this.$store.getters.getLanguage || "de";
    },
    consentGiven() {
      return this.$store.getters.getInformedConsentAgreement === "yes";
    },
  },

  watch: {
    consentGiven(val) {
      if (val) {
        localStorage.setItem(CONSENT_KEY, "yes");
        this.showConsentModal = false;
        this.fetchInterviewState();
      }
    },
    "$store.getters.getInformedConsentAgreement"(val) {
      // Close modal when user explicitly declines ('Nein')
      if (val === "no" && this.showConsentModal) {
        this.showConsentModal = false;
      }
    },
  },

  mounted() {
    const stored = localStorage.getItem(CONSENT_KEY);
    if (stored === "yes") {
      this.$store.commit("setInformedConsentAgreement", "yes");
    } else if (this.$store.getters.getInformedConsentAgreement === false) {
      this.$store.commit("setInformedConsentAgreement", "none");
    }
    this.fetchInterviewState();
  },

  methods: {
    openConsentModal() {
      // Reset to 'none' so v-if in ChatInformedConsent matches and
      // the 'Nein' watcher can detect a change from 'none' â†’ 'no'
      this.$store.commit("setInformedConsentAgreement", "none");
      this.showConsentModal = true;
    },
    async redoInterview() {
      try {
        await axios.post(`${this.host}/resetConversation`, {
          client: "web",
          userid: this.$store.getters.getUser,
        });
      } catch (e) {
        // proceed even if archiving fails
      }
      localStorage.setItem("srl_fresh_start", "1");
      this.$router.push("/agent-chat");
    },

    async fetchInterviewState() {
      const userid = this.$store.getters.getUser;
      // Users are always stored with client="web" in the standalone/LTI context.
      const client = "web";
      if (!userid) return;
      try {
        const res = await axios.get(`${this.host}/student/results`, {
          params: { userid, client },
        });
        const data = res.data;
        const strategies = data.strategies || [];
        const completed = data.interview_completed === true;
        const hasActivity = strategies.length > 0 || completed;

        if (completed) {
          this.interviewState = "completed";
        } else if (hasActivity) {
          this.interviewState = "in_progress";
        } else {
          this.interviewState = "not_started";
        }

        this.progressStats[0].value = String(data.completed_runs || 0);

        const lastDone = Number(data.last_progress_done || 0);
        const lastTotal = Number(
          data.last_progress_total || data.total_contexts || 0,
        );
        this.progressStats[1].value = `${lastDone} / ${lastTotal}`;

        if (data.survey) {
          this.progressStats[2].value = "\u2713";
        } else {
          this.progressStats[2].value = "\u2713";
        }
      } catch {
        // backend unreachable or no data â€” keep defaults
      }
    },
  },
});
</script>

<style scoped>
.landing-student {
  max-width: 960px;
  margin: 0 auto;
}

.section-label {
  color: #495057;
  font-weight: 600;
  text-transform: uppercase;
  font-size: 0.78rem;
  letter-spacing: 0.08em;
}

.stat-value {
  font-size: 1.6rem;
  font-weight: 700;
}

.stat-label {
  font-size: 0.8rem;
  margin-top: 2px;
}

.stat-card-clickable {
  cursor: pointer;
  transition: box-shadow 0.2s, transform 0.2s;
}

.stat-card-clickable:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12) !important;
  transform: translateY(-2px);
}

.discover-list li {
  margin-bottom: 8px;
}

.consent-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.consent-modal-box {
  background: white;
  border-radius: 10px;
  padding: 28px 32px;
  width: 90%;
  max-width: 720px;
  max-height: 85vh;
  overflow-y: auto;
  position: relative;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.18);
}

.consent-modal-close {
  position: absolute;
  top: 14px;
  right: 18px;
  background: none;
  border: none;
  font-size: 1.6rem;
  line-height: 1;
  cursor: pointer;
  color: #6c757d;
}

.consent-modal-close:hover {
  color: #343a40;
}
/* ── Mobile responsive ─────────────────────────────────────── */
@media (max-width: 600px) {
  .landing-student {
    max-width: 100%;
    padding: 0 4px;
  }
  .stat-value {
    font-size: 1.3rem;
  }
  .consent-modal-box {
    padding: 18px 16px;
    width: 96%;
  }
}
/* LTI iframe - reduce padding when viewport is narrow */
@media (max-width: 480px) {
  .landing-student {
    padding: 0 2px;
  }
}
</style>


