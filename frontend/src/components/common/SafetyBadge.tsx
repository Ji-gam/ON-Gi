// 목업 전 화면 우상단에 반복되는 "안전" 배지.
// 대응하는 백엔드 개념(신고/제재 이력)이 아직 없어 정적 표시다 — docs/backend-handoff.txt B-10.
export default function SafetyBadge() {
  return (
    <span className="rounded-full bg-destructive/10 px-2 py-0.5 text-[10px] font-semibold text-destructive">
      안전
    </span>
  );
}
