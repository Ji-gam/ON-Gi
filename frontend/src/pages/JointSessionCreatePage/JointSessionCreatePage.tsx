import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";

import * as matchingApi from "@/api/matching";
import * as trustApi from "@/api/trust";
import PageHeader from "@/components/common/PageHeader";
import { useAuth } from "@/hooks/useAuth";

// 사적 공간은 선택할 수 없다 — 첫 만남은 공개 장소에서만 진행한다(REQ-F-TRS-02).
const PLACE_TYPES = ["키즈카페", "공원", "문화센터", "도서관"];

function todayYmd(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function JointSessionCreatePage() {
  const { partnerId } = useParams();
  const { accessToken } = useAuth();
  const navigate = useNavigate();

  const [partnerName, setPartnerName] = useState("이웃");
  const [placeType, setPlaceType] = useState<string>(PLACE_TYPES[0]);
  const [placeName, setPlaceName] = useState("");
  const [scheduledDate, setScheduledDate] = useState(todayYmd());
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!accessToken || !partnerId) return;
    matchingApi
      .getCandidates(accessToken)
      .then((candidates) => {
        const found = candidates.find((c) => String(c.user_id) === partnerId);
        if (found) setPartnerName(found.nickname);
      })
      .catch(() => {});
  }, [accessToken, partnerId]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!accessToken || !partnerId) return;
    setError(null);
    setIsSubmitting(true);
    try {
      await trustApi.createJointSession(
        Number(partnerId),
        {
          partner_id: Number(partnerId),
          place: placeName.trim() ? `${placeType} · ${placeName.trim()}` : placeType,
          scheduled_date: scheduledDate,
        },
        accessToken,
      );
      navigate(`/trust/${partnerId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "일정을 등록하지 못했습니다.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!accessToken) return null;

  return (
    <main className="flex min-h-screen justify-center bg-background px-6 py-10">
      <div className="flex w-full max-w-[480px] flex-col gap-4">
        <PageHeader title="첫 만남 요청" backTo={`/trust/${partnerId}`} />

        <p className="rounded-2xl bg-secondary p-4 text-xs leading-relaxed text-foreground">
          처음 세 번은 <span className="font-semibold">공개 장소</span>에서 함께 돌봅니다. 단독
          위탁은 그 다음에 열립니다.
        </p>

        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          <div>
            <div className="mb-2 text-xs font-semibold text-foreground">장소 유형</div>
            <div className="flex flex-wrap gap-2">
              {PLACE_TYPES.map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => setPlaceType(type)}
                  className={
                    placeType === type
                      ? "rounded-full border-0 bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground"
                      : "rounded-full border border-border bg-secondary px-3 py-1.5 text-xs text-foreground"
                  }
                >
                  {type}
                </button>
              ))}
            </div>
            <p className="mt-2 text-[11px] text-muted-foreground">
              자택 등 사적 공간은 첫 만남 장소로 선택할 수 없어요.
            </p>
          </div>

          <div>
            <label htmlFor="placeName" className="mb-1 block text-xs font-semibold text-foreground">
              장소명 (선택)
            </label>
            <input
              id="placeName"
              value={placeName}
              onChange={(event) => setPlaceName(event.target.value)}
              placeholder="예: 망원한강공원"
              className="w-full rounded-lg border border-border bg-secondary px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground"
            />
          </div>

          <div>
            <label
              htmlFor="scheduledDate"
              className="mb-1 block text-xs font-semibold text-foreground"
            >
              날짜 <span className="text-destructive">*</span>
            </label>
            <input
              id="scheduledDate"
              type="date"
              required
              min={todayYmd()}
              value={scheduledDate}
              onChange={(event) => setScheduledDate(event.target.value)}
              className="w-full rounded-lg border border-border bg-secondary px-3 py-2.5 text-sm text-foreground"
            />
          </div>

          {error && (
            <p className="rounded-lg bg-destructive/10 px-3 py-2.5 text-xs text-destructive">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded-full border-0 bg-primary px-3 py-3 text-sm font-semibold text-primary-foreground disabled:opacity-60"
          >
            {isSubmitting ? "보내는 중..." : `${partnerName}님에게 요청 보내기`}
          </button>
        </form>
      </div>
    </main>
  );
}
