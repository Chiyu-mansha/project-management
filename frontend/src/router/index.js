import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import FaqManage from '../views/FaqManage.vue'
import QaChat from '../views/QaChat.vue'
import ActivityList from '../views/ActivityList.vue'
import ActivityForm from '../views/ActivityForm.vue'
import ActivityDetail from '../views/ActivityDetail.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Home },
    { path: '/faqs', component: FaqManage },
    { path: '/qa', component: QaChat },
    { path: '/activities', component: ActivityList },
    { path: '/activities/new', component: ActivityForm },
    { path: '/activities/:id', component: ActivityDetail },
    { path: '/activities/:id/edit', component: ActivityForm },
  ],
})
