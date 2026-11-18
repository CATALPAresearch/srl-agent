import { createStore } from "vuex";

// App-wide state. All data comes from this app's own backend (apiHost); there are no
// other service hosts in the frontend.
export const store = createStore({
  state: {
    // admin mode — mirrors the server session (see ChatApp.loadAdminStatus)
    isAdmin: sessionStorage.getItem("srl_admin_session") === "1",

    // API backend host (set from SRL_CONFIG or defaults to current origin)
    apiHost: window.location.origin,

    // user context (identity is issued by the server, see main.js)
    user: {
      userId: null,
    },
    language: localStorage.getItem("srl_lang") || "de",
    role: "student", // 'student' | 'teacher' — from the server-issued identity
    informedConsentAgreement: false,
  },

  mutations: {
    setInformedConsentAgreement(state, value) {
      state.informedConsentAgreement = value;
    },

    setAdmin(state, value) {
      state.isAdmin = value;
    },

    setApiHost(state, host) {
      state.apiHost = host;
    },

    setUser(state, userId) {
      state.user.userId = userId;
    },

    setLanguage(state, lang) {
      state.language = lang || "de";
      localStorage.setItem("srl_lang", state.language);
    },

    setRole(state, role) {
      state.role = role === "teacher" ? "teacher" : "student";
    },
  },

  getters: {
    getIsAdmin(state) {
      return state.isAdmin;
    },

    getInformedConsentAgreement(state) {
      return state.informedConsentAgreement;
    },

    getApiHost(state) {
      return state.apiHost;
    },

    getUser(state) {
      return state.user.userId;
    },

    getLanguage(state) {
      return state.language;
    },

    getRole(state) {
      return state.role;
    },
  },
});
