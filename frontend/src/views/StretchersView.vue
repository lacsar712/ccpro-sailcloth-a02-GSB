<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api'

const openTags = ref([])
const rolls = ref([])
const error = ref('')
const busy = ref(false)
const form = reactive({
  rollId: null,
  stretcherNo: '',
})

const statusLabel = { raw: '原布', dipping: '浸渍中', cured: '已固化' }

async function load() {
  error.value = ''
  try {
    const [t, r] = await Promise.all([
      api.get('/stretcher-tags/', { params: { open: 1 } }),
      api.get('/rolls/'),
    ])
    openTags.value = t.data.results || t.data
    rolls.value = r.data.results || r.data
    if (!form.rollId) {
      const first = availableRolls.value[0]
      if (first) form.rollId = first.id
    }
  } catch {
    error.value = '绷架占用数据加载失败'
  }
}

const rollById = computed(() => {
  const m = new Map()
  for (const r of rolls.value) m.set(r.id, r)
  return m
})

const occupiedNos = computed(
  () => new Set(openTags.value.map((t) => t.stretcherNo))
)

// 可占架的卷：未固化且当前没有未归还牌
const availableRolls = computed(() =>
  rolls.value.filter(
    (r) => r.status !== 'cured' && r.stretcherNo == null
  )
)

const board = computed(() =>
  Array.from({ length: 99 }, (_, i) => {
    const no = i + 1
    const tag = openTags.value.find((t) => t.stretcherNo === no)
    return { no, busy: Boolean(tag), tag }
  })
)

async function checkout() {
  error.value = ''
  busy.value = true
  try {
    await api.post('/stretcher-tags/', {
      rollId: form.rollId,
      stretcherNo: Number(form.stretcherNo),
    })
    form.stretcherNo = ''
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || '占架失败'
  } finally {
    busy.value = false
  }
}

async function returnTag(tag) {
  error.value = ''
  busy.value = true
  try {
    await api.post(`/stretcher-tags/${tag.id}/return_tag/`)
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || '归还失败'
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="stretcher-page">
    <h1>绷架占用</h1>
    <p class="sub">
      原布改为「浸渍中」前，须先占用一张绷架牌。绷架号 1–99；同一架号未归还前只能占一卷，同一卷未归还牌至多一张；已固化卷禁止新占。
    </p>
    <p v-if="error" class="error">{{ error }}</p>

    <form class="panel row" @submit.prevent="checkout">
      <label>布卷
        <select v-model.number="form.rollId" required>
          <option v-if="!availableRolls.length" disabled value="">无可占架布卷</option>
          <option
            v-for="r in availableRolls"
            :key="r.id"
            :value="r.id"
          >
            {{ r.rollCode }} · {{ r.loftName }} · {{ statusLabel[r.status] || r.status }}
          </option>
        </select>
      </label>
      <label>绷架号（1–99）
        <input
          v-model.number="form.stretcherNo"
          type="number"
          min="1"
          max="99"
          step="1"
          required
        />
      </label>
      <button class="btn" type="submit" :disabled="busy || !form.rollId">占出</button>
      <p class="hint" style="margin:0">已占用：{{ occupiedNos.size }} / 99</p>
    </form>

    <section class="panel">
      <h2 class="feed-title">未归还占用牌</h2>
      <table v-if="openTags.length">
        <thead>
          <tr>
            <th>绷架号</th>
            <th>布卷</th>
            <th>帆布间</th>
            <th>占架人</th>
            <th>占出时刻</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="tag in openTags" :key="tag.id">
            <td><strong>{{ tag.stretcherNo }} 号</strong></td>
            <td>{{ tag.rollCode }}</td>
            <td>{{ tag.loftName }}</td>
            <td>{{ tag.holderName }}</td>
            <td>{{ new Date(tag.checkedOutAt).toLocaleString() }}</td>
            <td>
              <button
                class="btn secondary"
                type="button"
                :disabled="busy"
                @click="returnTag(tag)"
              >
                归还
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="hint" style="margin:0">当前没有未归还占用牌</p>
    </section>

    <section class="panel">
      <h2 class="feed-title">绷架架面</h2>
      <div class="rack-board">
        <span
          v-for="cell in board"
          :key="cell.no"
          class="rack-cell"
          :class="{ occupied: cell.busy }"
          :title="cell.busy ? `${cell.no} 号：${cell.tag.rollCode}（${cell.tag.holderName}）` : `${cell.no} 号空闲`"
        >
          {{ cell.no }}
        </span>
      </div>
      <p class="hint" style="margin-top:10px">金色为占用中、未归还。</p>
    </section>
  </div>
</template>
