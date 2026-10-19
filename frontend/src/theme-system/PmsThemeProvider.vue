<script setup lang="ts">
import { provide, watch, onBeforeUnmount } from 'vue'
import { createThemeSession, type ThemeStorage } from './core'
import { themeSessionKey } from './context'
import './theme.css'
const props=defineProps<{userId:string|number|null;environment?:string;publicUser?:string}>()
let storage:ThemeStorage|undefined
try{storage=window.localStorage}catch{/* The switcher reports unavailable persistence when used. */}
const session=createThemeSession({environment:props.environment??location.origin,root:document.documentElement,storage,events:window,publicUser:props.publicUser})
provide(themeSessionKey,session)
watch(()=>props.userId,id=>session.setUser(id),{immediate:true})
onBeforeUnmount(()=>session.dispose())
</script>
<template><slot /></template>
