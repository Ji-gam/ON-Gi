import { useState } from "react";
import { useNavigate } from "react-router-dom";

// 사용자에게 보이는 실제 앱 진입점. 개발용 화면 모음은 /screens(ScreenIndexPage)로 옮겼다.
export default function StartPage() {
  const navigate = useNavigate();
  const [imageFailed, setImageFailed] = useState(false);

  return (
    <main className="flex min-h-screen flex-col items-center justify-between bg-background px-6 py-14">
      <div className="flex flex-1 flex-col items-center justify-center gap-8">
        {imageFailed ? (
          <div className="flex h-[280px] w-full max-w-[320px] items-center justify-center rounded-2xl bg-secondary">
            <span className="text-xs text-muted-foreground">삽화 준비 중</span>
          </div>
        ) : (
          <img
            src="/images/start-illustration.png"
            alt="할머니, 아이, 엄마가 손을 잡고 마을길을 걷는 모습"
            className="w-full max-w-[320px]"
            onError={() => setImageFailed(true)}
          />
        )}

        <p className="text-center text-sm font-medium leading-relaxed text-foreground">
          한 아이를 키우려면 온 마을이 필요합니다.
          <br />그 마을을, 온기와 함께 만들어가요.
        </p>
      </div>

      <button
        type="button"
        onClick={() => navigate("/login")}
        className="w-full max-w-[480px] rounded-lg border-0 bg-primary py-3 text-sm font-medium text-primary-foreground"
      >
        시작하기
      </button>
    </main>
  );
}
