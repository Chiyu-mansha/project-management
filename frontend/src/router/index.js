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
import Recommend from '../views/Recommend.vue'
import Notifications from '../views/Notifications.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Home },
    { path: '/faqs', component: FaqManage },
    { path: '/qa', component: QaChat },
    { path: '/activities', component: ActivityList },
    { path: '/activities/new', component: ActivityForm },
    { path: '/activities/:id', component: ActivityDetail },
    { path: '/activities/:id/edit', component: ActivityForm },
    { path: '/registrations', component: RegistrationEntry },
    { path: '/login', component: Login },
    { path: '/register', component: Register },
    { path: '/profile', component: Profile },
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
    return { path: '/' }
  }
})

export default router
