interface PlaceholderPageProps {
  title: string;
  taskId: string;
  description: string;
}

// 도메인 로직/API 연동 전 라우트 스켈레톤 전용 — 실 화면 구현 시 페이지별 컴포넌트로 교체한다.
export default function PlaceholderPage({ title, taskId, description }: PlaceholderPageProps) {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-2 px-4 text-center">
      <span className="text-xs font-medium text-muted-foreground">{taskId}</span>
      <h1 className="text-2xl font-bold">{title}</h1>
      <p className="text-muted-foreground">{description}</p>
    </main>
  );
}
