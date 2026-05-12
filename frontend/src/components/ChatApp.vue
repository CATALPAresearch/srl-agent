<template>
  <div class="chat-app">
    <div class="header-bar d-flex align-items-center px-2 py-1">

      <!-- MOBILE: hamburger (visible xs only) -->
      <div class="mobile-menu-wrapper d-flex d-sm-none align-items-center flex-grow-1">
        <button
          class="btn btn-sm btn-outline-secondary"
          @click="mobileMenuOpen = !mobileMenuOpen"
          aria-label="Navigation menu"
        >
          <font-awesome-icon :icon="['fas', 'bars']" />
        </button>
        <div v-if="mobileMenuOpen" class="mobile-nav-dropdown">
          <router-link to="/" exact class="mobile-nav-item" active-class="mobile-nav-active" @click.native="mobileMenuOpen = false">
            {{ lang === "de" ? "Start" : "Home" }}
          </router-link>
          <router-link to="/agent-chat" class="mobile-nav-item" active-class="mobile-nav-active" @click.native="mobileMenuOpen = false">
            {{ lang === "de" ? "Interview" : "Interview" }}
          </router-link>
          <router-link to="/survey" class="mobile-nav-item" active-class="mobile-nav-active" @click.native="mobileMenuOpen = false">
            {{ lang === "de" ? "Umfrage" : "Survey" }}
          </router-link>
          <router-link v-if="isAdmin" to="/protocols" class="mobile-nav-item" active-class="mobile-nav-active" @click.native="mobileMenuOpen = false">
            Protocols
          </router-link>
          <router-link v-if="isAdmin" to="/dashboard/researcher" class="mobile-nav-item" active-class="mobile-nav-active" @click.native="mobileMenuOpen = false">
            Researcher Dashboard
          </router-link>
          <router-link to="/dashboard/teacher" class="mobile-nav-item" active-class="mobile-nav-active" @click.native="mobileMenuOpen = false">
            Teacher Dashboard
          </router-link>
        </div>
      </div>

      <!-- DESKTOP: tabs (hidden on xs) -->
      <nav class="tabs flex-grow-1 d-none d-sm-flex">
        <router-link to="/" exact class="tab" active-class="active">
          {{ lang === "de" ? "Start" : "Home" }}
        </router-link>
        <router-link to="/agent-chat" class="tab" active-class="active">
          {{
            lang === "de"
              ? "Interview zu Lernstrategien"
              : "Learning Strategies Interview"
          }}
        </router-link>
        <router-link to="/survey" class="tab" active-class="active">
          {{ lang === "de" ? "Umfrage" : "Survey" }}
        </router-link>
        <router-link
          v-if="isAdmin"
          to="/protocols"
          class="tab"
          active-class="active"
        >
          Protocols
        </router-link>
        <router-link
          v-if="isAdmin"
          to="/dashboard/researcher"
          class="tab"
          active-class="active"
        >
          Researcher Dashboard
        </router-link>
        <router-link to="/dashboard/teacher" class="tab" active-class="active">
          Teacher Dashboard
        </router-link>
      </nav>

      <!-- Role switcher (admin only) -->
      <div
        v-if="isAdmin"
        class="d-flex align-items-center mr-3"
        title="Switch role"
      >
        <div class="btn-group btn-group-sm" role="group" aria-label="Role">
          <button
            type="button"
            @click="setRole('student')"
            :class="[
              'btn',
              role === 'student' ? 'btn-primary' : 'btn-outline-secondary',
            ]"
          >
            <small>{{ lang === "de" ? "Stud." : "Student" }}</small>
          </button>
          <button
            type="button"
            @click="setRole('teacher')"
            :class="[
              'btn',
              role === 'teacher' ? 'btn-primary' : 'btn-outline-secondary',
            ]"
          >
            <small>{{ lang === "de" ? "Lehr." : "Teacher" }}</small>
          </button>
        </div>
      </div>

      <!-- Language switcher -->
      <div class="btn-group btn-group-sm" role="group" aria-label="Language">
        <button
          type="button"
          @click="setLanguage('de')"
          :class="[
            'btn',
            lang === 'de' ? 'btn-primary' : 'btn-outline-secondary',
          ]"
        >
          DE
        </button>
        <button
          type="button"
          @click="setLanguage('en')"
          :class="[
            'btn',
            lang === 'en' ? 'btn-primary' : 'btn-outline-secondary',
          ]"
        >
          EN
        </button>
      </div>

      <button
        v-if="isAdmin"
        type="button"
        class="btn btn-sm btn-outline-danger ml-2"
        @click="resetInterview"
      >
        {{ lang === "de" ? "Reset" : "Reset" }}
      </button>

      <!-- Admin area -->
      <div class="admin-area ml-2" style="position: relative">
        <button
          v-if="!isAdmin"
          class="btn btn-sm btn-secondary admin-lock-btn ml-2 d-none d-sm-inline-flex align-items-center"
          @click="toggleAdminLogin"
          :title="lang === 'de' ? 'Admin-Login' : 'Admin login'"
        >
          <font-awesome-icon icon="unlock" aria-hidden="true" />
        </button>
        <span v-else class="d-flex align-items-center">
          <button class="btn btn-sm btn-outline-secondary" @click="logoutAdmin">
            {{ lang === "de" ? "Admin abmelden" : "Logout admin" }}
          </button>
        </span>

        <!-- Login dropdown -->
        <div v-if="showAdminLogin" class="admin-login-popup">
          <div class="admin-login-inner">
            <p class="admin-login-title">
              {{ lang === "de" ? "Admin-Zugang" : "Admin access" }}
            </p>
            <input
              ref="adminPwInput"
              v-model="adminPasswordInput"
              type="password"
              class="form-control form-control-sm"
              :placeholder="lang === 'de' ? 'Passwort' : 'Password'"
              @keyup.enter="loginAdmin"
            />
            <p v-if="adminLoginError" class="admin-login-error">
              {{ lang === "de" ? "Falsches Passwort." : "Wrong password." }}
            </p>
            <div class="d-flex justify-content-between mt-2">
              <button
                class="btn btn-sm btn-secondary"
                @click="showAdminLogin = false"
              >
                {{ lang === "de" ? "Abbrechen" : "Cancel" }}
              </button>
              <button class="btn btn-sm btn-primary" @click="loginAdmin">
                {{ lang === "de" ? "Anmelden" : "Login" }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
    <keep-alive>
      <router-view class="chat-app__view" :lang="lang" />
    </keep-alive>
  </div>
</template>

<script>
import Vue from "vue";
import axios from "axios";
import { FontAwesomeIcon } from "@fortawesome/vue-fontawesome";

export default Vue.extend({
  name: "ChatApp",

  data() {
    return {
      showAdminLogin: false,
      adminPasswordInput: "",
      adminLoginError: false,
      mobileMenuOpen: false,
    };
  },

  computed: {
    host() {
      return this.$store.getters.getApiHost;
    },

    lang() {
      return this.$store.getters.getLanguage;
    },

    role() {
      return this.$store.getters.getRole;
    },

    isAdmin() {
      return this.$store.getters.getIsAdmin;
    },
  },

  methods: {
    setLanguage(lang) {
      this.$store.commit("setLanguage", lang);
      const userId = this.$store.getters.getUser;
      if (userId) {
        axios.put(`${this.host}/user_language/`, {
          userid: userId,
          client: "web",
          lang,
        }).catch(() => {});
      }
    },

    setRole(role) {
      this.$store.commit("setRole", role);
    },

    toggleAdminLogin() {
      this.showAdminLogin = !this.showAdminLogin;
      this.adminLoginError = false;
      if (this.showAdminLogin) {
        this.$nextTick(() => {
          const el = this.$refs.adminPwInput;
          if (el) el.focus();
        });
      }
    },

    loginAdmin() {
      const expected = window.SRL_ADMIN_PASSWORD || "admin";
      if (this.adminPasswordInput === expected) {
        this.$store.commit("setAdmin", true);
        sessionStorage.setItem("srl_admin_session", "1");
        this.showAdminLogin = false;
        this.adminPasswordInput = "";
        this.adminLoginError = false;
      } else {
        this.adminLoginError = true;
        this.adminPasswordInput = "";
      }
    },

    logoutAdmin() {
      this.$store.commit("setAdmin", false);
      sessionStorage.removeItem("srl_admin_session");
      const adminRoutes = ["/protocols", "/dashboard/researcher"];
      if (adminRoutes.includes(this.$route.path)) {
        this.$router.push("/");
      }
    },

    async loadUserLanguage() {
      const userId = this.$store.getters.getUser;
      if (!userId) return;
      try {
        const res = await axios.get(`${this.host}/user_language/`, {
          params: { userid: userId, client: "web" },
        });
        const backendLang = res.data;
        const localLang = localStorage.getItem("srl_lang");
        // localStorage wins â€” it reflects the user's explicit UI choice
        if (localLang) {
          this.$store.commit("setLanguage", localLang);
        } else if (backendLang) {
          this.$store.commit("setLanguage", backendLang);
        }
      } catch (e) {
        console.warn("Failed to load user language:", e);
      }
    },

    async loadUserRole() {
      try {
        const res = await axios.get(`${this.host}/user_role/`);
        if (res.data) this.$store.commit("setRole", res.data);
      } catch (e) {
        console.warn("Failed to load user role:", e);
      }
    },

    async resetInterview() {
      const userId =
        this.$store.getters.getUser || localStorage.getItem("srl_userid");
      if (!userId) {
        alert(
          this.lang === "de" ? "Keine User-ID gefunden." : "No user ID found.",
        );
        return;
      }

      const ok = window.confirm(
        this.lang === "de"
          ? "Interview wirklich zurÃ¼cksetzen?"
          : "Do you really want to reset the interview?",
      );
      if (!ok) return;

      try {
        await axios.post(`${this.host}/resetConversation`, {
          client: "web",
          userid: userId,
        });

        // keep-alive caches views; hard reload guarantees a clean UI state.
        window.location.hash = "#/agent-chat";
        window.location.reload();
      } catch (e) {
        console.error("Reset failed:", e);
        alert(this.lang === "de" ? "Reset fehlgeschlagen." : "Reset failed.");
      }
    },
  },

  mounted() {
    this.loadUserLanguage();
    this.loadUserRole();
  },
});
</script>

<style scoped>
.chat-app {
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-app__view {
  flex: 1 1 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: auto;
  background: #faf8f3;
}

.tabs {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
}

.tab {
  margin-right: 12px;
  padding: 6px 10px;
  text-decoration: none;
  color: #333;
  border-bottom: 2px solid transparent;
  white-space: nowrap;
}

.tab.active {
  border-bottom: 2px solid #0d6efd;
  font-weight: 600;
}

.admin-lock-btn {
  opacity: 0.4;
  transition: opacity 0.2s;
}
.admin-lock-btn:hover {
  opacity: 1;
}

.admin-login-popup {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  z-index: 1000;
  background: #fff;
  border: 1px solid #dee2e6;
  border-radius: 6px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  min-width: 220px;
}

.admin-login-inner {
  padding: 14px;
}

.admin-login-title {
  font-size: 0.85rem;
  font-weight: 600;
  margin-bottom: 8px;
  color: #495057;
}

.admin-login-error {
  color: #dc3545;
  font-size: 0.8rem;
  margin-top: 4px;
  margin-bottom: 0;
}
<<<<<<< Updated upstream
/* ── Mobile responsive ─────────────────────────────────────── */
@media (max-width: 900px) {
  .tabs {
    overflow-x: auto;
    flex-wrap: nowrap;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
  }
  .tabs::-webkit-scrollbar {
    display: none;
  }
  .tab {
    white-space: nowrap;
    flex-shrink: 0;
    font-size: 0.82rem;
    padding: 6px 8px;
    margin-right: 6px;
  }
}
@media (max-width: 600px) {
  .tabs {
    gap: 0;
    overflow-x: auto;
    flex-wrap: nowrap;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
  }
  .tabs::-webkit-scrollbar {
    display: none;
  }
  .tab {
    margin-right: 8px;
    padding: 6px 8px;
    font-size: 0.82rem;
    white-space: nowrap;
    flex-shrink: 0;
  }
=======

/* ── Mobile nav ──────────────────────────────────────── */
.mobile-menu-wrapper {
  position: relative;
}

.mobile-nav-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  z-index: 1050;
  background: #fff;
  border: 1px solid #dee2e6;
  border-radius: 6px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.13);
  min-width: 200px;
  overflow: hidden;
}

.mobile-nav-item {
  display: block;
  padding: 10px 16px;
  color: #333;
  text-decoration: none;
  font-size: 0.9rem;
  border-bottom: 1px solid #f0f0f0;
  transition: background 0.15s;
}

.mobile-nav-item:last-child {
  border-bottom: none;
}

.mobile-nav-item:hover {
  background: #f8f9fa;
}

.mobile-nav-active {
  font-weight: 700;
  background: #f0f4ff;
  color: #0d6efd;
>>>>>>> Stashed changes
}
</style>


