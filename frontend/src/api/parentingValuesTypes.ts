// app/dtos/parenting_values_dto.py 와 수동 동기화 (CODING_RULES.md §3-4).

export interface BaumrindQuestionItem {
  index: number;
  text: string;
  dimension: string;
}

export interface QuestionnaireSubmitRequest {
  answers: number[];
}

export interface NarrativeSubmitRequest {
  narrative: string;
}

export interface ParentingValuesResponse {
  warmth_score: number;
  control_score: number;
  type_label: string;
  narrative: string | null;
  updated_at: string;
}
