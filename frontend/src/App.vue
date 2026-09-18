<template>
  <el-config-provider :table="PMS_TABLE_CONFIG">
    <router-view />
  </el-config-provider>
</template>
<script setup lang="ts">
import { PMS_TABLE_CONFIG } from '@/config/listUi'
</script>
