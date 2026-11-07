import { OpenAPI } from "./generated";
OpenAPI.BASE = "/api";
OpenAPI.WITH_CREDENTIALS = true;
OpenAPI.CREDENTIALS = "same-origin";

// Set from login/me; clear on logout, password change, account switch or 401.
// Kept in memory only; the workspace clears this on every identity transition.
let csrfToken: string | undefined;
export function setCsrfToken(value?: string) {
  csrfToken = value;
}
OpenAPI.HEADERS = async (options): Promise<Record<string, string>> => {
  if (["GET", "HEAD", "OPTIONS"].includes(options.method)) return {};
  // logout has no request body in OpenAPI, but all auth writes require JSON.
  return csrfToken
    ? { "Content-Type": "application/json", "X-CSRF-Token": csrfToken }
    : { "Content-Type": "application/json" };
};
