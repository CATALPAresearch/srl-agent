import { createRouter, createWebHashHistory } from "vue-router";
import axios from "axios";
import AgentChat from "../components/AgentChat.vue";
import SurveyView from "../components/SurveyView.vue";
import ProtocolEditor from "../components/ProtocolEditor.vue";
import DashboardResearcher from "../components/DashboardResearcher.vue";
import DashboardTeacher from "../components/DashboardTeacher.vue";
import LandingPage from "../components/LandingPage.vue";
import StudentResults from "../components/StudentResults.vue";

const routes = [
  { path: "/", component: LandingPage },
  { path: "/agent-chat", component: AgentChat },
  { path: "/survey", component: SurveyView },
  { path: "/protocols", component: ProtocolEditor },
  { path: "/results", component: StudentResults },
  { path: "/dashboard/researcher", component: DashboardResearcher },
  { path: "/dashboard/teacher", component: DashboardTeacher },
];
const router = createRouter({
  history: createWebHashHistory(),
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

// Redirect unauthenticated users away from admin-only routes
const ADMIN_ROUTES = new Set(['/protocols', '/dashboard/researcher']);
// Routes that require informed consent before access is granted
const CONSENT_ROUTES = new Set(['/agent-chat', '/survey', '/results']);
const CONSENT_KEY = 'srl_informed_consent';

router.beforeEach((to) => {
  if (ADMIN_ROUTES.has(to.path) && sessionStorage.getItem('srl_admin_session') !== '1') {
    return '/';
  }
  if (CONSENT_ROUTES.has(to.path) && localStorage.getItem(CONSENT_KEY) !== 'yes') {
    return '/';
  }
  return true;
});

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
