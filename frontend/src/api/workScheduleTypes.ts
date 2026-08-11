// app/dtos/work_schedule_dto.py, app/core/utils/schedule_slots.py 와 수동 동기화 (CODING_RULES.md §3-4).

export type ShiftTemplate = "DAY" | "EVENING" | "NIGHT" | "OFF";

export interface ShiftRegisterRequest {
  work_date: string;
  template: ShiftTemplate;
}

export interface WorkScheduleResponse {
  work_date: string;
  slot_bitmask: number;
  shift_template: ShiftTemplate;
  updated_at: string;
}
