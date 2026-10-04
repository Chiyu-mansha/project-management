import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import FaqManage from '../views/FaqManage.vue'
import QaChat from '../views/QaChat.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Home },
    { path: '/faqs', component: FaqManage },
    { path: '/qa', component: QaChat },
  ],
})
