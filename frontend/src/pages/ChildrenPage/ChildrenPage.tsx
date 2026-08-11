import { useEffect, useState, type FormEvent } from "react";

import * as childrenApi from "@/api/children";
import type { ChildGender, ChildResponse } from "@/api/childrenTypes";
import { ApiError } from "@/api/client";
import { useAuth } from "@/hooks/useAuth";

export default function ChildrenPage() {
  const { accessToken } = useAuth();
  const [children, setChildren] = useState<ChildResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [monthsOld, setMonthsOld] = useState("");
  const [gender, setGender] = useState<ChildGender | "">("");
  const [temperamentMemo, setTemperamentMemo] = useState("");
  const [allergies, setAllergies] = useState("");
  const [conditions, setConditions] = useState("");
  const [medications, setMedications] = useState("");

  useEffect(() => {
    if (!accessToken) return;
    childrenApi
      .listChildren(accessToken)
      .then(setChildren)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "목록을 불러오지 못했습니다."),
      );
  }, [accessToken]);

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    if (!accessToken) return;
    setError(null);
    setIsSubmitting(true);
    try {
      await childrenApi.createChild(
        {
          months_old: Number(monthsOld),
          gender: gender as ChildGender,
          temperament_memo: temperamentMemo || null,
          allergies: allergies || null,
          conditions: conditions || null,
          medications: medications || null,
        },
        accessToken,
      );
      const updated = await childrenApi.listChildren(accessToken);
      setChildren(updated);
      setMonthsOld("");
      setGender("");
      setTemperamentMemo("");
      setAllergies("");
      setConditions("");
      setMedications("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "아동 등록에 실패했습니다.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDelete(childId: number) {
    if (!accessToken) return;
    setError(null);
    try {
      await childrenApi.deleteChild(childId, accessToken);
      setChildren((prev) => prev?.filter((c) => c.id !== childId) ?? null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "삭제에 실패했습니다.");
    }
  }

  if (!accessToken) return null;

  return (
    <main>
      <h1>아동 관리</h1>

      <section>
        <h2>등록된 아동</h2>
        {children === null && !error && <p>불러오는 중...</p>}
        {children && children.length === 0 && <p>등록된 아동이 없습니다.</p>}
        {children && children.length > 0 && (
          <ul>
            {children.map((child) => (
              <li key={child.id}>
                {child.months_old}개월 · {child.gender === "M" ? "남아" : "여아"}
                {child.temperament_memo ? ` · ${child.temperament_memo}` : ""}
                <button type="button" onClick={() => handleDelete(child.id)}>
                  삭제
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2>아동 등록</h2>
        <form onSubmit={handleCreate}>
          <div>
            <label htmlFor="monthsOld">개월 수</label>
            <input
              id="monthsOld"
              type="number"
              min={0}
              max={216}
              required
              value={monthsOld}
              onChange={(event) => setMonthsOld(event.target.value)}
            />
          </div>
          <div>
            <label htmlFor="childGender">성별</label>
            <select
              id="childGender"
              required
              value={gender}
              onChange={(event) => setGender(event.target.value as ChildGender)}
            >
              <option value="" disabled>
                선택
              </option>
              <option value="M">남아</option>
              <option value="F">여아</option>
            </select>
          </div>
          <div>
            <label htmlFor="temperamentMemo">기질 메모</label>
            <input
              id="temperamentMemo"
              value={temperamentMemo}
              onChange={(event) => setTemperamentMemo(event.target.value)}
            />
          </div>
          <div>
            <label htmlFor="allergies">알레르기</label>
            <input
              id="allergies"
              value={allergies}
              onChange={(event) => setAllergies(event.target.value)}
            />
          </div>
          <div>
            <label htmlFor="conditions">지병</label>
            <input
              id="conditions"
              value={conditions}
              onChange={(event) => setConditions(event.target.value)}
            />
          </div>
          <div>
            <label htmlFor="medications">상시 투약</label>
            <input
              id="medications"
              value={medications}
              onChange={(event) => setMedications(event.target.value)}
            />
          </div>
          {error && <p>{error}</p>}
          <button type="submit" disabled={isSubmitting || !gender}>
            {isSubmitting ? "등록 중..." : "등록"}
          </button>
        </form>
      </section>
    </main>
  );
}
