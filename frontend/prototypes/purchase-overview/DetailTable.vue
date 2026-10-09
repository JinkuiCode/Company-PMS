<script setup>
defineProps({ rows: Array, activeId: String })
const emit = defineEmits(['open', 'select'])
</script>
<template>
  <table class="detail-table">
    <thead><tr><th>项目编号</th><th>产品线</th><th>物料编码</th><th>物料名称</th><th>申请单编号</th><th>行号</th><th>申请日期</th><th>申请单位</th><th>申请数量</th><th>累计下单数量</th><th>累计净入库数量</th><th>采购进度</th><th class="action-cell">操作</th></tr></thead>
    <tbody><tr v-for="r in rows" :key="r.id" :class="{ selected: activeId === r.id }" @click="emit('select', r)">
      <td>{{ r.code }}</td><td>{{ r.product }}</td><td>{{ r.material_code }}</td><td>{{ r.material }}</td><td>{{ r.bill }}</td><td class="number">{{ r.line }}</td><td>{{ r.date }}</td><td>{{ r.unit }}</td><td class="number">{{ r.requested }}</td><td class="number">{{ r.ordered }}</td><td class="number">{{ r.received }}</td><td><span :class="['pms-status', r.tone]">{{ r.progress_label }}</span></td><td class="action-cell"><button class="text-action" @click.stop="emit('open', r)">明细</button></td>
    </tr><tr v-if="!rows?.length"><td colspan="13" class="empty-cell">没有符合条件的申请行</td></tr></tbody>
  </table>
</template>
