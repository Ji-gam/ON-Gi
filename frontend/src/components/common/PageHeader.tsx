import { Link } from "react-router-dom";

// 화면 상단 공통 헤더 — 뒤로가기 + 제목 + (선택) 우측 배지/액션.
export default function PageHeader({
  title,
  backTo,
  right,
}: {
  title: string;
  backTo?: string;
  right?: React.ReactNode;
}) {
  return (
    <div className="mb-4 flex items-center justify-between">
      <div className="flex items-center gap-2">
        {backTo && (
          <Link to={backTo} className="text-sm text-muted-foreground">
            ‹
          </Link>
        )}
        <h1 className="text-base font-semibold text-foreground">{title}</h1>
      </div>
      {right}
    </div>
  );
}
