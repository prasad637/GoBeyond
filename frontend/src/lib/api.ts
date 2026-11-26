const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

let inMemoryAccessToken: string | null = null;
let isRefreshing = false;
let refreshPromise: Promise<string | null> | null = null;

export const setAccessToken = (token: string | null) => {
  inMemoryAccessToken = token;
};

export const getAccessToken = (): string | null => {
  return inMemoryAccessToken;
};

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp("(^|;\\s*)" + name + "=([^;]*)"));
  return match ? decodeURIComponent(match[2]) : null;
}

/**
 * Checks whether an authenticated browser session likely exists before issuing
 * a startup refresh request. The backend sets the non-HttpOnly `gobeyond_csrf_token`
 * cookie with the same lifetime whenever it issues `gobeyond_refresh_token` and
 * clears both together on logout, revocation, or expiry.
 */
export function hasRefreshSessionHint(): boolean {
  if (inMemoryAccessToken) return true;
  return Boolean(getCookie("gobeyond_csrf_token"));
}

export class ApiError extends Error {
  status: number;
  data: any;

  constructor(status: number, message: string, data?: any) {
    super(message);
    this.status = status;
    this.data = data;
    this.name = "ApiError";
  }
}

interface CustomRequestInit extends RequestInit {
  _isRetry?: boolean;
}

/**
 * Single-flight token refresh mechanism.
 * Multiple concurrent 401 responses share a single HTTP request to /api/v1/auth/refresh.
 */
export async function singleFlightRefreshToken(): Promise<string | null> {
  if (isRefreshing && refreshPromise) {
    return refreshPromise;
  }

  isRefreshing = true;
  refreshPromise = (async () => {
    try {
      const csrfToken = getCookie("gobeyond_csrf_token");
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      if (csrfToken) {
        headers["X-CSRF-Token"] = csrfToken;
      }

      const res = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
        method: "POST",
        headers,
        credentials: "include",
      });

      if (!res.ok) {
        setAccessToken(null);
        if (typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("gobeyond_session_expired"));
        }
        return null;
      }

      const data = await res.json();
      if (data?.access_token) {
        setAccessToken(data.access_token);
        return data.access_token;
      }
      return null;
    } catch {
      setAccessToken(null);
      return null;
    } finally {
      isRefreshing = false;
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

export async function apiRequest<T = any>(
  endpoint: string,
  options: CustomRequestInit = {}
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  const token = inMemoryAccessToken;
  if (token && !headers["Authorization"]) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  // Include CSRF token on state-modifying requests if present in cookie
  const csrfToken = getCookie("gobeyond_csrf_token");
  if (csrfToken && !headers["X-CSRF-Token"] && options.method && options.method !== "GET" && options.method !== "HEAD") {
    headers["X-CSRF-Token"] = csrfToken;
  }

  // Ensure clean url
  const cleanEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  const url = `${API_BASE_URL}/api/v1${cleanEndpoint}`;

  try {
    const res = await fetch(url, {
      ...options,
      headers,
      credentials: "include",
    });

    // Handle 401 Unauthorized with single-flight refresh
    if (
      res.status === 401 &&
      !options._isRetry &&
      !cleanEndpoint.includes("/auth/refresh") &&
      !cleanEndpoint.includes("/auth/login") &&
      !cleanEndpoint.includes("/auth/register")
    ) {
      const refreshedToken = await singleFlightRefreshToken();
      if (refreshedToken) {
        return apiRequest<T>(endpoint, {
          ...options,
          _isRetry: true,
          headers: {
            ...headers,
            Authorization: `Bearer ${refreshedToken}`,
          },
        });
      }
    }

    if (!res.ok) {
      let errorMessage = `API request failed with status ${res.status}`;
      let errorData = null;
      try {
        errorData = await res.json();
        if (errorData?.detail) {
          errorMessage = typeof errorData.detail === "string" ? errorData.detail : JSON.stringify(errorData.detail);
        }
      } catch {
        // non-json error
      }
      throw new ApiError(res.status, errorMessage, errorData);
    }

    if (res.status === 204) {
      return {} as T;
    }

    return await res.json();
  } catch (err: any) {
    if (err instanceof ApiError) {
      throw err;
    }
    throw new ApiError(0, err?.message || "Network error. Failed to reach server.");
  }
}
