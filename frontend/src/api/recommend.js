export function createRecommendApi(request) {
  return {
    score: (signal) => request('/recommend/score', { method: 'POST', signal }),
    list: (query, signal) => request('/recommend/list', { query, signal })
  }
}
