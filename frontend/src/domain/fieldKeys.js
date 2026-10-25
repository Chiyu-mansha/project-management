// User-confirmed rule: lowercase, tone-free pinyin separated by underscores.
export async function generateFieldKey(label) {
  if (typeof label !== 'string' || !label.trim()) throw new Error('题干不能为空')
  // Load the dictionary only when an organizer saves a new question.
  const { pinyin } = await import('pinyin-pro')
  const key = pinyin(label.trim(), { toneType: 'none', type: 'array', nonZh: 'consecutive' })
    .join('_').toLowerCase().replace(/ü/g, 'v')
    .replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '')
  if (!key) throw new Error('题干请至少包含一个汉字、英文字母或数字')
  return /^[a-z]/.test(key) ? key : `field_${key}`
}
