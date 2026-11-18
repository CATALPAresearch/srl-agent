<template>
  <div id="container" class="content agent-chat" role="main">
    <div class="chat-header w100">
      <h3 class="d-flex justify-content-betweenx xalign-items-center mb-3">
        <span id="chat-title" hidden>Agent-Chat</span>
      </h3>
    </div>

    <button
      hidden
      v-if="!chatStarted"
      @click="startChat"
      class="btn btn-primary start-btn w-25"
    >
      Beginne das Interview
    </button>
    <div v-if="is_loading && messages.length === 0" class="text-center my-3">
      <font-awesome-icon
        class="fa-spin fa-2x"
        icon="spinner"
        aria-hidden="true"
      />
      <span class="sr-only">Chat wird gestartet</span>
    </div>
    <ChatUI
      v-if="chatStarted"
      :messages="messages"
      :is_loading="is_loading"
      @requestChatResponse="requestAgentChat"
      @openSurvey="openSurvey"
      @openResults="openResults"
      aria-labelledby="chat-title"
    />
  </div>
</template>

<script>
import axios from "axios";
import { defineComponent } from "vue";
import ChatUI from "./ChatUI.vue";

export default defineComponent({
  name: "AgentChat",
  components: {
    ChatUI: ChatUI,
  },
  data() {
    return {
      messages: [],
      messageId: 0,
      error_msg: "",
      is_loading: false,
      chatStarted: false,
      userInput: "",
      tabHiddenAt: null,
      mouseTraceBuffer: [],
      mouseSessionId: null,
      mouseTraceInterval: null,
      mouseSampleInterval: null,
      lastMouseX: undefined,
      lastMouseY: undefined,
      summaryPollInterval: null,
      summaryPollAttempts: 0,
      surveyReturnBaseline: null,
      postSurveyInfoActive: false,
      visibilityHandler: null,
      mouseMoveHandler: null,
    };
  },

  computed: {
    host() {
      return this.$store.getters.getApiHost;
    },
  },

  mounted() {
    this.setupTabVisibilityTracking();
    this.setupMouseTracking();
    this.restoreOrStart();
  },

  activated() {
    // AgentChat is cached via keep-alive. When returning from survey,
    // mounted() is not called again, so we must explicitly re-run restore flow.
    if (this.isReturningFromSurvey()) {
      this.restoreOrStart();
    } else if (localStorage.getItem("srl_fresh_start") === "1") {
      localStorage.removeItem("srl_fresh_start");
      this.messages = [];
      this.chatStarted = false;
      this.restoreOrStart();
    }
  },

  methods: {
    getNextMessageId: function () {
      this.messageId++;
      return this.messageId;
    },

    getPostSurveyInfoMessage: function () {
      const lang = this.$store.getters.getLanguage || "de";
      return lang === "de"
        ? "Vielen Dank fuers Ausfuellen des Fragebogens. Ich erstelle gerade deine Zusammenfassung und zeige sie hier automatisch an, sobald sie fertig ist."
        : "Thank you for filling out the survey. I am generating your summary now and will show it here automatically as soon as it is ready.";
    },

    // Limits enforced by the server (and nginx) for /reply, shown in the chat.
    replyErrorMessage: function (error) {
      const de = (this.$store.getters.getLanguage || "de") === "de";
      const res = error && error.response;
      const code = res && res.data && res.data.error;
      const limit = res && res.data && res.data.limit;
      if (code === "message_too_long") {
        return de
          ? `Deine Nachricht ist zu lang (höchstens ${limit} Zeichen). Bitte kürze sie und sende sie erneut.`
          : `Your message is too long (at most ${limit} characters). Please shorten it and send it again.`;
      }
      if (code === "interview_quota_reached") {
        return de
          ? `Für dieses Interview ist die Höchstzahl von ${limit} Nachrichten erreicht. Du kannst über die Startseite ein neues Interview beginnen.`
          : `This interview has reached the maximum of ${limit} messages. You can start a new interview from the start page.`;
      }
      if (res && res.status === 429) {
        return de
          ? "Du hast gerade sehr viele Nachrichten gesendet (höchstens 10 pro Minute). Bitte warte einen Moment und sende deine Nachricht dann erneut."
          : "You have sent a lot of messages just now (at most 10 per minute). Please wait a moment and send your message again.";
      }
      return de
        ? "Es konnte gerade keine Antwort erzeugt werden. Bitte versuche es erneut."
        : "Unable to get a response right now. Please try again.";
    },

    getPendingSummaryMessage: function () {
      const lang = this.$store.getters.getLanguage || "de";
      return lang === "de"
        ? "Das Interview ist abgeschlossen. Bitte fuelle jetzt den Fragebogen aus. Deine Zusammenfassung wird im Hintergrund erstellt."
        : "The interview is complete. Please fill out the survey now. Your summary is being generated in the background.";
    },

    isPendingSummaryMessage: function (text) {
      if (!text || typeof text !== "string") return false;
      const normalized = text.toLowerCase();
      return (
        normalized.includes("summary is being generated in the background") ||
        normalized.includes("zusammenfassung wird im hintergrund erstellt")
      );
    },

    hasPendingSummaryInHistory: function (history) {
      return Array.isArray(history)
        ? history.some(
            (m) =>
              m.author === "bot" && this.isPendingSummaryMessage(m.message),
          )
        : false;
    },

    shouldActivatePostSurveyFlow: function (history) {
      const fromQuery = this.$route.query.fromSurvey === "1";
      const fromStorage = localStorage.getItem("srl_from_survey") === "1";
      return (
        fromQuery || fromStorage || this.hasPendingSummaryInHistory(history)
      );
    },

    isReturningFromSurvey: function () {
      return (
        this.$route.query.fromSurvey === "1" ||
        localStorage.getItem("srl_from_survey") === "1"
      );
    },

    clearPostSurveyReturnFlag: function () {
      localStorage.removeItem("srl_from_survey");
      if (this.$route.query.fromSurvey === "1") {
        this.$router
          .replace({ path: "/agent-chat", query: {} })
          .catch(() => {});
      }
    },

    markSummaryResultsCTA: function (history) {
      if (!Array.isArray(history) || history.length === 0) return history;
      const marked = history.map((m) => ({ ...m, isResultsCTA: false }));
      let lastBotIdx = -1;
      for (let i = marked.length - 1; i >= 0; i--) {
        if (
          marked[i].author === "bot" &&
          typeof marked[i].message === "string"
        ) {
          lastBotIdx = i;
          break;
        }
      }
      if (lastBotIdx === -1) return marked;

      const lastBotMsg = (marked[lastBotIdx].message || "").trim();
      if (!lastBotMsg || this.isPendingSummaryMessage(lastBotMsg)) {
        return marked;
      }

      const pendingExists = marked.some(
        (m) => m.author === "bot" && this.isPendingSummaryMessage(m.message),
      );
      if (pendingExists || this.postSurveyInfoActive) {
        marked[lastBotIdx].isResultsCTA = true;
        marked[lastBotIdx].isSurveyCTA = false; // survey is done; replace survey button with results button
      }
      return marked;
    },

    applyConversationHistory: function (history) {
      this.messages = this.markSummaryResultsCTA(history);
      this.messageId = history.reduce((max, m) => Math.max(max, m.id || 0), 0);
      this.chatStarted = true;

      if (
        this.postSurveyInfoActive &&
        history.length <= this.surveyReturnBaseline
      ) {
        this.messages.push({
          author: "bot",
          message: this.getPostSurveyInfoMessage(),
          id: this.getNextMessageId(),
          isPostSurveyInfo: true,
        });
      }
    },

    refreshConversation: async function () {
      const res = await axios.get(this.host + "/conversation", {
        params: { userid: this.$store.getters.getUser, client: "web" },
      });
      const history = res.data && res.data.messages;
      if (history && history.length > 0) {
        this.applyConversationHistory(history);
        return history;
      }
      return [];
    },

    stopSummaryPolling: function () {
      if (this.summaryPollInterval) {
        clearInterval(this.summaryPollInterval);
        this.summaryPollInterval = null;
      }
      this.summaryPollAttempts = 0;
      this.postSurveyInfoActive = false;
      this.surveyReturnBaseline = null;
    },

    startSummaryPolling: function () {
      if (this.summaryPollInterval) {
        clearInterval(this.summaryPollInterval);
        this.summaryPollInterval = null;
      }
      this.postSurveyInfoActive = true;
      this.summaryPollAttempts = 0;

      const poll = async () => {
        this.summaryPollAttempts += 1;
        try {
          const history = await this.refreshConversation();
          const hasUpdate =
            this.surveyReturnBaseline !== null &&
            history.length > this.surveyReturnBaseline;
          if (hasUpdate || this.summaryPollAttempts >= 12) {
            this.stopSummaryPolling();
            return;
          }
        } catch (e) {
          console.warn("Summary polling failed:", e);
          if (this.summaryPollAttempts >= 12) {
            this.stopSummaryPolling();
            return;
          }
        }
        this.summaryPollInterval = setTimeout(poll, 3000);
      };

      this.summaryPollInterval = setTimeout(poll, 3000);
    },

    restoreOrStart: async function () {
      this.is_loading = true;
      const returningFromSurvey = this.isReturningFromSurvey();
      try {
        const history = await this.refreshConversation();
        if (history && history.length > 0) {
          if (this.shouldActivatePostSurveyFlow(history)) {
            const hasPending = this.hasPendingSummaryInHistory(history);
            if (hasPending) {
              // Summary not ready yet — show pending UI and poll for it.
              this.surveyReturnBaseline = history.length;
              this.postSurveyInfoActive = true;
              this.applyConversationHistory(history);
              this.startSummaryPolling();
            } else {
              // Summary already present in history (generated synchronously).
              // Show it directly with a results CTA — no polling needed.
              this.postSurveyInfoActive = true; // enables CTA marking
              this.surveyReturnBaseline = history.length - 1; // prevents info-message injection
              this.applyConversationHistory(history);
              this.postSurveyInfoActive = false;
            }
            this.clearPostSurveyReturnFlag();
          }
          this.is_loading = false;
          return;
        }
      } catch (e) {
        console.warn("Could not restore conversation:", e);
      }

      if (returningFromSurvey) {
        // No history yet — start a fresh chat (edge case).
        this.chatStarted = true;
        this.messages = [];
        this.clearPostSurveyReturnFlag();
        this.is_loading = false;
        this.startChat();
        return;
      }

      this.startChat();
    },

    startChat: async function () {
      console.log("Started Chat");
      this.is_loading = true;
      let _this = this;
      const selectedLanguage = this.$store.getters.getLanguage || "de";
      await axios
        .post(this.host + "/startConversation", {
          language: selectedLanguage,
          client: "web",
          userid: this.$store.getters.getUser,
        })
        .then((response) => {
          _this.is_loading = false;
          console.log("/startConversation: ", response);
          _this.messages.push({
            message:
              (response.data && response.data.message) || "Chat started!",
            author: "bot",
            id: _this.getNextMessageId(),
          });
          _this.chatStarted = true;
        })
        .catch((error) => {
          _this.is_loading = false;
          console.error("Error starting chat:", error);
        });
    },

    requestAgentChat: async function (message) {
      this.is_loading = true;

      //@ts-ignore
      let new_message = {
        author: "user",
        message: message,
        id: this.getNextMessageId(),
      };
      this.messages.push(new_message);

      const bot_placeholder = {
        author: "bot",
        message: "",
        id: this.getNextMessageId(),
      };
      const bot_pos = this.messages.push(bot_placeholder) - 1;

      await axios
        .post(this.host + "/reply", {
          message: message,
          client: "web",
          userid: this.$store.getters.getUser,
        })
        .then((response) => {
          this.is_loading = false;
          console.log("/reply: ", response);
          this.messages[bot_pos] = {
            author: "bot",
            message:
              response.data && typeof response.data.message === "string"
                ? response.data.message
                : typeof response.data === "string"
                ? response.data
                : "",
            id: bot_placeholder.id,
            isSurveyCTA: Boolean(response.data && response.data.complete),
            // Results CTA is never shown immediately after interview completion —
            // only after the user has completed the survey and returned here.
            isResultsCTA: false,
          };
          this.wait_video_generation = false;
        })
        .catch((error) => {
          this.is_loading = false;
          console.error("Error sending message:", error);
          this.messages[bot_pos] = {
            author: "bot",
            message: this.replyErrorMessage(error),
            id: bot_placeholder.id,
          };
        });
    },

    setupTabVisibilityTracking: function () {
      this.visibilityHandler = () => {
        const event = document.hidden ? "tab_hidden" : "tab_visible";
        const timestamp = Math.floor(Date.now() / 1000);

        if (document.hidden) {
          this.tabHiddenAt = timestamp;
        }

        axios
          .post(this.host + "/log/tab_event", {
            userid: this.$store.getters.getUser,
            client: "web",
            event: event,
            timestamp: timestamp,
          })
          .catch(function (error) {
            console.warn("Tab event logging failed:", error);
          });

        console.log("Tab visibility changed:", event, "at", timestamp);
      };
      document.addEventListener("visibilitychange", this.visibilityHandler);
    },

    openSurvey() {
      this.$router.push("/survey");
    },

    openResults() {
      this.$router.push("/results");
    },

    setupMouseTracking: function () {
      const _this = this;
      this.mouseSessionId = "session_" + Date.now();

      // Sample mouse position every 2 seconds
      this.mouseSampleInterval = setInterval(function () {
        if (_this.lastMouseX !== undefined && _this.lastMouseY !== undefined) {
          _this.mouseTraceBuffer.push({
            x: _this.lastMouseX,
            y: _this.lastMouseY,
            page_width: window.innerWidth,
            page_height: window.innerHeight,
            timestamp: Math.floor(Date.now() / 1000),
          });
        }
      }, 2000);

      // Send batch every 10 seconds
      this.mouseTraceInterval = setInterval(function () {
        if (_this.mouseTraceBuffer.length > 0) {
          const batch = _this.mouseTraceBuffer.splice(0);
          axios
            .post(_this.host + "/log/mouse_traces", {
              userid: _this.$store.getters.getUser,
              client: "web",
              session_id: _this.mouseSessionId,
              traces: batch,
            })
            .catch(function (error) {
              console.warn("Mouse trace logging failed:", error);
            });
        }
      }, 10000);

      // Track mouse position
      this.mouseMoveHandler = (e) => {
        this.lastMouseX = e.clientX;
        this.lastMouseY = e.clientY;
      };
      document.addEventListener("mousemove", this.mouseMoveHandler);
    },

    stopMouseTracking: function () {
      if (this.mouseTraceInterval) clearInterval(this.mouseTraceInterval);
      if (this.mouseSampleInterval) clearInterval(this.mouseSampleInterval);
    },
  },

  beforeUnmount() {
    this.stopSummaryPolling();
    this.stopMouseTracking();
    if (this.visibilityHandler) {
      document.removeEventListener("visibilitychange", this.visibilityHandler);
    }
    if (this.mouseMoveHandler) {
      document.removeEventListener("mousemove", this.mouseMoveHandler);
    }
  },
});
</script>

<style scoped>
.sr-only {
  position: absolute;
  left: -9999px;
  width: 1px;
  height: 1px;
  overflow: hidden;
}

.chat-widget {
  max-width: 400px;
  margin: auto;
  font-family: Arial, sans-serif;
}

.chat-container {
  border: 1px solid #ccc;
  padding: 10px;
  border-radius: 5px;
  background: #f9f9f9;
}

.messages {
  max-height: 300px;
  overflow-y: auto;
  padding: 10px;
  display: flex;
  flex-direction: column;
}

.user-message {
  align-self: flex-end;
  background-color: #007bff;
  color: white;
  padding: 8px;
  border-radius: 10px;
  margin: 5px;
}

.server-message {
  align-self: flex-start;
  background-color: #e0e0e0;
  padding: 8px;
  border-radius: 10px;
  margin: 5px;
}

.chat-input {
  display: flex;
  margin-top: 10px;
}

.chat-input input {
  flex-grow: 1;
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 5px;
}

.chat-input button {
  padding: 8px 15px;
  margin-left: 5px;
  border: none;
  background-color: #28a745;
  color: white;
  cursor: pointer;
}

.agent-chat {
  flex: 1 1 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
</style>
