<template>
  <div class="col-12">
    <div
      v-if="
        $store.getters.getInformedConsentAgreement == 'none' ||
        $store.getters.getInformedConsentAgreement == 'no'
      "
      class="alert alert-info"
      role="dialog"
    >
      <!-- ===== DEUTSCH ===== -->
      <template v-if="lang === 'de'">
        <h5>Einwilligung zur Nutzung des Interview-Agenten</h5>

        <h4>Zweck</h4>
        <p class="lead text-wrap">
          Der Interview-Agent dient der Ermittlung technischer und didaktischer
          Voraussetzungen für den Einsatz von Sprachmodellen im
          Lehr-Lern-Kontext, insbesondere zur Durchführung von Interviews zur
          Erfassung und Förderung der Selbstregulation.
        </p>

        <h4>Erfasste Daten</h4>
        <p class="lead text-wrap">
          Erfasst werden Interaktionen (Klicks, Mausbewegungen, Tab-Wechsel,
          Texteingaben) sowie Fragen und Antworten der Sprachmodelle —
          ausschließlich in pseudonymisierter Form. Nach der Speicherung ist
          eine Zuordnung zu einer Person oder Moodle-Nutzer-ID nicht mehr
          möglich. Bitte geben Sie keine personenbezogenen Daten Dritter ein.
        </p>

        <h4>Verwendung</h4>
        <p class="lead text-wrap">
          Die Daten dienen der Überwachung, Analyse und Verbesserung des
          technischen Betriebs und der Benutzerfreundlichkeit des
          Interview-Agenten und verbundener Dienste (z. B. FLEXI LLM-Server)
          sowie der Beantwortung wissenschaftlicher Fragestellungen zur Nutzung
          und Qualität von KI-gestützten Lehrangeboten. Die Verarbeitung erfolgt
          auf Basis Ihrer freiwilligen Einwilligung (Art. 6 Abs. 1 lit. a DSGVO)
          ausschließlich auf Servern der FernUniversität in Hagen mit
          Open-Source-Sprachmodellen.
        </p>

        <h4>Rechte und Freiwilligkeit</h4>
        <p class="lead text-wrap">
          Die Nutzung ist freiwillig (Opt-in); die Einwilligung kann jederzeit
          mit Wirkung für die Zukunft widerrufen werden. Lehrende können den
          Agenten über Moodle (LTI) oder als Web-Anwendung einsetzen und durch
          Löschung der Aktivität jederzeit deaktivieren. Eine Herausgabe oder
          Löschung einzelner Datensätze ist aufgrund der Pseudonymisierung
          technisch nicht möglich.
        </p>

        <h4>Verantwortlichkeiten</h4>
        <p class="lead text-wrap">
          Verantwortlich für die Datenverarbeitung ist die FernUniversität in
          Hagen, Universitätsstraße 11, 58097 Hagen. Bei Fragen wenden Sie sich
          bitte an den
          <a href="mailto:datenschutzbeauftragter@fernuni-hagen.de"
            >Behördlichen Datenschutzbeauftragten</a
          >. Weitere Fragen beantworten Ihnen der Leiter dieser Studie
          <a href="mailto:niels.seidel@fernuni-hagen.de">Dr. Niels Seidel</a>.
        </p>

        <hr />
        <div
          class="d-flex flex-column flex-md-row justify-content-between align-items-stretch mb-3"
        >
          <button
            type="button"
            @click="$store.commit('setInformedConsentAgreement', 'yes')"
            class="btn btn-primary mb-2 mb-md-0 mr-md-3 w-100 w-md-auto"
            aria-label="Einwilligung erteilen"
          >
            Ja, ich erteile die Einwilligung zur Erhebung und Verarbeitung
            meiner Daten im Interview-Agenten!
          </button>
          <button
            type="button"
            @click="$store.commit('setInformedConsentAgreement', 'no')"
            class="btn btn-danger w-100 w-md-auto"
            aria-label="Einwilligung nicht erteilen"
          >
            Nein, ich willige nicht ein.
          </button>
        </div>
      </template>

      <!-- ===== ENGLISH ===== -->
      <template v-else>
        <h5>Consent to Use the Interview Agent</h5>

        <h4>Purpose</h4>
        <p class="lead text-wrap">
          The interview agent is used to determine the technical and didactic
          requirements for deploying language models in teaching and learning
          contexts, in particular for conducting interviews to assess and
          promote self-regulated learning.
        </p>

        <h4>Data Collected</h4>
        <p class="lead text-wrap">
          We collect interactions (clicks, mouse movements, tab switches, text
          input) as well as questions and answers from the language models —
          exclusively in pseudonymised form. Once stored, it is no longer
          possible to link the data to an individual or a Moodle user ID. Please
          do not enter any personal data of third parties.
        </p>

        <h4>Use of Data</h4>
        <p class="lead text-wrap">
          The data is used to monitor, analyse and improve the technical
          operation and usability of the interview agent and related services
          (e.g. FLEXI LLM server), as well as to answer research questions
          regarding the use and quality of AI-assisted teaching offerings.
          Processing is carried out on the basis of your voluntary consent (Art.
          6(1)(a) GDPR) exclusively on servers of the FernUniversität in Hagen
          using open-source language models.
        </p>

        <h4>Rights and Voluntary Nature</h4>
        <p class="lead text-wrap">
          Participation is voluntary (opt-in); consent may be withdrawn at any
          time with effect for the future. Instructors can deploy the agent via
          Moodle (LTI) or as a web application and deactivate it at any time by
          deleting the activity. The disclosure or deletion of individual
          records is technically not possible due to pseudonymisation.
        </p>

        <h4>Responsibilities</h4>
        <p class="lead text-wrap">
          The controller responsible for data processing is FernUniversität in
          Hagen, Universitätsstraße 11, 58097 Hagen, Germany. If you have any
          questions, please contact the
          <a href="mailto:datenschutzbeauftragter@fernuni-hagen.de"
            >Official Data Protection Officer</a
          >. Further questions can be directed to the lead researcher of this
          study,
          <a href="mailto:niels.seidel@fernuni-hagen.de">Dr. Niels Seidel</a>.
        </p>

        <hr />
        <div
          class="d-flex flex-column flex-md-row justify-content-between align-items-stretch mb-3"
        >
          <button
            type="button"
            @click="$store.commit('setInformedConsentAgreement', 'yes')"
            class="btn btn-primary mb-2 mb-md-0 mr-md-3 w-100 w-md-auto"
            aria-label="Give consent"
          >
            Yes, I consent to the collection and processing of my data in the
            Interview Agent!
          </button>
          <button
            type="button"
            @click="$store.commit('setInformedConsentAgreement', 'no')"
            class="btn btn-danger w-100 w-md-auto"
            aria-label="Decline consent"
          >
            No, I do not consent.
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<script>
import Vue from "vue";

export default Vue.extend({
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
[v-cloak] .v-cloak--hidden {
  display: none !important;
}

[v-cloak] {
  display: none !important;
}
</style>
