<script setup lang="ts">
import { computed } from 'vue'
import { Folder, DataAnalysis, Setting, Menu } from '@element-plus/icons-vue'
import { PmsThemeProvider, PmsThemeSwitcher } from '@/theme-system'
import { useAuthStore } from '@/stores/auth'
import { stats } from './fixtures'
const auth=useAuthStore()
const userId=computed(()=>auth.user?.id??null)
</script>
<template>
  <PmsThemeProvider :user-id="userId" environment="isolated-archive-5184">
    <div class="archive-theme-pilot" :data-list-reads="stats.listReads" :data-memory-draft-writes="stats.memoryDraftWrites" :data-blocked-writes="stats.blockedWrites">
      <header class="pilot-oa-top"><strong>OA <span>AELsystem</span></strong><span>主题试点</span></header>
      <aside class="pilot-oa-side"><span>协同办公</span><span>公司系统</span><span>报表</span><span>人事</span><span>研发项目</span><span>公共功能</span><strong>PMS</strong></aside>
      <section class="pilot-pms"><aside class="pilot-rail"><strong>P</strong><el-icon><Folder /></el-icon><el-icon><DataAnalysis /></el-icon><el-icon><Setting /></el-icon></aside>
        <header class="pilot-header"><el-icon><Menu /></el-icon><h1>项目档案</h1><span>隔离试点 · 模拟数据</span><PmsThemeSwitcher /></header>
        <main class="pilot-page"><router-view /></main>
      </section>
    </div>
  </PmsThemeProvider>
</template>
<style>
html[data-pms-theme]{--pms-host-top:55px;}
@media(max-width:560px){html[data-pms-theme]{--pms-host-top:38px;}}
</style>
<style scoped>
.archive-theme-pilot{height:100dvh;display:grid;grid-template-columns:172px minmax(0,1fr);grid-template-rows:48px minmax(0,1fr);background:#eef2f7;}
.pilot-oa-top{grid-column:1/-1;display:flex;align-items:center;justify-content:space-between;padding:0 18px;background:#fff;color:#225ebd;border-bottom:1px solid #e7ecf2;font-size:12px;}.pilot-oa-top strong{font-size:14px;}.pilot-oa-top strong span{margin-left:8px;}
.pilot-oa-side{display:flex;flex-direction:column;gap:6px;padding-top:20px;background:#2460be;color:#fff;font-size:13px;}.pilot-oa-side>*{padding:14px 22px;}.pilot-oa-side>span:first-child{font-size:12px;opacity:.8;}.pilot-oa-side strong{background:#134995;font-weight:500;}
.pilot-pms{display:grid;grid-template-columns:64px minmax(0,1fr);grid-template-rows:44px minmax(0,1fr);margin:6px 6px 6px 8px;border:1px solid var(--pms-border);background:var(--pms-bg);min-width:0;min-height:0;overflow:hidden;}
.pilot-rail{grid-row:1/-1;background:#fff;border-right:1px solid var(--pms-border);display:flex;align-items:center;flex-direction:column;gap:24px;padding-top:6px;color:var(--pms-text-secondary);font-size:18px;}.pilot-rail strong{display:grid;place-items:center;width:30px;height:30px;color:var(--pms-primary);background:var(--pms-primary-soft);border:1px solid var(--pms-accent-border);border-radius:4px;font-size:13px;}
.pilot-header{display:flex;align-items:center;gap:12px;background:#fff;padding:0 12px;border-bottom:1px solid var(--pms-border);min-width:0;}.pilot-header h1{font-size:14px;margin:0;font-weight:600;white-space:nowrap;}.pilot-header>span{margin-left:auto;color:var(--pms-text-muted);font-size:11px;}
.pilot-page{min-width:0;min-height:0;overflow:hidden;padding:6px;}
@media(max-width:850px){.archive-theme-pilot{grid-template-columns:48px minmax(0,1fr);}.pilot-oa-side>*{padding:14px 0;text-align:center;font-size:0;}.pilot-oa-side strong{font-size:12px;}.pilot-pms{grid-template-columns:48px minmax(0,1fr);margin-left:4px;}.pilot-header>span{display:none;}.pilot-header>.el-dropdown{margin-left:auto;}}
@media(max-width:560px){.archive-theme-pilot{grid-template-columns:minmax(0,1fr);grid-template-rows:38px minmax(0,1fr);}.pilot-oa-side{display:none;}.pilot-pms{margin:0;grid-template-columns:40px minmax(0,1fr);}.pilot-header{padding:0 8px;gap:8px;}.pilot-page{padding:4px;}}
</style>
