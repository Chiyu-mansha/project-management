<script setup>
import { isFixedMemberField, newQuestion } from '../model.js'

const props = defineProps({
  modelValue: { type: Array, required: true },
  member: Boolean,
  readonly: Boolean,
  disabled: Boolean
})
const emit = defineEmits(['update:modelValue'])
const locked = (field) => props.member && isFixedMemberField(field)
function update(index, key, value) {
  if (props.disabled || props.readonly || locked(props.modelValue[index])) return
  emit('update:modelValue', props.modelValue.map((field, i) => i === index ? { ...field, [key]: value } : field))
}
function remove(index) {
  if (props.disabled || props.readonly || locked(props.modelValue[index])) return
  emit('update:modelValue', props.modelValue.filter((_, i) => i !== index))
}
</script>

<template>
  <section class="form-section">
    <div class="section-heading">
      <h3>{{ member ? '队员表单（每位队员单独填写）' : '队伍表单（全队填写一次）' }}</h3>
      <el-button
        v-if="!readonly" :disabled="disabled" type="primary" plain
        @click="emit('update:modelValue', [...modelValue, newQuestion()])"
      >{{ member ? '＋ 添加队员题目' : '＋ 添加题目' }}</el-button>
    </div>
    <p v-if="!modelValue.length" class="muted">暂无题目</p>
    <div v-for="(field, index) in modelValue" :key="field._uiId" class="question-row" :class="{ 'fixed-question': locked(field) && !readonly }">
      <template v-if="readonly">
        <strong>{{ field.label }}</strong>
        <span class="muted">{{ field.type === 'textarea' ? '多行文本' : '单行文本' }} · {{ field.required ? '必填' : '选填' }}</span>
      </template>
      <template v-else>
        <div class="question-controls">
          <label class="grow">
            <span>题干</span>
            <el-input :model-value="field.label" :disabled="disabled || locked(field)" :aria-label="`${member ? '队员' : '队伍'}题目 ${index + 1} 题干`" @update:model-value="update(index, 'label', $event)" />
          </label>
          <label>
            <span>类型</span>
            <el-select :model-value="field.type" :disabled="disabled || locked(field)" :aria-label="`${member ? '队员' : '队伍'}题目 ${index + 1} 类型`" @update:model-value="update(index, 'type', $event)">
              <el-option label="单行文本" value="text" />
              <el-option label="多行文本" value="textarea" />
            </el-select>
          </label>
          <el-checkbox :model-value="field.required" :disabled="disabled || locked(field)" @update:model-value="update(index, 'required', $event)">必填</el-checkbox>
          <el-button v-if="!locked(field)" :disabled="disabled" aria-label="删除题目" @click="remove(index)">×</el-button>
        </div>
      </template>
    </div>
  </section>
</template>
