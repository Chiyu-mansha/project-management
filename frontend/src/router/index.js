import { createRouter, createWebHistory } from 'vue-router'
import { session } from '../auth/session.js'
import Home from '../views/Home.vue'
import FaqManage from '../views/FaqManage.vue'
import QaChat from '../views/QaChat.vue'
import ActivityList from '../views/ActivityList.vue'
import ActivityForm from '../views/ActivityForm.vue'
import ActivityDetail from '../views/ActivityDetail.vue'
import RegistrationEntry from '../views/RegistrationEntry.vue'
import Login from '../views/Login.vue'
import Register from '../views/Register.vue'
import Profile from '../views/Profile.vue'
import Account from '../views/Account.vue'
import Recommend from '../views/Recommend.vue'
import Notifications from '../views/Notifications.vue'
import Browse from '../views/Browse.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Home },
    { path: '/faqs', component: FaqManage, meta: { role: 'organizer' } },
    { path: '/qa', component: QaChat, meta: { role: 'student' } },
    { path: '/activities', component: ActivityList, meta: { role: 'organizer' } },
    { path: '/activities/new', component: ActivityForm, meta: { role: 'organizer' } },
    { path: '/activities/:id', component: ActivityDetail },
    { path: '/activities/:id/edit', component: ActivityForm, meta: { role: 'organizer' } },
    { path: '/browse', component: Browse },
    { path: '/registrations', component: RegistrationEntry },
    { path: '/login', component: Login },
    { path: '/register', component: Register },
    { path: '/profile', component: Profile },
    { path: '/account', component: Account },
    { path: '/recommend', component: Recommend },
    { path: '/notifications', component: Notifications },
  ],
})

router.beforeEach((to) => {
  const isPublic = to.path === '/login' || to.path === '/register'
  if (!isPublic && !session.value) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (isPublic && session.value) {
    return { path: session.value.role === 'organizer' ? '/browse' : '/' }
  }
  // 发布者没有"工作台选择页"，首页直接进活动广场
  if (to.path === '/' && session.value?.role === 'organizer') {
    return { path: '/browse' }
  }
  // 角色限制：发布者/学生专属页面，未授权角色跳回对应入口
  if (to.meta.role === 'organizer' && session.value?.role !== 'organizer') {
    return { path: '/browse' }
  }
  if (to.meta.role === 'student' && session.value?.role !== 'student') {
    return { path: '/browse' }
  }
})

export default router
