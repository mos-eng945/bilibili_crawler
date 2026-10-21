<script setup>
import { Flame, FolderOpen, MessageCircle, MessageSquare, Users, Video } from '@lucide/vue'

const scopes = [
  {
    title: '视频信息',
    description: '标题、封面、简介、分区与播放、点赞、投币、收藏等互动快照。',
    icon: Video,
  },
  {
    title: '一级评论',
    description: '评论正文、发布时间、点赞、用户等级、IP 属地与图片地址；暂不含子评论正文。',
    icon: MessageSquare,
  },
  {
    title: '软字幕与 AI 字幕',
    description: '按分 P 和语言轨道保存字幕 JSON／SRT；画面中的硬字幕暂不支持。',
    icon: MessageCircle,
  },
  {
    title: '弹幕数据',
    description: '弹幕内容、出现时间、发送时间与权重；实际数量以平台返回为准(可能有延迟,因为字幕是从字幕随机抽取的,实际上并不完整)。',
    icon: MessageCircle,
  },
  {
    title: ' UP 主',
    description: 'UP 主基本信息、公开视频、',
    icon: Users,
  },
  {
    title: '视频搜索与热搜榜单',
    description: '关键词搜索结果,分区、标签与互动数据。热搜排名、展示词、关键词热度，以及各热搜词的关联视频。',
    icon: Flame,
  },
]

const analysisViews = [
  {
    index: '01',
    title: '数据总览',
    description: '集中查看数据集规模、时间范围和核心互动指标。',
  },
  {
    index: '02',
    title: '趋势分析',
    description: '观察评论、弹幕和互动数据随时间发生的变化。',
  },
  {
    index: '03',
    title: '内容对比',
    description: '对比视频、关键词和 UP 主之间的数据表现差异。',
  },
]
</script>

<template>
  <div class="project-intro">
    <section class="intro">
      <div class="intro__copy">
        <p class="eyebrow">项目介绍</p>
        <h2>对bilibili可视的数据，<br />进行采集并分析。</h2>
        <p class="intro__lead">
          面向 Bilibili 视频、一级评论、字幕、弹幕、搜索与热搜数据，提供统一的查看、筛选与对比入口。
          只对公开的数据进行采集和分析,不爬取任何私有数据。
        </p>
      </div>

      <aside class="dataset" aria-label="当前工作区状态">
        <div class="dataset__heading">
          <FolderOpen :size="17" aria-hidden="true" />
          <span>当前工作区</span>
        </div>
        <dl class="dataset__list">
          <div>
            <dt>数据集</dt>
            <dd>尚未载入</dd>
          </div>
          <div>
            <dt>数据时间</dt>
            <dd>—</dd>
          </div>
          <div>
            <dt>文件状态</dt>
            <dd>等待导入</dd>
          </div>
        </dl>
      </aside>
    </section>

    <section class="section">
      <div class="section__heading">
        <h2>爬取的数据范围</h2>
        <span>01 / Scope</span>
      </div>
      <div class="scope-grid">
        <article v-for="scope in scopes" :key="scope.title" class="scope-item">
          <div class="scope-item__icon">
            <component :is="scope.icon" :size="18" aria-hidden="true" />
          </div>
          <div>
            <h3>{{ scope.title }}</h3>
            <p>{{ scope.description }}</p>
          </div>
        </article>
      </div>
    </section>

    <section class="section">
      <div class="section__heading">
        <h2>分析视图</h2>
        <span>02 / Analysis</span>
      </div>
      <div class="analysis-grid">
        <article v-for="view in analysisViews" :key="view.index" class="analysis-item">
          <span class="analysis-item__index">{{ view.index }}</span>
          <div>
            <h3>{{ view.title }}</h3>
            <p>{{ view.description }}</p>
          </div>
        </article>
      </div>
    </section>

    <section class="project-note">
      <div>
        <span class="project-note__title">数据来源</span>
        <p>视频 · 一级评论 · 软字幕／AI 字幕 · 弹幕 · 视频搜索 · UP 主视频 · 热搜榜单</p>
      </div>
      <div>
        <span class="project-note__title">处理方式</span>
        <p>读取本地采集结果，保持原始文件不变。</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.project-intro {
  --overview-border: #e3e5e9;
  --overview-surface: #ffffff;
  --overview-text: #1b1d22;
  --overview-muted: #626771;
  --overview-faint: #949aa3;
  --overview-accent: #fb7299;
}

.intro {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(270px, 0.65fr);
  gap: 56px;
  align-items: end;
}

.eyebrow {
  margin: 0 0 16px;
  color: var(--overview-accent);
  font-size: 12px;
  font-weight: 600;
}

.intro h1 {
  max-width: 720px;
  margin: 0;
  color: var(--overview-text);
  font-size: 64px;
  font-weight: 700;
  line-height: 1.08;
}

.intro__lead {
  max-width: 670px;
  margin: 24px 0 0;
  color: var(--overview-muted);
  font-size: 15px;
  line-height: 1.8;
}

.dataset {
  padding: 20px;
  background: var(--overview-surface);
  border: 1px solid var(--overview-border);
  border-radius: 8px;
  box-shadow: 0 1px 2px rgba(27, 29, 34, 0.04);
}

.dataset__heading {
  display: flex;
  align-items: center;
  gap: 9px;
  padding-bottom: 16px;
  color: var(--overview-text);
  font-size: 13px;
  font-weight: 600;
}

.dataset__heading svg {
  color: var(--overview-accent);
}

.dataset__list {
  margin: 0;
}

.dataset__list div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 0;
  border-top: 1px solid var(--overview-border);
}

.dataset__list dt {
  color: var(--overview-faint);
  font-size: 12px;
}

.dataset__list dd {
  margin: 0;
  color: var(--overview-muted);
  font-size: 12px;
  text-align: right;
}

.section {
  margin-top: 68px;
}

.section__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--overview-border);
}

.section__heading h2 {
  margin: 0;
  color: var(--overview-text);
  font-size: 18px;
  font-weight: 650;
}

.section__heading span {
  color: var(--overview-faint);
  font-size: 11px;
}

.scope-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 44px;
}

.scope-item {
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr);
  gap: 15px;
  padding: 23px 0;
  border-bottom: 1px solid var(--overview-border);
}

.scope-item__icon {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  color: var(--overview-muted);
  background: var(--overview-surface);
  border: 1px solid var(--overview-border);
  border-radius: 8px;
}

.scope-item h3,
.analysis-item h3 {
  margin: 0;
  color: var(--overview-text);
  font-size: 14px;
  font-weight: 600;
}

.scope-item p,
.analysis-item p {
  margin: 7px 0 0;
  color: var(--overview-muted);
  font-size: 13px;
  line-height: 1.65;
}

.analysis-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 32px;
}

.analysis-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 14px;
  padding-top: 22px;
}

.analysis-item__index {
  color: var(--overview-accent);
  font-size: 11px;
  font-weight: 600;
  line-height: 1.7;
}

.project-note {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 40px;
  margin-top: 68px;
  padding: 24px 0;
  border-top: 1px solid var(--overview-border);
  border-bottom: 1px solid var(--overview-border);
}

.project-note__title {
  color: var(--overview-faint);
  font-size: 11px;
}

.project-note p {
  margin: 7px 0 0;
  color: var(--overview-muted);
  font-size: 13px;
}

@media (max-width: 1024px) {
  .intro {
    grid-template-columns: minmax(0, 1fr) 260px;
    gap: 34px;
  }

  .intro h1 {
    font-size: 50px;
  }

  .scope-grid {
    column-gap: 28px;
  }

  .analysis-grid {
    gap: 22px;
  }
}

@media (max-width: 760px) {
  .intro {
    grid-template-columns: minmax(0, 1fr);
    gap: 30px;
  }

  .intro h1 {
    font-size: 42px;
  }

  .intro__lead {
    margin-top: 19px;
  }

  .scope-grid,
  .analysis-grid,
  .project-note {
    grid-template-columns: minmax(0, 1fr);
  }

  .scope-grid {
    column-gap: 0;
  }

  .analysis-grid {
    gap: 0;
  }

  .analysis-item {
    padding-bottom: 20px;
    border-bottom: 1px solid var(--overview-border);
  }

  .project-note {
    gap: 20px;
  }
}

@media (max-width: 480px) {
  .intro h1 {
    font-size: 35px;
  }

  .section {
    margin-top: 52px;
  }

  .scope-item {
    grid-template-columns: 34px minmax(0, 1fr);
    gap: 12px;
  }

  .scope-item__icon {
    width: 34px;
    height: 34px;
  }
}
</style>
