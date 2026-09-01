// Fetch wrapper scaffold for the 7 backend endpoints (T031).
// Consumed by later specs; this module establishes the typed call surface and
// a single configurable base URL.

const DEFAULT_BASE_URL = "";

export const API_BASE_URL: string =
  (import.meta as unknown as { env?: { VITE_API_BASE_URL?: string } }).env?.VITE_API_BASE_URL ??
  DEFAULT_BASE_URL;

export interface OnboardingResponse {
  userId: string;
  identifier: string;
  status: "enrolled";
}

export interface FaceLoginResponse {
  userId: string;
  status: "authenticated";
}

export interface AuthMeResponse {
  authenticated: boolean;
  userId: string | null;
}

export interface LogoutResponse {
  status: "ok";
}

export interface MoodResponse {
  label: string;
  // Spec 004 (FR-012a): confidence is optional — null/omitted when the
  // estimator does not produce one. Rendered as "≈NN%" when present.
  confidence: number | null;
  disclaimer: string;
}

export interface AgeResponse {
  estimatedAge: number;
  range: { min: number; max: number };
  disclaimer: string;
}

export interface DeleteFaceDataResponse {
  userId: string;
  status: "deleted";
}

// Spec 002 error shape: {"error": {"code": "...", "message": "..."}}.
export interface ErrorBody {
  code: string;
  message: string;
}

export class OnboardingApiError extends Error {
  readonly code: string;
  constructor(code: string, message: string) {
    super(message);
    this.name = "OnboardingApiError";
    this.code = code;
  }
}

export class AuthApiError extends Error {
  readonly code: string;
  constructor(code: string, message: string) {
    super(message);
    this.name = "AuthApiError";
    this.code = code;
  }
}

async function parseError(resp: Response, defaultCode = "internal_error"): Promise<never> {
  let code = defaultCode;
  let message = "Ocurrió un error inesperado. Inténtalo de nuevo.";
  try {
    const errBody = (await resp.json()) as { error?: ErrorBody };
    if (errBody?.error?.code && errBody?.error?.message) {
      code = errBody.error.code;
      message = errBody.error.message;
    }
  } catch {
    // Non-JSON error body — keep the generic default.
  }
  throw new AuthApiError(code, message);
}

function headersWithSession(sessionId?: string): HeadersInit {
  if (!sessionId) return {};
  return { "X-Session-Id": sessionId };
}

async function multipart(identifier?: string, image?: Blob, consent?: boolean): Promise<FormData> {
  const form = new FormData();
  if (identifier !== undefined) form.append("identifier", identifier);
  if (consent !== undefined) form.append("consentAccepted", String(consent));
  if (image !== undefined) form.append("image", image);
  return form;
}

export const api = {
  async onboarding(identifier: string, consentAccepted: boolean, image: Blob): Promise<OnboardingResponse> {
    const body = await multipart(identifier, image, consentAccepted);
    const resp = await fetch(`${API_BASE_URL}/api/onboarding`, { method: "POST", body });
    if (!resp.ok) {
      let code = "internal_error";
      let message = "Ocurrió un error inesperado. Inténtalo de nuevo.";
      try {
        const errBody = (await resp.json()) as { error?: ErrorBody };
        if (errBody?.error?.code && errBody?.error?.message) {
          code = errBody.error.code;
          message = errBody.error.message;
        }
      } catch {
        // Non-JSON error body — keep the generic internal_error.
      }
      throw new OnboardingApiError(code, message);
    }
    return resp.json();
  },

  async faceLogin(identifier: string, image: Blob): Promise<FaceLoginResponse> {
    const body = await multipart(identifier, image);
    const resp = await fetch(`${API_BASE_URL}/api/auth/face-login`, {
      method: "POST",
      body,
      credentials: "include",
    });
    if (!resp.ok) {
      await parseError(resp);
    }
    return resp.json();
  },

  async getMe(): Promise<AuthMeResponse> {
    const resp = await fetch(`${API_BASE_URL}/api/auth/me`, { credentials: "include" });
    if (!resp.ok) {
      await parseError(resp, "unauthenticated");
    }
    return resp.json();
  },

  async logout(): Promise<LogoutResponse> {
    const resp = await fetch(`${API_BASE_URL}/api/auth/logout`, {
      method: "POST",
      credentials: "include",
    });
    return resp.json();
  },

  async analysisMood(image: Blob): Promise<MoodResponse> {
    const body = await multipart(undefined, image);
    const resp = await fetch(`${API_BASE_URL}/api/analysis/mood`, {
      method: "POST",
      body,
      credentials: "include", // send the session cookie (spec 003)
    });
    if (!resp.ok) {
      await parseError(resp);
    }
    return resp.json();
  },

  async analysisAge(image: Blob): Promise<AgeResponse> {
    const body = await multipart(undefined, image);
    const resp = await fetch(`${API_BASE_URL}/api/analysis/age`, {
      method: "POST",
      body,
    });
    return resp.json();
  },

  async deleteFaceData(userId: string): Promise<DeleteFaceDataResponse> {
    const resp = await fetch(`${API_BASE_URL}/api/users/${userId}/face-data`, {
      method: "DELETE",
      credentials: "include", // send the session cookie (spec 006, research R-6)
    });
    if (!resp.ok) {
      await parseError(resp);
    }
    return resp.json();
  },
};

export default api;
