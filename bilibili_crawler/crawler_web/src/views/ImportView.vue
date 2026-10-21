<template>
  <section class="route-page">
    <p class="route-page__label">导入</p>
    <h1>导入数据</h1>
    <p class="route-page__description">在这里加载已有的采集结果。</p>
  </section>
</template>

<style scoped>
.route-page {
  padding-top: 8px;
}

.route-page__label {
  margin: 0 0 12px;
  color: var(--accent);
  font-size: 12px;
  font-weight: 600;
}

.route-page h1 {
  margin: 0;
  color: var(--text-strong);
  font-size: 38px;
  line-height: 1.2;
}

.route-page__description {
  margin: 14px 0 0;
  color: var(--text-muted);
  font-size: 14px;
}
</style>
