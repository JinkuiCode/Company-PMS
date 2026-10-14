export const feedbackEnumCodes = ['feedback_type','feedback_module','feedback_issue_category','feedback_request_category','feedback_impact','feedback_status','feedback_outcome','feedback_cause'] as const
export type FeedbackMode = 'new' | 'handle' | 'supplement'
export function categoryCode(type: number | null) { return type === 1 ? 'feedback_issue_category' : type === 2 ? 'feedback_request_category' : '' }
export function freshFeedback(): Record<string, any> {
  return {type_id:null,module_id:null,category_id:null,impact_id:null,title:'',description:'',expected_result:'',steps:''}
}
export function allowedOutcomes(status: number) { return status === 5 ? [1,2,3,4] : status === 6 ? [5,6] : [1,2,3,4,5,6] }
export function validateFeedback(draft: Record<string, any>, mode: FeedbackMode): Record<string,string> {
  const errors: Record<string,string> = {}
  const required = mode === 'new' ? ['type_id','module_id','category_id','impact_id','title','description','expected_result',...(draft.type_id === 1 ? ['steps'] : [])] : mode === 'handle' ? ['status_id','opinion',...([5,6].includes(draft.status_id)?['outcome_id','cause_id']:[])] : ['description']
  for (const key of required) if (draft[key] == null || String(draft[key]).trim() === '') errors[key] = '请填写或选择此项'
  if (mode === 'handle' && draft.outcome_id && !allowedOutcomes(draft.status_id).includes(draft.outcome_id)) errors.outcome_id = '请选择与当前状态相符的结论'
  if (mode === 'new' && String(draft.title).trim().length > 200) errors.title = '标题最多200字'
  return errors
}
export const mailLabels: Record<string,string> = {pending:'待发送',waiting:'待配置',processing:'发送中',sent:'已发送',failed:'发送失败',unknown:'结果待核查'}
export function feedbackTone(status: number | string) { return status === 5 || status === 'sent' ? 'success' : status === 6 ? 'neutral' : status === 'failed' || status === 'unknown' ? 'danger' : status === 3 || status === 'waiting' ? 'warning' : 'info' }

export { newSubmissionId } from '../utils/submissionId.ts'
