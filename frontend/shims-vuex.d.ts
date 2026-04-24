// Pulls in vuex/types/vue.d.ts which augments Vue instances with $store: Store<any>.
// Without this file in tsconfig "files", the augmentation is not applied
// and TypeScript reports "Property '$store' does not exist on type 'Vue'".
import "vuex";

// Global runtime variables injected by the backend or LTI context.
declare global {
  interface Window {
    SRL_CONFIG?: {
      apiBaseUrl?: string;
      userId?: string;
      adminPassword?: string;
    };
    SRL_CLIENT?: string;
    SRL_BACKEND_URL?: string;
    SRL_ADMIN_PASSWORD?: string;
  }
}
