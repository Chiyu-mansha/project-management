<script setup>
defineProps({ schema: { type: Array, required: true }, answers: { type: Object, required: true } })
</script>

<template>
  <dl class="answers-view">
    <div v-for="field in schema" :key="field.field_key">
      <dt>{{ field.label }}</dt>
      <dd>{{ answers[field.field_key] === '' || answers[field.field_key] == null ? '—' : answers[field.field_key] }}</dd>
    </div>
  </dl>
</template>
