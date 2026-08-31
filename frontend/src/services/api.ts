// Fetch wrapper scaffold for the 7 backend endpoints (T031).
// Consumed by later specs; this module establishes the typed call surface and
// a single configurable base URL.

const DEFAULT_BASE_URL = "http://localhost:8000";

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
  userId: string;
  status: "authenticated";
  expiresAt: string;
}

export interface LogoutResponse {
  status: "logged_out";
}

export interface MoodResponse {
  label: string;
  confidence: number;
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
    const resp = await fetch(`${API_BASE_URL}/api/auth/face-login`, { method: "POST", body });
    return resp.json();
  },

  async authMe(sessionId?: string): Promise<AuthMeResponse> {
    const resp = await fetch(`${API_BASE_URL}/api/auth/me`, { headers: headersWithSession(sessionId) });
    return resp.json();
  },

  async logout(sessionId?: string): Promise<LogoutResponse> {
    const resp = await fetch(`${API_BASE_URL}/api/auth/logout`, {
      method: "POST",
      headers: headersWithSession(sessionId),
    });
    return resp.json();
  },

  async analysisMood(image: Blob, sessionId?: string): Promise<MoodResponse> {
    const body = await multipart(undefined, image);
    const resp = await fetch(`${API_BASE_URL}/api/analysis/mood`, {
      method: "POST",
      headers: headersWithSession(sessionId),
      body,
    });
    return resp.json();
  },

  async analysisAge(image: Blob, sessionId?: string): Promise<AgeResponse> {
    const body = await multipart(undefined, image);
    const resp = await fetch(`${API_BASE_URL}/api/analysis/age`, {
      method: "POST",
      headers: headersWithSession(sessionId),
      body,
    });
    return resp.json();
  },

  async deleteFaceData(userId: string, sessionId?: string): Promise<DeleteFaceDataResponse> {
    const resp = await fetch(`${API_BASE_URL}/api/users/${userId}/face-data`, {
      method: "DELETE",
      headers: headersWithSession(sessionId),
    });
    return resp.json();
  },
};

export default api;
