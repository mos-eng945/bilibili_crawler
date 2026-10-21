<script setup>
defineProps({
  title: { type: String, required: true },
  description: { type: String, required: true },
  icon: { type: [Object, Function], required: true },
})
</script>

<template>
  <section class="placeholder">
    <p class="placeholder__eyebrow">工作区</p>
    <div class="placeholder__heading">
      <div class="placeholder__icon">
        <component :is="icon" :size="21" aria-hidden="true" />
      </div>
      <h1>{{ title }}</h1>
    </div>
    <p class="placeholder__description">{{ description }}</p>

    <div class="placeholder__empty">
      <strong>暂无数据</strong>
      <span>导入采集结果后显示内容。</span>
    </div>
  </section>
</template>

<style scoped>
.placeholder {
  min-height: calc(100vh - 250px);
}

.placeholder__eyebrow {
  margin: 0 0 16px;
  color: #fb7299;
  font-size: 12px;
  font-weight: 600;
}

.placeholder__heading {
  display: flex;
  align-items: center;
  gap: 14px;
}

.placeholder__icon {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  color: #626771;
  background: #ffffff;
  border: 1px solid #e3e5e9;
  border-radius: 8px;
}

.placeholder h1 {
  margin: 0;
  color: #1b1d22;
  font-size: 42px;
  font-weight: 700;
  line-height: 1.2;
}

.placeholder__description {
  max-width: 620px;
  margin: 20px 0 0;
  color: #626771;
  font-size: 14px;
  line-height: 1.8;
}

.placeholder__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 280px;
  margin-top: 54px;
  color: #949aa3;
  background: #ffffff;
  border: 1px solid #e3e5e9;
  border-radius: 8px;
}

.placeholder__empty strong {
  color: #626771;
  font-size: 14px;
  font-weight: 600;
}

.placeholder__empty span {
  margin-top: 7px;
  font-size: 12px;
}

@media (max-width: 760px) {
  .placeholder h1 {
    font-size: 36px;
  }

  .placeholder__empty {
    min-height: 220px;
    margin-top: 38px;
  }
}
</style>
