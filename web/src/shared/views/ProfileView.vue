<script setup lang="ts">
import { useRoleConfig } from '@/shared/app/roleConfig'

const config = useRoleConfig()
</script>

<template>
  <section class="space-y-6">
    <div>
      <h1 class="font-serif text-3xl font-semibold text-ink">{{ config.roleLabel }} profile</h1>
      <p class="mt-2 max-w-2xl text-base text-ink-soft">
        Account, session, and notification preferences are grouped here.
      </p>
    </div>

    <div class="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
      <section class="mp-surface p-5">
        <h2 class="font-serif text-xl font-semibold">Account</h2>
        <dl class="mt-5 grid gap-4 sm:grid-cols-2">
          <div>
            <dt class="text-xs font-extrabold uppercase tracking-[0.13em] text-ink-muted">Role</dt>
            <dd class="mt-1 text-base font-bold text-ink">{{ config.roleLabel }}</dd>
          </div>
          <div>
            <dt class="text-xs font-extrabold uppercase tracking-[0.13em] text-ink-muted">Scope</dt>
            <dd class="mt-1 text-base font-bold text-ink">{{ config.tenantLabel }}</dd>
          </div>
          <div>
            <dt class="text-xs font-extrabold uppercase tracking-[0.13em] text-ink-muted">
              Status
            </dt>
            <dd class="mt-1">
              <span class="mp-chip bg-success-soft text-success">
                <span class="mp-dot" aria-hidden="true"></span>
                Ready
              </span>
            </dd>
          </div>
          <div>
            <dt class="text-xs font-extrabold uppercase tracking-[0.13em] text-ink-muted">
              Session
            </dt>
            <dd class="mt-1 font-mono text-sm text-ink-soft">active</dd>
          </div>
        </dl>
      </section>

      <aside class="mp-surface p-5">
        <h2 class="font-serif text-xl font-semibold">Access states</h2>
        <ul class="mt-4 space-y-3 text-sm text-ink-soft">
          <li v-for="state in config.states" :key="state.kind" class="flex gap-2">
            <span class="mp-dot mt-2 text-accent" aria-hidden="true"></span>
            <span>
              <span class="block font-bold text-ink">{{ state.label }}</span>
              {{ state.detail }}
            </span>
          </li>
        </ul>
      </aside>
    </div>
  </section>
</template>
