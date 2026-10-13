<script setup>
defineProps({
  schema: { type: Array, required: true },
  modelValue: { type: Object, required: true },
  disabled: Boolean,
  prefix: { type: String, default: 'field' }
})
const emit = defineEmits(['update:modelValue'])
</script>

<template>
  <div v-for="field in schema" :key="field.field_key" class="answer-field">
    <label :for="`${prefix}-${field.field_key}`">
      <span v-if="field.required" class="required-mark" aria-hidden="true">*</span>{{ field.label }}
    </label>
    <el-input
      :id="`${prefix}-${field.field_key}`"
      :model-value="modelValue[field.field_key]"
      :type="field.type === 'textarea' ? 'textarea' : 'text'"
      :rows="field.type === 'textarea' ? 3 : undefined"
      :disabled="disabled"
      :aria-required="field.required"
      @update:model-value="emit('update:modelValue', { ...modelValue, [field.field_key]: $event })"
    />
  </div>
</template>
