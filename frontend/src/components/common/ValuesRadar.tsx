import { VALUE_AXES } from "@/lib/valueAxes";

// 목업의 가치관 8축 레이더.
// 백엔드는 현재 온기/통제 2축 집계값만 저장해 축별 실제 응답을 내려주지 않는다
// (docs/backend-handoff.txt A-2). 그래서 지금은 전체 일치율 하나로 모든 축을 채우고,
// 축별 저장이 열리면 axisValues에 실제 값을 넣기만 하면 되도록 구성했다.

function polygonPoints(values: number[], radius: number, center: number): string {
  return values
    .map((value, index) => {
      const angle = (Math.PI * 2 * index) / values.length - Math.PI / 2;
      const r = radius * Math.max(0.08, Math.min(1, value));
      return `${center + r * Math.cos(angle)},${center + r * Math.sin(angle)}`;
    })
    .join(" ");
}

export default function ValuesRadar({
  partnerValues,
  myValues,
}: {
  partnerValues: number[];
  myValues: number[];
}) {
  const size = 200;
  const center = size / 2;
  const radius = 78;

  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      className="mx-auto h-48 w-48"
      role="img"
      aria-label="가치관 축별 비교"
    >
      {[1, 0.75, 0.5, 0.25].map((ratio) => (
        <polygon
          key={ratio}
          points={polygonPoints(
            VALUE_AXES.map(() => ratio),
            radius,
            center,
          )}
          fill="none"
          stroke="hsl(var(--border))"
          strokeWidth="1"
        />
      ))}
      <polygon
        points={polygonPoints(partnerValues, radius, center)}
        fill="hsl(var(--primary) / 0.18)"
        stroke="hsl(var(--primary))"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <polygon
        points={polygonPoints(myValues, radius, center)}
        fill="none"
        stroke="hsl(var(--foreground))"
        strokeWidth="1.5"
        strokeDasharray="4 3"
        strokeLinejoin="round"
      />
    </svg>
  );
}
