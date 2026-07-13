const DEV_AUTH_TOKEN =
  process.env.NEXT_PUBLIC_DEV_AUTH_TOKEN ?? "local-dev-token";
const AUTH_MODE = process.env.NEXT_PUBLIC_AUTH_MODE ?? "dev";
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function authMode() {
  return AUTH_MODE === "oidc" ? "oidc" : "dev";
}

export function isOidcAuthMode() {
  return authMode() === "oidc";
}

function resolveInput(input: RequestInfo | URL): RequestInfo | URL {
  if (!API_BASE_URL || typeof input !== "string" || !input.startsWith("/")) {
    return input;
  }
  return `${API_BASE_URL}${input}`;
}

export function safeReturnTo(value: string | null | undefined) {
  if (!value || !value.startsWith("/") || value.startsWith("//")) {
    return "/admin/workspace";
  }
  return value.slice(0, 500);
}

export function loginUrl(returnTo: string) {
  const query = new URLSearchParams({ return_to: safeReturnTo(returnTo) });
  return `/auth/login?${query.toString()}`;
}

export function adminLoginPageUrl(returnTo = "/admin/workspace", reason?: string | null) {
  const query = new URLSearchParams({ return_to: safeReturnTo(returnTo) });
  if (reason) query.set("reason", reason);
  return `/admin/login?${query.toString()}`;
}

export async function logoutFromSession(returnTo = "/admin/login") {
  await fetch(`/auth/logout?${new URLSearchParams({ return_to: safeReturnTo(returnTo) })}`, {
    method: "POST",
    credentials: "include",
  });
}

export function authenticatedFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  const headers = new Headers(init.headers);
  if (authMode() === "dev") {
    headers.set("Authorization", `Bearer ${DEV_AUTH_TOKEN}`);
  }
  return fetch(resolveInput(input), {
    ...init,
    headers,
    credentials: "include",
  });
}
