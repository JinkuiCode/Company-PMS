export type ProgressStage='low'|'mid'|'complete'|'empty'
const colors={low:'#c83434',mid:'#b68b00',complete:'#087e65',empty:'#6f7b8b'} as const
export function progressAppearance(value:unknown,counts?:{completed:unknown;total:unknown}){
  const raw=value===null||value===undefined||value===''?NaN:Number(value)
  const percentage=Number.isFinite(raw)?Math.min(100,Math.max(0,raw)):0
  let stage:ProgressStage=!Number.isFinite(raw)?'empty':percentage<50?'low':percentage<100?'mid':'complete'
  if(counts){
    const completed=Number(counts.completed),total=Number(counts.total)
    if(!Number.isFinite(completed)||!Number.isFinite(total)||total<=0)stage='empty'
    else if(stage==='complete'&&completed<total)stage='mid'
  }
  return {percentage,valid:Number.isFinite(raw),stage,color:colors[stage],token:stage==='empty'?'var(--pms-text-muted)':`var(--pms-progress-${stage},${colors[stage]})`}
}
