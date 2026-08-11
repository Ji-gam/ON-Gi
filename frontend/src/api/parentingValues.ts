import { apiRequest } from "./client";
import type {
  BaumrindQuestionItem,
  NarrativeSubmitRequest,
  ParentingValuesResponse,
  QuestionnaireSubmitRequest,
} from "./parentingValuesTypes";

export function getQuestions(): Promise<BaumrindQuestionItem[]> {
  return apiRequest<BaumrindQuestionItem[]>("/acc/parenting-values/questions");
}

export function getParentingValues(accessToken: string): Promise<ParentingValuesResponse> {
  return apiRequest<ParentingValuesResponse>("/acc/parenting-values", { accessToken });
}

export function submitQuestionnaire(
  request: QuestionnaireSubmitRequest,
  accessToken: string,
): Promise<ParentingValuesResponse> {
  return apiRequest<ParentingValuesResponse>("/acc/parenting-values/questionnaire", {
    method: "POST",
    body: request,
    accessToken,
  });
}

export function submitNarrative(
  request: NarrativeSubmitRequest,
  accessToken: string,
): Promise<ParentingValuesResponse> {
  return apiRequest<ParentingValuesResponse>("/acc/parenting-values/narrative", {
    method: "POST",
    body: request,
    accessToken,
  });
}
