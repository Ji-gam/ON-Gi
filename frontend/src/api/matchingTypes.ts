// app/dtos/matching_dto.py 와 수동 동기화 (CODING_RULES.md §3-4).

export interface CandidateResponse {
  user_id: number;
  nickname: string;
  total_score: number;
  values_similarity: number;
  complementary_score: number;
  distance_m: number;
  age_similarity: number;
  trust_score: number;
  average_rating: number | null;
  top_tags: string[];
  reason: string;
}
