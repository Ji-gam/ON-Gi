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

// 백엔드 DTO 필드명 → 화면 표시용 한글 라벨. 새 필드 추가 시 같이 갱신.
const FIELD_LABELS: Record<string, string> = {
  email: "이메일",
  password: "비밀번호",
  name: "이름",
  nickname: "닉네임",
  birth_date: "생년월일",
  gender: "성별",
  phone_number: "휴대폰 번호",
  code: "인증번호",
  residence_h3: "거주지",
  job_category: "직군",
  work_type: "근무 형태",
  household_composition: "가구 구성",
  work_date: "근무일",
  template: "근무 템플릿",
  months_old: "개월 수",
  narrative: "서술",
  answers: "응답",
  provider_id: "상대",
  child_id: "아동",
  meeting_h3: "약속 장소",
  care_date: "돌봄 날짜",
  start_slot: "시작 시간",
  end_slot: "종료 시간",
};

function toErrorMessage(detail: unknown, status: number): string {
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail)) {
    return (detail as ValidationErrorItem[])
      .map((item) => {
        const parts = item.loc.filter((part) => part !== "body");
        const field = parts[parts.length - 1];
        // pydantic v2가 AfterValidator의 ValueError 앞에 붙이는 영문 접두사 제거.
        const message = item.msg.replace(/^Value error,\s*/, "");
        const label = typeof field === "string" ? (FIELD_LABELS[field] ?? field) : undefined;
        return label ? `${label}: ${message}` : message;
      })
      .join(" / ");
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
