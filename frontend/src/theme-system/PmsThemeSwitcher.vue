<script setup lang="ts">
import { ref, onBeforeUnmount } from 'vue'
import { ArrowDown, Check } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { THEMES } from './core'
import { useThemeSession } from './context'
const session=useThemeSession(),theme=ref(session.theme),active=ref(session.active)
const stop=session.subscribe(()=>{theme.value=session.theme;active.value=session.active})
onBeforeUnmount(stop)
function choose(value:unknown){const result=session.choose(value);if(result.applied&&!result.persisted)ElMessage.warning('外观已切换，当前浏览器无法记住设置')}
</script>
<template>
  <el-dropdown trigger="click" popper-class="pms-theme-switcher-popup" @command="choose"><el-button class="pms-theme-switcher" :disabled="!active" aria-label="切换外观"><span class="pms-theme-swatch" :style="{background:THEMES[theme].brand}"></span>{{THEMES[theme].name}}<el-icon><ArrowDown /></el-icon></el-button><template #dropdown><el-dropdown-menu class="pms-theme-menu"><el-dropdown-item v-for="(item,id) in THEMES" :key="id" :command="id" :aria-current="theme===id?'true':undefined"><span class="pms-theme-swatch" :style="{background:item.brand}"></span>{{item.name}}<el-icon v-if="theme===id" aria-hidden="true"><Check /></el-icon></el-dropdown-item></el-dropdown-menu></template></el-dropdown>
</template>
