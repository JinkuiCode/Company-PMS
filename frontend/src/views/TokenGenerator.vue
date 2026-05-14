<template>
  <div class="token-gen">
    <h2>OA 单点登录配置工具</h2>
    <p class="desc">为泛微 e-Cology 9.x 配置 PMS 单点登录，员工点击 OA 菜单即可自动登录</p>

    <!-- 正确配置步骤 -->
    <el-card shadow="hover" class="guide-card">
      <template #header><span class="card-title">正确配置步骤</span></template>
      <div class="steps">
        <p><b>第 1 步：</b>登录 OA 管理后台 → <b>统一认证中心 → 认证接入管理</b></p>
        <p><b>第 2 步：</b>查看是否有「<b>注册应用</b>」或「<b>新建应用</b>」按钮，点击后填写以下信息：</p>
        <table class="config-table">
          <tr><td>应用名称</td><td><code>PMS 项目管理系统</code></td></tr>
          <tr><td>应用地址</td><td><code>{{ baseUrl }}/</code></td></tr>
          <tr><td>回调/重定向地址</td><td><code>{{ baseUrl }}/sso/login</code></td></tr>
          <tr><td>需要传递的用户属性</td><td>登录账号（loginid）、用户姓名、部门</td></tr>
        </table>
        <p style="margin-top:12px"><b>第 3 步：</b>进入 <b>门户引擎 → 门户菜单</b>，新建菜单，链接地址设为：</p>
        <div class="url-box">
          <code>{{ baseUrl }}/sso/login</code>
          <el-button size="small" type="primary" @click="copyText(baseUrl + '/sso/login')">复制</el-button>
        </div>
        <p style="margin-top:12px; color:#E6A23C;"><b>注意：</b>如果认证接入管理中有「Token 方式」或「密钥」相关配置，请截图发给我，即可确定最终方案</p>
      </div>
    </el-card>

    <!-- 测试 SSO -->
    <el-card shadow="hover" class="test-card">
      <template #header><span class="card-title">测试 SSO 登录（测试账号：A000645）</span></template>
      <el-form :model="testForm" label-width="110px" style="max-width:500px;">
        <el-form-item label="OA 登录名">
          <el-input v-model="testForm.loginid" placeholder="OA 登录名" />
        </el-form-item>
        <el-form-item label="姓名（可选）">
          <el-input v-model="testForm.username" placeholder="用户姓名" />
        </el-form-item>
        <el-form-item>
          <el-button type="success" @click="testSSO">模拟 OA 跳转登录</el-button>
        </el-form-item>
      </el-form>
      <p v-if="ssoUrl" class="test-result">
        模拟链接：<code>{{ ssoUrl }}</code>
        <el-button size="small" type="primary" style="margin-left:8px" @click="openUrl">打开测试</el-button>
      </p>
    </el-card>

    <!-- HMAC 签名链接 -->
    <el-card shadow="hover" class="form-card">
      <template #header><span class="card-title">HMAC 签名链接（更安全，一次性链接）</span></template>
      <el-form :model="form" label-width="110px" style="max-width:500px;">
        <el-form-item label="登录名">
          <el-input v-model="form.loginid" placeholder="OA 用户登录名" />
        </el-form-item>
        <el-form-item label="用户姓名">
          <el-input v-model="form.username" placeholder="显示名称" />
        </el-form-item>
        <el-form-item label="部门">
          <el-input v-model="form.dept" placeholder="所属部门（可选）" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="generate">生成带签名的 SSO 链接</el-button>
        </el-form-item>
      </el-form>
      <div v-if="hmacUrl" class="result-box">
        <div class="url-box">
          <code>{{ hmacUrl }}</code>
          <el-button size="small" type="primary" @click="copyUrl">复制</el-button>
          <el-button size="small" @click="openHmacUrl">测试</el-button>
        </div>
        <p class="hint">签名链接 5 分钟内有效</p>
      </div>
    </el-card>

    <!-- 备选变量格式 -->
    <el-card shadow="hover" class="alt-card">
      <template #header><span class="card-title">备选：OA 菜单如果支持系统变量，尝试以下格式</span></template>
      <div class="url-options">
        <div class="url-opt" v-for="(item, i) in urlFormats" :key="i">
          <el-tag type="info" size="small">{{ item.label }}</el-tag>
          <code>{{ item.value }}</code>
          <el-button size="small" @click="copyText(item.value)">复制</el-button>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

const form = reactive({ loginid: '', username: '', dept: '' })
const hmacUrl = ref('')

// 测试表单默认 A000645
const testForm = reactive({ loginid: 'A000645', username: '管理员' })
const ssoUrl = ref('')

const baseUrl = computed(() => window.location.origin)

const urlFormats = [
  { label: '表达式', value: `${baseUrl.value}/sso/login?loginid={UserContext.GetValue("LoginId")}` },
  { label: '变量1', value: `${baseUrl.value}/sso/login?loginid=$LoginId$` },
  { label: '变量2', value: `${baseUrl.value}/sso/login?loginid=$loginid$` },
  { label: '变量3', value: `${baseUrl.value}/sso/login?loginid={loginid}` },
]

async function generate() {
  if (!form.loginid || !form.username) {
    ElMessage.warning('请填写登录名和用户姓名')
    return
  }
  const res: any = await request.post('/sso/generate-url', {
    loginid: form.loginid,
    username: form.username,
    dept: form.dept,
  })
  hmacUrl.value = baseUrl.value + res.url
}

function testSSO() {
  if (!testForm.loginid) {
    ElMessage.warning('请填写 OA 登录名')
    return
  }
  const params = new URLSearchParams()
  params.set('loginid', testForm.loginid)
  if (testForm.username) params.set('username', testForm.username)
  ssoUrl.value = `${baseUrl.value}/sso/login?${params.toString()}`
  window.open(ssoUrl.value, '_blank')
}

function copyUrl() {
  navigator.clipboard.writeText(hmacUrl.value)
  ElMessage.success('已复制')
}
function copyText(text: string) {
  navigator.clipboard.writeText(text)
  ElMessage.success('已复制')
}
function openUrl() {
  window.open(ssoUrl.value, '_blank')
}
function openHmacUrl() {
  window.open(hmacUrl.value, '_blank')
}
</script>

<style scoped>
.token-gen { padding: 24px; max-width: 860px; }
.token-gen h2 { margin: 0 0 4px 0; }
.desc { color: #909399; margin-bottom: 20px; }
.guide-card { margin-bottom: 16px; border-left: 4px solid #67C23A; }
.alt-card { margin-bottom: 16px; }
.test-card { margin-bottom: 16px; }
.form-card { margin-bottom: 16px; }

.config-table { width: 100%; border-collapse: collapse; margin: 12px 0; }
.config-table td { padding: 8px 12px; border: 1px solid #ebeef5; }
.config-table td:first-child { background: #f5f7fa; font-weight: 500; width: 150px; }

.url-options { margin: 12px 0; display: flex; flex-direction: column; gap: 8px; }
.url-opt { display: flex; align-items: center; gap: 8px; background: #f5f7fa; padding: 8px 12px; border-radius: 4px; }
.url-opt code { font-size: 13px; word-break: break-all; flex: 1; }

.url-box { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.url-box code { background: #f5f7fa; padding: 8px 12px; border-radius: 4px; word-break: break-all; flex: 1;}

.result-box { margin-top: 16px; }
.test-result { margin-top: 12px; color: #67C23A; }
.test-result code { background: #f5f7fa; padding: 4px 8px; border-radius: 3px; font-size: 13px; }

.hint { color: #909399; font-size: 13px; margin-top: 12px; }
.card-title { font-weight: 600; color: #303133; }
.steps p { margin: 6px 0; line-height: 1.8; }
</style>
