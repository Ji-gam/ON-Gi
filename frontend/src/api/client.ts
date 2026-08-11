// CODING_RULES.md §3-1 — 화면/훅은 fetch를 직접 호출하지 않고 반드시 이 파일을 경유한다.
// CODING_RULES.md §9 — 422 detail(문자열|배열) 파싱은 이 파일 1곳에서만 처리한다.

const BASE_URL = "/api/v1";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

interface ValidationErrorItem {
  loc: unknown[];
  msg: string;
}

function toErrorMessage(detail: unknown, status: number): string {
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail)) {
    return (detail as ValidationErrorItem[])
      .map((item) => {
        const parts = item.loc.filter((part) => part !== "body");
        const field = parts[parts.length - 1];
        return field ? `${field}: ${item.msg}` : item.msg;
      })
      .join(" ");
  }
  return `요청을 처리하지 못했습니다. (상태 코드: ${status})`;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  accessToken?: string | null;
}

export async function apiRequest<TResponse>(
  path: string,
  { method = "GET", body, accessToken }: RequestOptions = {},
): Promise<TResponse> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

  let response: Response;
  try {
    // 백엔드가 refresh_token을 httpOnly 쿠키로 내려준다 — credentials:"include"로만 주고받는다.
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      credentials: "include",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (err) {
    console.error("네트워크 오류", err);
    throw new ApiError("서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.", 0);
  }

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    console.error("API 오류", response.status, payload);
    throw new ApiError(toErrorMessage(payload?.detail, response.status), response.status);
  }

  if (response.status === 204) return undefined as TResponse;
  return (await response.json()) as TResponse;
}
