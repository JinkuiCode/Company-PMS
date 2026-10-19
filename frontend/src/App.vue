<template>
  <el-config-provider :table="PMS_TABLE_CONFIG">
    <PmsThemeProvider :user-id="themeUserId" public-user="public"><router-view /></PmsThemeProvider>
  </el-config-provider>
</template>
<script setup lang="ts">
import { PMS_TABLE_CONFIG } from '@/config/listUi'
import {computed} from 'vue'
import {getActivePinia} from 'pinia'
import {PmsThemeProvider} from '@/theme-system'
// Observe an existing identity without creating a login store on public guide routes.
const pinia=getActivePinia()
const themeUserId=computed(()=>pinia?.state.value.auth?.user?.id??'public')
</script>
