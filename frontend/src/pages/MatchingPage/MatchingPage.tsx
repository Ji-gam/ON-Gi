import { useEffect, useState } from "react";

import * as matchingApi from "@/api/matching";
import type { CandidateResponse } from "@/api/matchingTypes";
import { useAuth } from "@/hooks/useAuth";

export default function MatchingPage() {
  const { accessToken } = useAuth();
  const [candidates, setCandidates] = useState<CandidateResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken) return;
    matchingApi
      .getCandidates(accessToken)
      .then(setCandidates)
      .catch((err) => setError(err instanceof Error ? err.message : "후보를 불러오지 못했습니다."));
  }, [accessToken]);

  if (!accessToken) return null;

  return (
    <main>
      <h1>매칭 후보</h1>
      {candidates === null && !error && <p>불러오는 중...</p>}
      {error && <p>{error}</p>}
      {candidates && candidates.length === 0 && <p>조건에 맞는 후보가 없습니다.</p>}
      {candidates && candidates.length > 0 && (
        <ul>
          {candidates.map((candidate) => (
            <li key={candidate.user_id}>
              {candidate.nickname} · 총점 {candidate.total_score.toFixed(2)} · 가치관유사도{" "}
              {candidate.values_similarity.toFixed(2)} · 상보스코어{" "}
              {candidate.complementary_score.toFixed(2)} · 거리 {Math.round(candidate.distance_m)}m
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
