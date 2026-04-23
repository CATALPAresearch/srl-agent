<template>
  <div class="chat-app">
    <div class="header-bar d-flex align-items-center px-2 py-1">
      <nav class="tabs flex-grow-1">
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
        <router-link to="/protocols" class="tab" active-class="active">
          Protocols
        </router-link>
        <router-link
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

      <!-- Role switcher (testing only) -->
      <div class="d-flex align-items-center mr-3" title="Switch role (testing)">
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
        type="button"
        class="btn btn-sm btn-outline-danger ml-2"
        @click="resetInterview"
      >
        {{ lang === "de" ? "Reset" : "Reset" }}
      </button>
    </div>
    <keep-alive>
      <router-view class="chat-app__view" :lang="lang" />
    </keep-alive>
  </div>
</template>

<script>
import Vue from "vue";
import axios from "axios";

export default Vue.extend({
  name: "ChatApp",

  data() {
    return {
      host: "http://localhost:5000",
    };
  },

  computed: {
    lang() {
      return this.$store.getters.getLanguage;
    },
    role() {
      return this.$store.getters.getRole;
    },
  },

  methods: {
    setLanguage(lang) {
      this.$store.commit("setLanguage", lang);
    },

    setRole(role) {
      this.$store.commit("setRole", role);
    },

    async loadUserLanguage() {
      const userId = this.$store.getters.getUser;
      if (!userId) return;
      try {
        const res = await axios.get(`${this.host}/user_language/`, {
          params: { userid: userId, client: "standalone" },
        });
        if (res.data) this.$store.commit("setLanguage", res.data);
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
          ? "Interview wirklich zurücksetzen?"
          : "Do you really want to reset the interview?",
      );
      if (!ok) return;

      try {
        const apiBase = this.$store.getters.getApiHost || this.host;
        await axios.post(`${apiBase}/resetConversation`, {
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
</style>
