import { createRouter, createWebHistory } from 'vue-router'

//@指向src目录,在vite.config.js中配置了
import { authenticated } from '@/auth'
import DataAnalysisView from '@/views/DataAnalysisView.vue'
import ExportView from '@/views/ExportView.vue'
import ImportView from '@/views/ImportView.vue'
import IndexView from '@/views/IndexView.vue'
import LoginPageView from '@/views/LoginPageView.vue'
import OverviewView from '@/views/OverviewView.vue'
import ProjectIntroView from '@/views/ProjectIntroView.vue'
import RegisterView from '@/views/RegisterView.vue'
import ReportsView from '@/views/ReportsView.vue'
import SearchHistoryView from '@/views/SearchHistoryView.vue'
import SettingsView from '@/views/SettingsView.vue'
import UserView from '@/views/UserView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),//vite中使用import.meta.env.BASE_URL获取基础路径
  routes: [
    {
      path: '/',
      component: IndexView,
      meta: { requiresAuth: true },// 需要认证
      children: [
        { path: '', redirect: '/overview' },
        { path: 'overview', name: 'overview', component: OverviewView },
        { path: 'project', name: 'project', component: ProjectIntroView },
        { path: 'analysis', name: 'analysis', component: DataAnalysisView },
        { path: 'history', name: 'history', component: SearchHistoryView },
        { path: 'reports', name: 'reports', component: ReportsView },
        { path: 'settings', name: 'settings', component: SettingsView },
        { path: 'user', name: 'user', component: UserView },
        { path: 'import', name: 'import-data', component: ImportView },
        { path: 'export', name: 'export-data', component: ExportView },
      ],
    },
    {
      path: '/login',
      name: 'login',
      component: LoginPageView,
    },
    {
      path: '/register',
      name: 'register',
      component: RegisterView,
    },
    { path: '/:pathMatch(.*)*', redirect: '/project' },//匹配所有未定义的路由,重定向到/project
  ],
  /** 滚动行为 切换时返回顶部 */
  scrollBehavior() {
    return { top: 0 }
  },
})
/** to即将进入某个路由, from从哪个路由离开 */
router.beforeEach((to) => {
  /**认证和授权 */
  if (to.meta.requiresAuth && !authenticated.value) {
    return {
      name: 'login',
      query: { redirect: to.fullPath },//表示当前目标路由的完整 URL 路径，包含查询参数和哈希值,登录后可以跳转回原来的页面
    }
  }
  /**如果已经认证,访问登陆和注册页面时重定向到项目介绍页 */
  if ((to.name === 'login' || to.name === 'register') && authenticated.value) {
    return { name: 'project' }
  }

  return true
})

export default router//导出路由
