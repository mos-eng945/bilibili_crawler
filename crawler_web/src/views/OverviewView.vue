<script setup>
import { ref } from 'vue'
import { Search } from '@lucide/vue'

const categories = [
  { id: 'all', label: '全部' },
  { id: 'hot', label: '热搜' },
  { id: 'search', label: '搜索' },
  { id: 'up', label: 'UP 主' },
  { id: 'video', label: '视频' },
]

const selectedCategory = ref('all')
const searchQuery = ref('')
const columns = ref([])
</script>

<template>
  <section class="overview" aria-labelledby="overview-title">
    <header class="overview-header">
      <h1 id="overview-title">数据概览</h1>
    </header>

    <div class="overview-toolbar">
      <nav class="category-tabs" aria-label="数据类型">
        <button
          v-for="category in categories"
          :key="category.id"
          type="button"
          :class="{ 'is-active': selectedCategory === category.id }"
          :aria-pressed="selectedCategory === category.id"
          @click="selectedCategory = category.id"
        >
          {{ category.label }}
        </button>
      </nav>

      <label class="data-search">
        <Search :size="16" aria-hidden="true" />
        <span class="sr-only">搜索数据</span>
        <input v-model="searchQuery" type="search" placeholder="搜索数据" />
      </label>
    </div>

    <div class="data-table-shell">
      <div class="data-table-scroll">
        <table>
          <thead>
            <tr>
              <th class="row-number">序号</th>
              <th v-for="column in columns" :key="column">{{ column }}</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td class="empty-state" :colspan="columns.length + 1">暂无数据</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<style scoped>
.overview {
  --overview-border: #e3e5e9;
  --overview-border-strong: #d0d5dc;
  --overview-panel: #ffffff;
  --overview-surface: #f8f9fa;
  --overview-text: #1b1d22;
  --overview-muted: #626771;
  --overview-faint: #949aa3;
  --overview-accent: #fb7299;
  --overview-accent-soft: #fdeef4;

  display: flex;
  flex-direction: column;
  gap: 18px;
  height: clamp(560px, calc(100vh - 170px), 860px);
  min-height: 0;
  color: var(--overview-text);
}

.overview-header h1 {
  margin: 0;
  font-size: 28px;
  line-height: 1.2;
}

.overview-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  min-height: 48px;
  padding: 8px;
  background: var(--overview-panel);
  border: 1px solid var(--overview-border);
  border-radius: 8px;
}

.category-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.category-tabs button {
  height: 32px;
  padding: 0 12px;
  color: var(--overview-muted);
  background: transparent;
  border: 0;
  border-radius: 5px;
  cursor: pointer;
}

.category-tabs button:hover {
  color: var(--overview-text);
  background: var(--overview-surface);
}

.category-tabs button.is-active {
  color: #a7395d;
  background: var(--overview-accent-soft);
}

.data-search {
  display: flex;
  flex: 0 1 300px;
  align-items: center;
  gap: 8px;
  height: 36px;
  min-width: 180px;
  padding: 0 11px;
  color: var(--overview-faint);
  background: var(--overview-surface);
  border: 1px solid var(--overview-border);
  border-radius: 6px;
}

.data-search:focus-within {
  border-color: var(--overview-accent);
  box-shadow: 0 0 0 2px rgba(251, 114, 153, 0.12);
}

.data-search input {
  width: 100%;
  min-width: 0;
  padding: 0;
  background: transparent;
  border: 0;
  outline: 0;
}

.data-table-shell {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  background: var(--overview-panel);
  border: 1px solid var(--overview-border);
  border-radius: 8px;
}

.data-table-scroll {
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow: auto;
}

table {
  width: 100%;
  min-width: max-content;
  border-spacing: 0;
  border-collapse: separate;
}

th {
  position: sticky;
  top: 0;
  z-index: 2;
  min-width: 140px;
  padding: 10px 14px;
  color: var(--overview-muted);
  text-align: left;
  white-space: nowrap;
  background: #f1f3f5;
  border-bottom: 1px solid var(--overview-border-strong);
  font-size: 11px;
  font-weight: 650;
}

td {
  padding: 11px 14px;
  border-bottom: 1px solid #eef0f2;
}

th.row-number,
td.row-number {
  position: sticky;
  left: 0;
  min-width: 64px;
  width: 64px;
  text-align: right;
}

th.row-number {
  z-index: 3;
}

.empty-state {
  height: 280px;
  color: var(--overview-faint);
  text-align: center;
  vertical-align: middle;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

@media (max-width: 760px) {
  .overview {
    height: auto;
    min-height: calc(100vh - 230px);
  }

  .overview-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .data-search {
    flex-basis: 36px;
    width: 100%;
  }

  .data-table-shell {
    min-height: 480px;
  }
}
</style>
