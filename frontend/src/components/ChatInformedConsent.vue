<template>
  <div
    v-if="
      $store.getters.getInformedConsentAgreement == 'none' ||
      $store.getters.getInformedConsentAgreement == 'no'
    "
    class="consent-overlay"
    role="dialog"
    aria-modal="true"
  >
    <div class="consent-dialog">

      <!-- Blue header with X -->
      <div class="consent-header">
        <h5 class="mb-0" v-if="lang === 'de'">Einwilligung zur Nutzung des Interview-Agenten</h5>
        <h5 class="mb-0" v-else>Consent to Use the Interview Agent</h5>
        <button
          class="consent-close-btn"
          @click="$store.commit('setInformedConsentAgreement', 'no')"
          :aria-label="lang === 'de' ? 'Schließen' : 'Close'"
        >&times;</button>
      </div>

      <!-- Body -->
      <div class="consent-body">

        <!-- ===== DEUTSCH ===== -->
        <template v-if="lang === 'de'">
          <div class="consent-sections">
            <section>
              <h6>Zweck</h6>
              <p>Der Interview-Agent dient der Ermittlung technischer und didaktischer
                Voraussetzungen für den Einsatz von Sprachmodellen im Lehr-Lern-Kontext,
                insbesondere zur Durchführung von Interviews zur Erfassung und Förderung
                der Selbstregulation.</p>
            </section>
            <section>
              <h6>Erfasste Daten</h6>
              <p>Erfasst werden Interaktionen (Klicks, Mausbewegungen, Tab-Wechsel,
                Texteingaben) sowie Fragen und Antworten der Sprachmodelle —
                ausschließlich in pseudonymisierter Form. Nach der Speicherung ist
                eine Zuordnung zu einer Person oder Moodle-Nutzer-ID nicht mehr möglich.
                Bitte geben Sie keine personenbezogenen Daten Dritter ein.</p>
            </section>
            <section>
              <h6>Verwendung</h6>
              <p>Die Daten dienen der Überwachung, Analyse und Verbesserung des
                technischen Betriebs und der Benutzerfreundlichkeit des Interview-Agenten
                und verbundener Dienste (z.&nbsp;B. KI:Connect LLM-Server) sowie der
                Beantwortung wissenschaftlicher Fragestellungen. Die Verarbeitung erfolgt
                auf Basis Ihrer freiwilligen Einwilligung (Art.&nbsp;6 Abs.&nbsp;1 lit.&nbsp;a DSGVO)
                ausschließlich auf Servern der FernUniversität in Hagen mit
                Open-Source-Sprachmodellen.</p>
            </section>
            <section>
              <h6>Rechte und Freiwilligkeit</h6>
              <p>Die Nutzung ist freiwillig (Opt-in); die Einwilligung kann jederzeit
                mit Wirkung für die Zukunft widerrufen werden. Lehrende können den
                Agenten über Moodle (LTI) oder als Web-Anwendung einsetzen und durch
                Löschung der Aktivität jederzeit deaktivieren. Eine Herausgabe oder
                Löschung einzelner Datensätze ist aufgrund der Pseudonymisierung
                technisch nicht möglich.</p>
            </section>
            <section class="consent-section-full">
              <h6>Verantwortlichkeiten</h6>
              <p>Verantwortlich ist die FernUniversität in Hagen, Universitätsstraße&nbsp;11,
                58097 Hagen. Bei Fragen wenden Sie sich an den
                <a href="mailto:datenschutzbeauftragter@fernuni-hagen.de">Behördlichen Datenschutzbeauftragten</a>
                oder den Leiter dieser Studie
                <a href="mailto:niels.seidel@fernuni-hagen.de">Dr.&nbsp;Niels Seidel</a>.</p>
            </section>
          </div>
        </template>

        <!-- ===== ENGLISH ===== -->
        <template v-else>
          <div class="consent-sections">
            <section>
              <h6>Purpose</h6>
              <p>The interview agent is used to determine the technical and didactic
                requirements for deploying language models in teaching and learning
                contexts, in particular for conducting interviews to assess and promote
                self-regulated learning.</p>
            </section>
            <section>
              <h6>Data Collected</h6>
              <p>We collect interactions (clicks, mouse movements, tab switches, text
                input) as well as questions and answers from the language models —
                exclusively in pseudonymised form. Once stored, it is no longer possible
                to link the data to an individual or Moodle user ID. Please do not enter
                any personal data of third parties.</p>
            </section>
            <section>
              <h6>Use of Data</h6>
              <p>The data is used to monitor, analyse and improve the technical operation
                and usability of the interview agent and related services (e.g. KI:Connect LLM
                server), as well as to answer research questions regarding AI-assisted
                teaching. Processing is based on your voluntary consent (Art.&nbsp;6(1)(a)
                GDPR) exclusively on FernUniversität in Hagen servers using open-source
                language models.</p>
            </section>
            <section>
              <h6>Rights and Voluntary Nature</h6>
              <p>Participation is voluntary (opt-in); consent may be withdrawn at any
                time with future effect. Instructors can deploy the agent via Moodle (LTI)
                or as a web application and deactivate it at any time. Disclosure or
                deletion of individual records is technically not possible due to
                pseudonymisation.</p>
            </section>
            <section class="consent-section-full">
              <h6>Responsibilities</h6>
              <p>The controller is FernUniversität in Hagen, Universitätsstraße&nbsp;11,
                58097 Hagen, Germany. Questions may be directed to the
                <a href="mailto:datenschutzbeauftragter@fernuni-hagen.de">Official Data Protection Officer</a>
                or the lead researcher
                <a href="mailto:niels.seidel@fernuni-hagen.de">Dr.&nbsp;Niels Seidel</a>.</p>
            </section>
          </div>
        </template>

      </div><!-- /consent-body -->

      <!-- Footer buttons -->
      <div class="consent-footer">
        <button
          type="button"
          @click="$store.commit('setInformedConsentAgreement', 'yes')"
          class="btn btn-primary"
          :aria-label="lang === 'de' ? 'Einwilligung erteilen' : 'Give consent'"
        >
          <template v-if="lang === 'de'">Ja, ich erteile die Einwilligung</template>
          <template v-else>Yes, I give my consent</template>
        </button>
        <button
          type="button"
          @click="$store.commit('setInformedConsentAgreement', 'no')"
          class="btn btn-outline-secondary"
          :aria-label="lang === 'de' ? 'Einwilligung ablehnen' : 'Decline consent'"
        >
          <template v-if="lang === 'de'">Nein, ich willige nicht ein</template>
          <template v-else>No, I do not consent</template>
        </button>
      </div>

    </div>
  </div>
</template>

<script>
import { defineComponent } from "vue";

export default defineComponent({
  name: "ChatInformedConsent",

  props: {
    lang: {
      type: String,
      default: "de",
    },
  },
});
</script>

<style scoped>
.consent-overlay {
  position: fixed;
  inset: 0;
  z-index: 1050;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
}

.consent-dialog {
  background: #fff;
  width: min(96vw, 1040px);
  max-height: 96vh;
  display: flex;
  flex-direction: column;
  border-radius: 4px;
  overflow: hidden;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

/* Blue header */
.consent-header {
  background: #0d6efd;
  color: #fff;
  padding: 12px 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

.consent-header h5 {
  color: #fff;
  font-size: 1rem;
}

.consent-close-btn {
  background: none;
  border: none;
  color: #fff;
  font-size: 1.6rem;
  line-height: 1;
  cursor: pointer;
  padding: 0 2px;
  opacity: 0.85;
}
.consent-close-btn:hover {
  opacity: 1;
}

/* Content body */
.consent-body {
  padding: 16px 20px 8px;
  overflow-y: auto;
  flex: 1;
}

/* 2-column grid for the four main sections */
.consent-sections {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 24px;
}

.consent-sections section {
  border-left: 3px solid #b6d4fe;
  padding-left: 10px;
}

.consent-sections h6 {
  color: #0a4db5;
  font-weight: 600;
  margin-bottom: 4px;
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.consent-sections p {
  font-size: 0.875rem;
  margin-bottom: 0;
  color: #333;
  line-height: 1.5;
}

/* Last section spans full width */
.consent-section-full {
  grid-column: 1 / -1;
}

.consent-sections a {
  color: #0d6efd;
}

/* Footer */
.consent-footer {
  padding: 12px 20px;
  border-top: 1px solid #dee2e6;
  display: flex;
  gap: 12px;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.consent-footer .btn {
  font-size: 0.875rem;
}
</style>
