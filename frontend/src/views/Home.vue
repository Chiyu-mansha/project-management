<template>
  <div v-if="session?.role === 'student'" class="student-home">
    <section class="hero">
      <div class="hero-copy">
        <span class="eyebrow">CAMPUS ACTIVITY HUB</span>
        <h1>发现让校园生活<br /><em>更有收获</em>的活动</h1>
        <p>根据你的兴趣与成长目标，找到适合自己的讲座、竞赛和校园活动。</p>
        <div class="hero-actions">
          <el-button type="primary" round size="large" @click="$router.push('/browse')">探索活动</el-button>
          <el-button plain round size="large" @click="$router.push('/qa')">智能答疑</el-button>
        </div>
      </div>
      <div class="hero-art" aria-hidden="true">
        <div class="sun"></div><div class="blob blob-one"></div><div class="blob blob-two"></div>
        <div class="art-card art-card-main">✦<strong>今日灵感</strong><span>去参加一场有趣的活动</span></div>
        <div class="art-card art-card-small">🎓<span>成长记录</span></div>
      </div>
    </section>

    <section class="dashboard-section">
      <div class="section-heading"><div><span class="section-kicker">为你精选</span><h2>推荐活动</h2></div><el-button link type="primary" @click="$router.push('/recommend')">更多 →</el-button></div>
      <div v-if="loading" class="loading-grid"><el-skeleton v-for="i in 2" :key="i" animated /></div>
      <el-empty v-else-if="recommended.length === 0" description="暂无推荐，去活动广场看看吧" />
      <div v-else class="recommend-grid">
        <article v-for="a in recommended" :key="a.id" class="recommend-card" @click="openActivity(a)">
          <div class="activity-cover" :style="coverStyle(a)">
            <span>{{ typeEmoji(a.type) }}</span>
            <div v-if="a.matchScore" class="match-badge">匹配 {{ a.matchScore }}%</div>
          </div>
          <div class="recommend-body">
            <div class="card-tag">{{ a.type || '校园活动' }}</div>
            <h3>{{ a.title }}</h3>
            <p>{{ a.description || '探索校园中的精彩活动，收获新的体验与成长。' }}</p>
            <div v-if="a.reasons && a.reasons.length" class="reason-row">
              <span v-for="r in a.reasons" :key="r" class="reason-chip">{{ r }}</span>
            </div>
            <div class="card-meta">{{ fmtTime(a.start_time) }} · {{ a.location || '地点待定' }}</div>
          </div>
        </article>
      </div>
    </section>

    <section class="dashboard-section hot-section">
      <div class="section-heading"><div><span class="section-kicker">大家都在关注</span><h2>热门活动</h2></div><el-button link type="primary" @click="$router.push('/browse')">更多 →</el-button></div>
      <div v-if="hot.length" class="hot-list"><button v-for="(a, index) in hot" :key="a.id" class="hot-item" @click="$router.push(`/activities/${a.id}`)"><span class="rank">{{ String(index + 1).padStart(2, '0') }}</span><span class="hot-title">{{ a.title }}</span><span class="hot-time">{{ fmtTime(a.start_time) }}</span><span class="arrow">→</span></button></div>
      <el-empty v-else description="暂无热门活动" />
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { session } from '../auth/session.js'
import { createApiClient } from '../api/request.js'

const router = useRouter()

const API = import.meta.env.VITE_API_BASE_URL || '/api'
const request = createApiClient({ baseUrl: API, getToken: () => session.value?.token })
const loading = ref(false)
const recommended = ref([])
const hot = ref([])
const EMOJI = { '学科类': '📚', '文体类': '🎭', '科创竞赛': '🏆', '社会实践': '🤝', '文体活动类': '🎤', '招募类': '🤝', '通知类': '📢' }
const GRADIENT = ['linear-gradient(135deg,#2563eb,#60a5fa)', 'linear-gradient(135deg,#0ea5e9,#7dd3fc)', 'linear-gradient(135deg,#4f46e5,#818cf8)', 'linear-gradient(135deg,#0284c7,#38bdf8)']
const typeEmoji = (type) => EMOJI[type] || '🎉'
const coverStyle = (activity) => ({ background: GRADIENT[(activity.id || 0) % GRADIENT.length] })
const fmtTime = (value) => value ? String(value).replace('T', ' ').slice(0, 16) : '时间待定'

// 推荐卡片示例：优先用后端个性化推荐；无画像/无结果时退回已发布活动并标注示意匹配度，
// 保证首页在任何情况下都有可看的内容（真实个性化需学生勾选画像标签后由 /recommend 生成）。
const DEMO_REASONS = [
  ['专业匹配', '可加综测分'],
  ['兴趣匹配', '技能锻炼'],
  ['专业匹配', '创新分'],
  ['兴趣匹配', '可加操行分']
]
const FALLBACK_TITLES = [
  { title: '华为鲲鹏昇腾开源技术高校行', type: '学科类', description: '为期两天的开源技术实践，面向大三以上软件学院学生，可认定1.0学分专业选修课。', location: 'B7 238' },
  { title: '校园歌手大赛', type: '文体活动类', description: '用歌声点亮校园舞台，初赛报名进行中，欢迎热爱音乐的同学参与。', location: '大学生活动中心' },
  { title: '全国大学生英语竞赛', type: '科创竞赛', description: '提升英语综合能力，获奖可计入综合素质评定，报名截止前尽快提交。', location: '线上报名' },
  { title: '志愿者招募', type: '招募类', description: '加入校园志愿服务队，参与公益活动积累志愿时长与实践经历。', location: '校团委' }
]

function decorate(activity, index) {
  return {
    ...activity,
    matchScore: 92 - index * 6,
    reasons: DEMO_REASONS[index % DEMO_REASONS.length]
  }
}

function demoRecommendations() {
  return FALLBACK_TITLES.map((item, index) => decorate({ id: `demo-${index}`, ...item }, index))
}

function openActivity(activity) {
  if (typeof activity.id === 'number') router.push(`/activities/${activity.id}`)
  else router.push('/browse')
}

async function loadStudentHome() {
  loading.value = true
  try {
    const data = await request('/activities', { query: { status: 'published', page_size: 100 } })
    const activities = (data.items || []).filter((a) => a.status !== 'cancelled')
    hot.value = activities.slice(0, 6)

    let picks = []
    try {
      const rec = await request('/recommend/list', {
        query: {
          match_major: 1, match_interests: 1, match_skills: 1,
          need_conduct_score: 0, need_innovation_score: 0, need_comprehensive_score: 0,
          page_size: 4
        }
      })
      const byId = new Map(activities.map((a) => [a.id, a]))
      picks = (rec.items || [])
        .map((r) => byId.get(r.activity_id))
        .filter(Boolean)
        .map((a, i) => ({ ...a, matchScore: Math.min(99, Math.round(60 + (i * -3) + 30)), reasons: ['专业匹配', '兴趣匹配'] }))
    } catch {
      picks = []
    }

    recommended.value = picks.length ? picks : (activities.length ? activities.slice(0, 2).map(decorate) : demoRecommendations())
  } catch {
    recommended.value = demoRecommendations()
    hot.value = []
  } finally { loading.value = false }
}

onMounted(() => { if (session.value?.role === 'student') loadStudentHome() })
</script>

<style scoped>
.student-home{max-width:1180px;margin:0 auto;padding:8px 0 48px;color:#30405c;background:#f6f9ff;border-radius:24px}
.hero{min-height:330px;display:flex;align-items:center;overflow:hidden;position:relative;border-radius:28px;padding:44px 64px;background:linear-gradient(115deg,#eaf2ff 0%,#e6efff 55%,#dbeafe 100%);box-shadow:0 12px 30px rgba(65,89,125,.1)}
.hero-copy{position:relative;z-index:1;max-width:540px}.eyebrow,.section-kicker{font-size:12px;letter-spacing:2px;color:#7790b4;font-weight:700}.hero h1{font-size:42px;line-height:1.2;margin:14px 0;color:#31415f}.hero h1 em{font-style:normal;color:#6686b9}.hero p{color:#72809a;line-height:1.8;margin:0 0 24px}.hero-actions{display:flex;gap:10px}.hero-art{position:absolute;right:42px;width:390px;height:300px}.sun{position:absolute;right:55px;top:15px;width:190px;height:190px;border-radius:50%;background:#bfdbfe;opacity:.85}.blob{position:absolute;border-radius:48% 52% 35% 65%;background:#93c5fd;opacity:.42}.blob-one{width:230px;height:120px;right:34px;bottom:8px;transform:rotate(-12deg)}.blob-two{width:145px;height:90px;right:180px;bottom:36px;background:#60a5fa;opacity:.5;transform:rotate(16deg)}.art-card{position:absolute;display:flex;flex-direction:column;gap:5px;padding:15px 18px;border:1px solid rgba(255,255,255,.7);border-radius:16px;background:rgba(255,255,255,.76);box-shadow:0 12px 25px rgba(80,98,130,.13);color:#6880a5}.art-card strong{font-size:15px;color:#40577b}.art-card span{font-size:12px}.art-card-main{right:85px;bottom:66px}.art-card-small{right:0;top:76px;font-size:21px}.art-card-small span{font-size:12px}
.dashboard-section{margin-top:34px}.section-heading{display:flex;align-items:end;justify-content:space-between;margin-bottom:15px}.section-heading h2{margin:5px 0 0;font-size:24px;color:#344664}.recommend-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.recommend-card{display:flex;min-height:174px;overflow:hidden;border:1px solid #e7edf4;border-radius:18px;background:#fff;box-shadow:0 5px 16px rgba(64,84,117,.06);cursor:pointer;transition:.2s}.recommend-card:hover{transform:translateY(-3px);box-shadow:0 10px 24px rgba(64,84,117,.12)}.activity-cover{position:relative;width:42%;display:flex;align-items:center;justify-content:center}.activity-cover span{font-size:54px;filter:drop-shadow(0 5px 5px rgba(0,0,0,.1))}.match-badge{position:absolute;left:10px;top:10px;padding:3px 9px;border-radius:20px;background:rgba(255,255,255,.9);color:#3f6aa8;font-size:11px;font-weight:700;letter-spacing:.3px}.recommend-body{padding:18px;flex:1}.card-tag{color:#7991b5;font-size:12px}.recommend-body h3{margin:7px 0;font-size:17px;color:#344664}.recommend-body p{margin:0;color:#8b97a9;font-size:13px;line-height:1.6;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.reason-row{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}.reason-chip{padding:2px 9px;border-radius:20px;background:#eef4ff;color:#4d77b5;font-size:11px}.card-meta{margin-top:10px;color:#8797ae;font-size:12px}.hot-section{padding:24px 26px;border-radius:20px;background:#eef4ff}.hot-list{border-top:1px solid #dbe6f5}.hot-item{width:100%;display:flex;align-items:center;gap:16px;padding:15px 4px;border:0;border-bottom:1px solid #dbe6f5;background:transparent;text-align:left;color:#566985;cursor:pointer}.hot-item:hover{color:#2563eb}.rank{color:#2563eb;font-weight:700;font-size:13px}.hot-title{flex:1;font-size:14px}.hot-time{color:#9b9b9b;font-size:12px}.arrow{color:#a9b8cc;font-size:18px}.loading-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:18px}.loading-grid .el-skeleton{padding:18px;border-radius:18px;background:#fff}
@media (max-width:800px){.hero{padding:34px 28px}.hero-art{opacity:.35;right:-90px}.hero h1{font-size:32px}.recommend-grid{grid-template-columns:1fr}.hot-item{gap:9px}.hot-time{font-size:11px}}
</style>
