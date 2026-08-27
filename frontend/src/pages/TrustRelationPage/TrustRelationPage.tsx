import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import * as matchingApi from "@/api/matching";
import * as trustApi from "@/api/trust";
import type { TrustLevel, TrustRelationshipResponse } from "@/api/trustTypes";
import PageHeader from "@/components/common/PageHeader";
import SafetyBadge from "@/components/common/SafetyBadge";
import { useAuth } from "@/hooks/useAuth";

const LEVEL_LABELS: Record<TrustLevel, string> = {
  L1: "대화 가능",
  L2: "함께 돌봄",
  L3: "단독 위탁",
};

// 기본 3회. 사용자별 조정은 PUT /trs/settings/joint-count로 가능하지만 조회 API가 없어 기본값을 쓴다.
const REQUIRED_JOINT_COUNT = 3;

function LevelUpModal({ partnerName, onClose }: { partnerName: string; onClose: () => void }) {
  const navigate = useNavigate();
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-foreground/40 px-6 pb-10">
      <div className="flex w-full max-w-[420px] flex-col items-center gap-4 rounded-3xl bg-background p-6">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-secondary">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.6}
            className="h-7 w-7 text-primary"
          >
            <path d="M12 3 5 6v6c0 4 3 7.4 7 9 4-1.6 7-5 7-9V6l-7-3Z" strokeLinejoin="round" />
          </svg>
        </div>
        <div className="text-center">
          <div className="text-[11px] font-semibold tracking-widest text-muted-foreground">
            LEVEL UP
          </div>
          <h2 className="mt-1 text-lg font-bold leading-snug text-foreground">
            L3 단독 위탁이
            <br />
            열렸습니다
          </h2>
        </div>
        <p className="text-center text-xs leading-relaxed text-muted-foreground">
          {partnerName}님과 공개 장소에서 {REQUIRED_JOINT_COUNT}회를 함께 돌봤습니다.
        </p>
        <div className="flex w-full items-center gap-2">
          <div className="flex-1 rounded-xl bg-secondary px-3 py-2.5 text-center">
            <div className="text-sm font-bold text-muted-foreground">L2</div>
            <div className="text-[10px] text-muted-foreground">함께 돌봄</div>
          </div>
          <span className="text-muted-foreground">→</span>
          <div className="flex-1 rounded-xl bg-primary px-3 py-2.5 text-center">
            <div className="text-sm font-bold text-primary-foreground">L3</div>
            <div className="text-[10px] text-primary-foreground/80">단독 위탁</div>
          </div>
        </div>
        <p className="w-full rounded-xl bg-secondary p-3 text-[11px] leading-relaxed text-muted-foreground">
          이제 {partnerName}님에게 아이를 단독으로 맡기는 요청을 보낼 수 있습니다. 노쇼 방지 포인트
          예치와 돌봄일지는 그대로 적용됩니다.
        </p>
        <button
          type="button"
          onClick={() => navigate("/care/requests/new")}
          className="w-full rounded-full border-0 bg-primary py-3 text-sm font-semibold text-primary-foreground"
        >
          단독 돌봄 요청하기
        </button>
        <button
          type="button"
          onClick={onClose}
          className="border-0 bg-transparent text-xs text-muted-foreground"
        >
          닫기
        </button>
      </div>
    </div>
  );
}

export default function TrustRelationPage() {
  const { partnerId } = useParams();
  const { accessToken } = useAuth();
  const [relationship, setRelationship] = useState<TrustRelationshipResponse | null | undefined>(
    undefined,
  );
  const [partnerName, setPartnerName] = useState("이웃");
  const [error, setError] = useState<string | null>(null);
  const [showLevelUp, setShowLevelUp] = useState(false);

  const load = useCallback(() => {
    if (!accessToken || !partnerId) return;
    trustApi
      .getRelationship(Number(partnerId), accessToken)
      .then((next) => {
        setRelationship((prev) => {
          // L3로 막 올라온 순간에만 축하 모달을 띄운다.
          if (prev && prev.level !== "L3" && next?.level === "L3") setShowLevelUp(true);
          return next;
        });
      })
      .catch((err) =>
        setError(err instanceof Error ? err.message : "신뢰 정보를 불러오지 못했습니다."),
      );
  }, [accessToken, partnerId]);

  useEffect(load, [load]);

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

  if (!accessToken) return null;

  const count = relationship?.joint_session_count ?? 0;
  const remaining = Math.max(0, REQUIRED_JOINT_COUNT - count);

  return (
    <main className="flex min-h-screen justify-center bg-background px-6 py-10">
      <div className="flex w-full max-w-[480px] flex-col gap-4">
        <PageHeader
          title={`${partnerName} 님과의 신뢰`}
          backTo="/matching"
          right={<SafetyBadge />}
        />

        {error && (
          <p className="rounded-lg bg-destructive/10 px-3 py-2.5 text-xs text-destructive">
            {error}
          </p>
        )}
        {relationship === undefined && !error && (
          <p className="text-xs text-muted-foreground">불러오는 중...</p>
        )}

        {relationship === null && !error && (
          <section className="flex flex-col gap-3 rounded-2xl border border-border bg-secondary p-4">
            <p className="text-xs leading-relaxed text-foreground">
              아직 {partnerName}님과의 관계가 시작되지 않았어요. 첫 만남(공개 장소 공동육아)을
              요청하면 신뢰 단계가 시작됩니다.
            </p>
            <Link
              to={`/trust/${partnerId}/joint-sessions/new`}
              className="rounded-full bg-primary px-3 py-2.5 text-center text-xs font-semibold text-primary-foreground"
            >
              첫 만남 요청 보내기
            </Link>
          </section>
        )}

        {relationship && (
          <>
            <section className="flex flex-col gap-2.5 rounded-2xl bg-secondary p-4">
              <div className="flex items-center justify-between">
                <h2 className="text-xs font-semibold text-foreground">공개 장소 공동육아</h2>
                <span className="text-xs font-bold text-foreground">
                  {count} / {REQUIRED_JOINT_COUNT}회
                </span>
              </div>
              <div className="flex gap-1.5">
                {Array.from({ length: REQUIRED_JOINT_COUNT }, (_, index) => (
                  <div
                    key={index}
                    className={
                      index < count
                        ? "h-2 flex-1 rounded-full bg-primary"
                        : "h-2 flex-1 rounded-full bg-background"
                    }
                  />
                ))}
              </div>
              <p className="text-[11px] text-muted-foreground">
                {relationship.level === "L3"
                  ? "단독 위탁이 열려 있습니다."
                  : remaining === 1
                    ? "한 번만 더 함께 돌보면 단독 위탁이 열립니다."
                    : `${remaining}번 더 함께 돌보면 단독 위탁이 열립니다.`}
              </p>
            </section>

            <section className="flex items-center justify-between rounded-2xl border border-border bg-secondary p-4">
              <div>
                <div className="text-[11px] text-muted-foreground">현재 신뢰 단계</div>
                <div className="text-sm font-semibold text-foreground">
                  {relationship.level} · {LEVEL_LABELS[relationship.level]}
                </div>
              </div>
              <div className="flex gap-1.5">
                {(["L1", "L2", "L3"] as TrustLevel[]).map((level) => (
                  <span
                    key={level}
                    className={
                      relationship.level === level
                        ? "rounded-full bg-primary px-2 py-1 text-[10px] font-bold text-primary-foreground"
                        : "rounded-full bg-background px-2 py-1 text-[10px] text-muted-foreground"
                    }
                  >
                    {level}
                  </span>
                ))}
              </div>
            </section>

            <section className="flex flex-col gap-2">
              <h2 className="text-xs font-semibold text-foreground">함께한 기록</h2>
              <p className="rounded-xl border border-dashed border-border bg-secondary p-3 text-[11px] leading-relaxed text-muted-foreground">
                회차별 기록 목록은 조회 API가 준비되면 표시됩니다. 지금은 위의 누적 횟수({count}
                회)만 확인할 수 있어요.
              </p>
              <p className="text-[11px] text-muted-foreground">
                회차마다 서로 평가를 남기고, 두 사람 모두 제출해야 기록으로 인정됩니다.
              </p>
            </section>

            {relationship.level === "L3" ? (
              <Link
                to={`/care/requests/new?providerId=${partnerId}&nickname=${encodeURIComponent(partnerName)}`}
                className="rounded-full bg-primary px-3 py-3 text-center text-sm font-semibold text-primary-foreground"
              >
                단독 돌봄 요청하기
              </Link>
            ) : (
              <Link
                to={`/trust/${partnerId}/joint-sessions/new`}
                className="rounded-full bg-primary px-3 py-3 text-center text-sm font-semibold text-primary-foreground"
              >
                공동육아 일정 잡기
              </Link>
            )}
          </>
        )}
      </div>

      {showLevelUp && (
        <LevelUpModal partnerName={partnerName} onClose={() => setShowLevelUp(false)} />
      )}
    </main>
  );
}
