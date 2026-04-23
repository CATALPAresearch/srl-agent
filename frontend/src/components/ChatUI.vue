<template>
  <div
    id="chat"
    class="chat-ui container-fluid px-0"
    role="region"
    :aria-label="translatedTitle"
  >
    <!-- Document header -->
    <header class="chat-doc-header">
      <div>
        <div hidden class="chat-eyebrow">
          {{ eyebrow }}
        </div>
        <h2 class="chat-title">{{ translatedTitle }}</h2>
      </div>
    </header>

    <!-- Transcript body -->
    <div
      class="chat-transcript"
      ref="messageList"
      role="log"
      aria-live="polite"
      aria-relevant="additions"
    >
      <div v-for="(m, index) in messages" :key="m.id || index" class="chat-row">
        <!-- Author column -->
        <div class="chat-author-col">
          <span
            class="chat-author-chip"
            :class="m.author == 'bot' ? 'is-bot' : 'is-user'"
          >
            {{ m.author == "bot" ? "Agent" : lang === "de" ? "Du" : "You" }}
          </span>
          <div class="chat-author-time" v-if="m.id">
            #{{ String(m.id).padStart(2, "0") }}
          </div>
        </div>

        <!-- Body column -->
        <article
          class="chat-body"
          :class="m.author == 'bot' ? 'is-bot' : 'is-user'"
        >
          <!-- Streaming / loading state -->
          <div
            v-if="m.message == ''"
            class="chat-typing"
            role="status"
            aria-live="polite"
            aria-atomic="true"
          >
            <span class="chat-dots" aria-hidden="true">
              <i></i><i></i><i></i>
            </span>
            <span class="chat-typing-label">{{
              lang === "de" ? "Agent antwortet" : "agent composing reply"
            }}</span>
            <span class="sr-only">{{
              lang === "de" ? "Nachricht wird geladen" : "Loading message"
            }}</span>
          </div>
          <!-- Message body (renders empty string when loading) -->
          <VueShowdown
            style="display: inline"
            :markdown="m.message"
            flavor="github"
            :options="{ emoji: true }"
          />

          <div v-if="m.isSurveyCTA" class="chat-inline-cta">
            <button
              type="button"
              class="chat-send"
              @click="$emit('openSurvey')"
            >
              <span>{{ lang === "de" ? "Zur Umfrage" : "Open Survey" }}</span>
              <font-awesome-icon icon="arrow-up" aria-hidden="true" />
            </button>
          </div>

          <div v-if="m.isResultsCTA" class="chat-inline-cta">
            <button
              type="button"
              class="chat-send"
              @click="$emit('openResults')"
            >
              <span>{{
                lang === "de" ? "Zu den Ergebnissen" : "Open Results"
              }}</span>
              <font-awesome-icon icon="arrow-up" aria-hidden="true" />
            </button>
          </div>

          <!-- Bot message actions -->
          <div v-if="m.author == 'bot' && m.message != ''" class="chat-actions">
            <button
              type="button"
              class="chat-action"
              :aria-label="lang === 'de' ? 'Antwort kopieren' : 'Copy response'"
              :title="lang === 'de' ? 'Kopieren' : 'Copy'"
              v-if="!copiedIndex || copiedIndex !== index"
              @click="copyMessageToClipboard(m.message, index)"
            >
              <font-awesome-icon icon="copy" aria-hidden="true" />
              <span hidden>{{ lang === "de" ? "Kopieren" : "Copy" }}</span>
            </button>
            <span v-else class="chat-action is-done" aria-live="assertive">
              <font-awesome-icon icon="check" aria-hidden="true" />
              <span class="sr-only">{{
                lang === "de" ? "Nachricht wurde kopiert" : "Message copied"
              }}</span>
              <span>{{ lang === "de" ? "Kopiert" : "Copied" }}</span>
            </span>
            <button
              type="button"
              class="chat-action"
              :aria-label="
                lang === 'de' ? 'Antwort positiv bewerten' : 'Rate helpful'
              "
              :title="lang === 'de' ? 'Hilfreich' : 'Helpful'"
              @click="sendRating('up', index)"
            >
              <font-awesome-icon icon="thumbs-up" aria-hidden="true" />
              <span hidden>{{ lang === "de" ? "Hilfreich" : "Helpful" }}</span>
            </button>
            <button
              type="button"
              class="chat-action"
              :aria-label="
                lang === 'de' ? 'Antwort negativ bewerten' : 'Rate not helpful'
              "
              :title="lang === 'de' ? 'Nicht hilfreich' : 'Not helpful'"
              @click="sendRating('down', index)"
            >
              <font-awesome-icon icon="thumbs-down" aria-hidden="true" />
              <span hidden>{{
                lang === "de" ? "Nicht hilfreich" : "Unhelpful"
              }}</span>
            </button>
          </div>
        </article>
      </div>
    </div>

    <!-- Composer -->
    <fieldset class="chat-composer">
      <legend class="sr-only">
        {{ lang === "de" ? "Neue Nachricht schreiben" : "Write a message" }}
      </legend>
      <div class="chat-composer-row">
        <div class="chat-author-col chat-author-col--input">
          <span class="chat-author-chip is-user">{{
            lang === "de" ? "Du" : "You"
          }}</span>
        </div>
        <div class="chat-input-wrap">
          <label for="chatTextarea" class="sr-only">
            {{ lang === "de" ? "Gib deine Frage ein" : "Type your question" }}
          </label>
          <textarea
            id="chatTextarea"
            ref="chatTextarea"
            class="chat-textarea"
            v-model="chat_message"
            @keydown.enter.exact.prevent="handleEnter"
            @keydown.enter.shift.exact="() => {}"
            @input="resizeTextarea"
            :placeholder="
              lang === 'de' ? 'Deine Antwort…' : 'Type your response…'
            "
            rows="1"
            :aria-label="lang === 'de' ? 'Deine Antwort' : 'Your response'"
          />
          <div class="chat-input-actions">
            <button
              type="button"
              class="chat-ghost"
              :aria-label="lang === 'de' ? 'Spracheingabe' : 'Voice input'"
              :title="lang === 'de' ? 'Sprache' : 'Voice'"
              @click="$emit('voiceInput')"
            >
              <font-awesome-icon icon="microphone" aria-hidden="true" />
            </button>
            <button
              type="button"
              class="chat-send"
              @click="handleChatMessage"
              :disabled="chat_message.length == 0 || is_loading"
              :aria-label="lang === 'de' ? 'Antwort senden' : 'Send response'"
              :title="lang === 'de' ? 'Senden ↵' : 'Send ↵'"
            >
              <span>{{ lang === "de" ? "Senden" : "Send" }}</span>
              <font-awesome-icon icon="arrow-up" aria-hidden="true" />
            </button>
          </div>
        </div>
      </div>
    </fieldset>
  </div>
</template>

<script lang="ts">
import Vue from "vue";
import { mapGetters, mapState } from "vuex";
import Communication from "../classes/communication";
import { VueShowdown } from "vue-showdown";

export default Vue.extend({
  name: "ChatUI",
  props: {
    messages: {
      type: Array,
      default: () => [],
    },
    is_loading: {
      type: Boolean,
      default: false,
    },
    title: {
      type: String,
      default: "Learning Strategies Interview",
    },
    eyebrow: {
      type: String,
      default: "Transcript · Session",
    },
  },
  data() {
    return {
      chat_message: "",
      error_msg: "",
      copied: false,
      copiedIndex: null,
      scrollTimers: [],
    };
  },
  components: {
    VueShowdown: VueShowdown,
  },
  computed: {
    ...mapState(["strings"]),
    lang() {
      return this.$store.getters.getLanguage || "de";
    },
    translatedTitle() {
      if (
        this.title.includes("Learning Strategies Interview") ||
        this.title === "Learning Strategies Interview"
      ) {
        return this.lang === "de"
          ? "Interview zu Lernstrategien"
          : "Learning Strategies Interview";
      }
      return this.title;
    },
    today() {
      const d = new Date();
      return d.toISOString().slice(0, 10);
    },
    now() {
      const d = new Date();
      return d.toTimeString().slice(0, 5);
    },
  },
  mounted() {
    this.scrollTranscriptToBottom();
  },
  beforeDestroy() {
    this.clearScrollTimers();
  },
  updated() {
    this.scrollTranscriptToBottom();
  },
  watch: {
    messages: {
      deep: true,
      handler() {
        this.scrollTranscriptToBottom();
      },
    },
    is_loading() {
      this.scrollTranscriptToBottom();
    },
  },
  methods: {
    ...mapGetters({
      //rag_webservice_host: 'getRAGWebserviceHost',
    }),
    handleEnter(event) {
      if (event.shiftKey) {
        return;
      }
      this.handleChatMessage();
    },
    handleChatMessage() {
      if (!this.chat_message || this.chat_message.length === 0) return;
      this.$emit("requestChatResponse", this.chat_message);
      this.chat_message = ""; // reset input field
      this.scrollTranscriptToBottom();
      this.$nextTick(() => {
        const ta = this.$refs.chatTextarea;
        if (ta) {
          ta.style.height = "auto";
          ta.focus();
        }
      });
    },
    resizeTextarea() {
      const textarea = this.$refs.chatTextarea;
      if (!textarea) return;
      textarea.style.height = "auto"; // Reset height
      textarea.style.height = textarea.scrollHeight + "px"; // Set height dynamically
    },
    copyMessageToClipboard(text, message_index) {
      const _this = this;
      navigator.clipboard
        .writeText(text)
        .then(() => {
          this.copied = true;
          this.copiedIndex = message_index;
          setTimeout(() => {
            this.copied = false;
            this.copiedIndex = null;
          }, 2000);
        })
        .catch((err) => {
          console.error("Failed to copy:", err);
        });
      Communication.webservice("triggerEvent", {
        cmid: _this.$store.getters.getCMID,
        action: "copy_response",
        value: JSON.stringify({ copied: text, index: message_index }),
      });
    },
    sendRating(rating, message_index) {
      const _this = this;
      const params = {
        request: this.messages[message_index - 1],
        response: this.messages[message_index],
        rating: rating,
      };
      // Note: preserving original action-name logic from previous version.
      Communication.webservice("triggerEvent", {
        cmid: _this.$store.getters.getCMID,
        action: "rate_response_" + rating == "up" ? "positive" : "negative",
        value: JSON.stringify({ index: message_index, rating, params }),
      });
    },
    clearScrollTimers() {
      this.scrollTimers.forEach((timerId) => clearTimeout(timerId));
      this.scrollTimers = [];
    },
    applyScrollToBottom() {
      const transcriptEl = this.$refs.messageList;
      if (transcriptEl) {
        transcriptEl.scrollTop = transcriptEl.scrollHeight;
      }

      const appViewEl = this.$el ? this.$el.closest(".chat-app__view") : null;
      if (appViewEl) {
        appViewEl.scrollTop = appViewEl.scrollHeight;
      }

      const root = document.scrollingElement || document.documentElement;
      if (root) {
        root.scrollTop = root.scrollHeight;
      }
    },
    scrollTranscriptToBottom() {
      this.clearScrollTimers();
      this.$nextTick(() => {
        this.applyScrollToBottom();

        // Repeat shortly after render because markdown/typing nodes can change height asynchronously.
        const t1 = setTimeout(() => this.applyScrollToBottom(), 40);
        const t2 = setTimeout(() => this.applyScrollToBottom(), 120);
        const t3 = setTimeout(() => this.applyScrollToBottom(), 240);
        this.scrollTimers.push(t1, t2, t3);
      });
    },
  },
});
</script>

<style>
/* ChatUI styles — intentionally not scoped to style VueShowdown rendered content */
/* -----------------------------------------------------------*/
/* Accessibility */
#chat .sr-only {
  position: absolute;
  left: -9999px;
  width: 1px;
  height: 1px;
  overflow: hidden;
}

/* -------------------------------------------------------------
 * Layout root
 * -----------------------------------------------------------*/
#chat.chat-ui {
  flex: 1 1 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;

  color: #1f1d1a;
  font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui,
    sans-serif;
  background: #fff;
}

/* -------------------------------------------------------------
 * Document header
 * -----------------------------------------------------------*/
#chat .chat-doc-header {
  max-width: 760px;
  width: 100%;
  margin: 0 auto;
  padding: 24px 24px 14px;
  border-bottom: 1px solid #1f1d1a;
  background: #fff;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  flex-shrink: 0;
}
#chat .chat-eyebrow {
  font-size: 11px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: #7d7575;
  margin-bottom: 6px;
}
#chat .chat-title {
  font-family: "Source Serif 4", Georgia, "Times New Roman", serif;
  font-size: 26px;
  font-weight: 500;
  letter-spacing: -0.3px;
  margin: 0;
  line-height: 1.25;
}
#chat .chat-meta {
  font-size: 11px;
  color: #a19e99;
  text-align: right;
  line-height: 1.5;
  white-space: nowrap;
}

/* -------------------------------------------------------------
 * Transcript
 * -----------------------------------------------------------*/
#chat .chat-transcript {
  flex: 1 1 0;
  min-height: 0;
  overflow-y: auto;
  padding: 28px 24px 20px;
  background: #fff;
}
#chat .chat-row {
  max-width: 760px;
  width: 100%;
  margin: 0 auto 32px;
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: 20px;
}
#chat .chat-row:last-child {
  margin-bottom: 8px;
}

#chat .chat-author-col {
  padding-top: 4px;
  padding-right: 14px;
  border-right: 1px solid #e4e0d6;
  text-align: right;
  font-size: 10px;
  letter-spacing: 1.8px;
  text-transform: uppercase;
  font-weight: 700;
}
#chat .chat-author-col--input {
  padding-top: 4px;
}
#chat .chat-author-chip {
  display: inline-block;
  padding: 3px 8px;
  border-radius: 3px;
  line-height: 1.3;
}
#chat .chat-author-chip.is-bot {
  background: #1f1d1a;
  color: #fff;
}
#chat .chat-author-chip.is-user {
  background: #d9edf7;
  color: #0d5a8a;
}
#chat .chat-author-time {
  margin-top: 6px;
  color: #b5b0a8;
  font-weight: 500;
  font-size: 9px;
  letter-spacing: 1px;
}

/* -------------------------------------------------------------
 * Message body (no bubbles — document style)
 * -----------------------------------------------------------*/
#chat .chat-body {
  color: #1f1d1a;
  line-height: 1.65;
  word-break: break-word;
  font-family: inherit;
  font-size: 15px;
}
#chat .chat-body.is-bot {
  font-family: inherit;
  font-size: 15px;
}
#chat .chat-body p {
  margin: 0 0 0.6em;
}
#chat .chat-body p:last-child {
  margin-bottom: 0;
}
#chat .chat-body code {
  background: rgba(0, 0, 0, 0.06);
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 0.92em;
}
#chat .chat-body pre {
  background: rgba(0, 0, 0, 0.04);
  padding: 10px 12px;
  border-radius: 6px;
  overflow-x: auto;
  font-size: 0.9em;
}
#chat .chat-body a {
  color: #0d6efd;
}

/* Typing state */
#chat .chat-typing {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: #7d7575;
  font-size: 13px;
  font-style: italic;
  font-family: "Inter", system-ui, sans-serif;
}
#chat .chat-dots {
  display: inline-flex;
  gap: 4px;
  align-items: center;
}
#chat .chat-dots i {
  width: 6px;
  height: 6px;
  border-radius: 99px;
  background: #0d6efd;
  opacity: 0.35;
  animation: chat-blink 1.2s infinite ease-in-out;
}
#chat .chat-dots i:nth-child(2) {
  animation-delay: 0.18s;
}
#chat .chat-dots i:nth-child(3) {
  animation-delay: 0.36s;
}
@keyframes chat-blink {
  0%,
  60%,
  100% {
    opacity: 0.25;
    transform: translateY(0);
  }
  30% {
    opacity: 1;
    transform: translateY(-2px);
  }
}

/* -------------------------------------------------------------
 * Actions row (hover-reveal)
 * -----------------------------------------------------------*/
#chat .chat-actions {
  margin-top: 10px;
  display: flex;
  gap: 14px;
  align-items: center;
  opacity: 0;
  transition: opacity 0.15s;
  pointer-events: none;
}
#chat .chat-body.is-bot:hover .chat-actions,
#chat .chat-body.is-bot:focus-within .chat-actions {
  opacity: 1;
  pointer-events: auto;
}
#chat .chat-action {
  border: none;
  background: transparent;
  color: #8a8580;
  padding: 0;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  letter-spacing: 0.3px;
  text-transform: uppercase;
  font-family: inherit;
  font-weight: 600;
  transition: color 0.12s;
}
#chat .chat-action:hover {
  color: #1f1d1a;
}
#chat .chat-action.is-done {
  color: #0d6efd;
  cursor: default;
}

/* -------------------------------------------------------------
 * Composer
 * -----------------------------------------------------------*/
#chat .chat-composer {
  border: 0;
  margin: 0;
  padding: 16px 24px 24px 6px;
  background: #faf8f3;
  border-top: 1px solid #ecebe7;
  flex-shrink: 0;
  max-height: 100%;
  min-height: 85px;
}
#chat .chat-composer-row {
  max-width: 760px;
  width: 100%;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: 20px;
}

#chat .chat-input-wrap {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  border-bottom: 1.5px solid #1f1d1a;
  padding-bottom: 8px;
  transition: border-color 0.15s;
}
#chat .chat-input-wrap:focus-within {
  border-bottom-color: #0d6efd;
}
#chat .chat-textarea {
  flex: 1 1 auto;
  min-height: 28px;
  max-height: 200px;
  width: 100%;
  border: none;
  outline: none;
  resize: none;
  background: transparent;
  color: #1f1d1a;
  font-size: 15px;
  font-family: inherit;
  line-height: 1.6;
  padding: 4px 0;
  overflow-y: auto;
}
#chat .chat-textarea::placeholder {
  color: #a19e99;
}

#chat .chat-input-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
#chat .chat-ghost {
  border: none;
  background: transparent;
  color: #7d7575;
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border-radius: 6px;
  transition: background 0.12s, color 0.12s;
}
#chat .chat-ghost:hover {
  background: #ecebe7;
  color: #1f1d1a;
}
#chat .chat-send {
  border: none;
  background: transparent;
  color: #0d6efd;
  padding: 6px 10px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: inherit;
  font-weight: 700;
  font-size: 12px;
  letter-spacing: 0.8px;
  text-transform: uppercase;
  border-radius: 6px;
  transition: background 0.12s, color 0.12s;
}
#chat .chat-send:hover:not(:disabled) {
  background: rgba(13, 110, 253, 0.08);
}
#chat .chat-send:disabled {
  color: #c9c4bc;
  cursor: not-allowed;
}

#chat .chat-inline-cta {
  margin-top: 12px;
}

/* -------------------------------------------------------------
 * Responsive — collapse the author gutter on small screens
 * -----------------------------------------------------------*/
@media (max-width: 640px) {
  #chat .chat-row,
  #chat .chat-composer-row {
    grid-template-columns: 1fr;
    gap: 6px;
  }
  #chat .chat-author-col {
    border-right: none;
    padding-right: 0;
    text-align: left;
  }
  #chat .chat-author-time {
    display: inline-block;
    margin-left: 8px;
    margin-top: 0;
  }
  #chat .chat-doc-header {
    flex-direction: column;
    align-items: flex-start;
  }
  #chat .chat-meta {
    text-align: left;
  }
}

/* Markdown wrapper styles */
#chat .chat-markdown {
  display: block;
  visibility: visible;
  opacity: 1;
}
#chat .chat-markdown * {
  visibility: visible;
  opacity: 1;
  color: inherit;
}
</style>
