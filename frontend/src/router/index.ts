import Vue from "vue";
import VueRouter from "vue-router";
import axios from "axios";
import AgentChat from "../components/AgentChat.vue";
import SurveyView from "../components/SurveyView.vue";
import ProtocolEditor from "../components/ProtocolEditor.vue";
import DashboardResearcher from "../components/DashboardResearcher.vue";
import DashboardTeacher from "../components/DashboardTeacher.vue";
import LandingPage from "../components/LandingPage.vue";
import StudentResults from "../components/StudentResults.vue";

Vue.use(VueRouter);
const routes = [
  { path: "/", component: LandingPage },
  { path: "/agent-chat", component: AgentChat },
  { path: "/survey", component: SurveyView },
  { path: "/protocols", component: ProtocolEditor },
  { path: "/results", component: StudentResults },
  { path: "/dashboard/researcher", component: DashboardResearcher },
  { path: "/dashboard/teacher", component: DashboardTeacher },
];
const router = new VueRouter({
  mode: "hash",
  routes,
});

const PAGE_NAMES = {
  "/": "landing",
  "/agent-chat": "interview",
  "/survey": "survey",
  "/protocols": "protocol_editor",
  "/results": "student_results",
  "/dashboard/researcher": "dashboard_researcher",
  "/dashboard/teacher": "dashboard_teacher",
};

// Log every page navigation to the backend activity_log
router.afterEach((to) => {
  const apiBase =
    (window.SRL_CONFIG && window.SRL_CONFIG.apiBaseUrl) ||
    window.location.origin;
  const userid =
    (window.SRL_CONFIG && window.SRL_CONFIG.userId) ||
    new URLSearchParams(window.location.search).get("userid") ||
    localStorage.getItem("srl_userid");

  const pageName = PAGE_NAMES[to.path] || to.path;

  axios
    .post(apiBase + "/log/page_view", {
      userid,
      client: "web",
      path: to.fullPath,
      page_name: pageName,
      timestamp: Math.floor(Date.now() / 1000),
    })
    .catch(() => {
      /* non-critical */
    });
});

export default router;
