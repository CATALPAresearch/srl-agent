import "bootstrap/dist/css/bootstrap.min.css";
import { createApp } from "vue";
import axios from "axios";
import { store } from "./store";
import router from "./router";
import ChatApp from "./components/ChatApp.vue";
import { library } from "@fortawesome/fontawesome-svg-core";
import {
  faCopy,
  faCog,
  faThumbsDown,
  faThumbsUp,
  faCheck,
  faSpinner,
  faArrowUp,
  faCommentDots,
  faLock,
  faUnlock,
  faBars,
} from "@fortawesome/free-solid-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/vue-fontawesome";

library.add(
  faCopy,
  faCog,
  faThumbsDown,
  faThumbsUp,
  faCheck,
  faSpinner,
  faArrowUp,
  faCommentDots,
  faLock,
  faUnlock,
  faBars,
);

// Set API host: prefer SRL_CONFIG.apiBaseUrl, then current origin
const _apiBase =
  (window.SRL_CONFIG && window.SRL_CONFIG.apiBaseUrl) || window.location.origin;
store.commit("setApiHost", _apiBase);

// The user id is issued by the server, never chosen by the client: after a verified
// LTI launch it arrives in SRL_CONFIG.token; standalone users get an anonymous identity
// whose signed token is kept in localStorage. Every request carries the token.
const TOKEN_KEY = "srl_identity_token";

function useToken(token) {
  axios.defaults.headers.common["Authorization"] = `Bearer ${token}`;
}

async function resolveIdentity() {
  const ltiToken = window.SRL_CONFIG && window.SRL_CONFIG.token;
  if (ltiToken) {
    useToken(ltiToken);
  } else {
    const stored = localStorage.getItem(TOKEN_KEY);
    if (stored) useToken(stored);
  }
  const res = await axios.post(`${_apiBase}/session/identity`);
  if (!ltiToken) localStorage.setItem(TOKEN_KEY, res.data.token);
  useToken(res.data.token);
  localStorage.removeItem("srl_userid"); // legacy client-chosen id, no longer used
  return res.data;
}

function mountApp() {
  createApp(ChatApp)
    .use(store)
    .use(router)
    .component("font-awesome-icon", FontAwesomeIcon)
    .mount("#app");
}

resolveIdentity()
  .then((identity) => {
    store.commit("setUser", identity.userid);
    store.commit("setRole", identity.role);
  })
  .catch((e) => console.error("Could not obtain a user identity:", e))
  .finally(mountApp);
