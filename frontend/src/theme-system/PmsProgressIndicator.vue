<script setup lang="ts">
import {computed} from 'vue'
import {progressAppearance} from './progress'
const props=withDefaults(defineProps<{label:string;value:number|string|null|undefined;completed?:number;total?:number;decimals?:number}>(),{decimals:1})
const appearance=computed(()=>progressAppearance(props.value,props.completed!==undefined&&props.total!==undefined?{completed:props.completed,total:props.total}:undefined))
const valueText=computed(()=>{
  if(!appearance.value.valid)return '无进度数据'
  const stage=appearance.value.percentage===0?'尚未开始':({low:'前期推进',mid:'持续推进，尚未完成',complete:'已完成',empty:'无有效统计行数'})[appearance.value.stage]
  const counts=props.completed!==undefined&&props.total!==undefined?`，${props.completed} / ${props.total} 行`:''
  return `${appearance.value.percentage.toFixed(props.decimals)}%，${stage}${counts}`
})
</script>
<template>
  <div class="pms-progress-indicator" :data-progress-stage="appearance.stage" :style="{'--pms-progress-color':appearance.token}" role="progressbar" :aria-label="label" :aria-valuenow="appearance.valid?appearance.percentage:undefined" aria-valuemin="0" aria-valuemax="100" :aria-valuetext="valueText" :title="`${label}：${valueText}`">
    <span class="pms-progress-indicator__track"><span :style="{width:appearance.percentage+'%'}" /></span><span class="pms-progress-indicator__value">{{appearance.valid?appearance.percentage.toFixed(decimals)+'%':''}}</span>
  </div>
</template>
<style scoped>
.pms-progress-indicator{display:flex;align-items:center;gap:8px;min-width:0;width:100%;height:100%;font-size:12px;font-variant-numeric:tabular-nums;color:var(--pms-text)}
.pms-progress-indicator__track{flex:1;min-width:20px;height:5px;border-radius:3px;overflow:hidden;background:var(--pms-border-soft)}
.pms-progress-indicator__track>span{display:block;height:100%;border-radius:inherit;background:var(--pms-progress-color)}
.pms-progress-indicator__value{min-width:44px;text-align:right;white-space:nowrap}
.pms-progress-indicator[aria-valuenow="0"] .pms-progress-indicator__value{color:var(--pms-progress-low)}
</style>
