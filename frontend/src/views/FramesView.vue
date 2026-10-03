<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api'

const tags = ref([])
const rolls = ref([])
const error = ref('')
const busy = ref(false)
const form = reactive({
  rollId: null,
  frameNo: '',
})

const openTags = computed(() => tags.value.filter((t) => !t.returnedAt))

// 已固化卷禁止新占；已有未归还牌的卷也不再列出
const occupiableRolls = computed(() => {
  const held = new Set(openTags.value.map((t) => t.rollId))
  return rolls.value.filter((r) => r.status !== 'cured' && !held.has(r.id))
})

async function load() {
  error.value = ''
  try {
    const [t, r] = await Promise.all([api.get('/frame-tags/'), api.get('/rolls/')])
    tags.value = t.data.results || t.data
    rolls.value = r.data.results || r.data
    if (!form.rollId && occupiableRolls.value.length) {
      form.rollId = occupiableRolls.value[0].id
    }
  } catch {
    error.value = '绷架占用加载失败'
  }
}

function firstError(data, fallback) {
  if (!data) return fallback
  return (
    data.frameNo?.[0] ||
    data.rollId?.[0] ||
    data.detail ||
    data.nonFieldErrors?.[0] ||
    fallback
  )
}

async function occupy() {
  error.value = ''
  busy.value = true
  try {
    await api.post('/frame-tags/', {
      rollId: form.rollId,
      frameNo: form.frameNo === '' ? null : Number(form.frameNo),
    })
    form.frameNo = ''
    await load()
  } catch (e) {
    // 占架被挡（撞号/已固化/已有牌）只提示，不影响本页与晾晒架继续使用
    error.value = firstError(e.response?.data, '占架失败')
  } finally {
    busy.value = false
  }
}

async function release(tag) {
  error.value = ''
  busy.value = true
  try {
    await api.post(`/frame-tags/${tag.id}/return/`)
    await load()
  } catch (e) {
    error.value = firstError(e.response?.data, '归还失败')
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <h1>绷架占用</h1>
    <p class="sub">
      原布改浸渍中前须先占一张未归还牌；绷架号 1–99，同号未归还期间不得被第二卷占用，每卷至多一张未归还牌。已固化卷禁止新占。
    </p>
    <p v-if="error" class="error">{{ error }}</p>

    <form class="panel row" @submit.prevent="occupy">
      <label>布卷
        <select v-model.number="form.rollId" required>
          <option v-for="r in occupiableRolls" :key="r.id" :value="r.id">
            {{ r.rollCode }} · {{ r.loftName }}
          </option>
        </select>
      </label>
      <label>绷架号（1–99）
        <input v-model="form.frameNo" type="number" min="1" max="99" step="1" required />
      </label>
      <button class="btn" type="submit" :disabled="busy || !occupiableRolls.length">占出</button>
      <p v-if="!occupiableRolls.length" class="hint" style="margin:0">暂无可占架布卷</p>
    </form>

    <section class="panel">
      <h2 style="margin-top:0">未归还占用牌</h2>
      <table v-if="openTags.length">
        <thead>
          <tr>
            <th>布卷</th>
            <th>帆布间</th>
            <th>绷架号</th>
            <th>占出时刻</th>
            <th>占架人</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="tag in openTags" :key="tag.id">
            <td>{{ tag.rollCode }}</td>
            <td>{{ tag.loftName }}</td>
            <td>{{ tag.frameNo }}</td>
            <td>{{ new Date(tag.occupiedAt).toLocaleString() }}</td>
            <td>{{ tag.occupiedByName }}</td>
            <td>
              <button class="btn secondary" type="button" :disabled="busy" @click="release(tag)">
                归还
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="hint" style="margin:0">当前没有未归还的绷架占用牌</p>
    </section>
  </div>
</template>
