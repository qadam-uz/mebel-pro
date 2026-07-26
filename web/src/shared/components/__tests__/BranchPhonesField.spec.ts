import { mount } from '@vue/test-utils'
import { defineComponent, h, ref, type PropType } from 'vue'
import { describe, expect, it } from 'vitest'

import BranchPhonesField from '@/shared/components/BranchPhonesField.vue'

// A host that owns the model the way the branch forms do — the add/remove
// contract only holds when the emitted list is written back through v-model.
const Host = defineComponent({
  props: {
    initial: { type: Array as PropType<string[]>, required: true },
    errors: { type: Array as PropType<Array<string | undefined>>, default: undefined },
  },
  setup(props) {
    const model = ref<string[]>([...props.initial])
    return () =>
      h(BranchPhonesField, {
        modelValue: model.value,
        idPrefix: 'branch-extra',
        errors: props.errors,
        'onUpdate:modelValue': (value: string[]) => {
          model.value = value
        },
      })
  },
})

function mountField(initial: string[], errors?: Array<string | undefined>) {
  return mount(Host, { props: { initial, errors }, attachTo: document.body })
}

type Wrapper = ReturnType<typeof mountField>

function addButton(wrapper: Wrapper) {
  return wrapper.findAll('button').filter((button) => button.text().includes('Telefon'))[0]
}

function removeButtons(wrapper: Wrapper) {
  return wrapper.findAll('button[aria-label]')
}

function rows(wrapper: Wrapper) {
  return wrapper.findAll<HTMLInputElement>('input[type="tel"]').map((input) => input.element.value)
}

describe('BranchPhonesField', () => {
  it('appends an empty row and focuses it so typing can start straight away', async () => {
    const wrapper = mountField(['+998902222222'])
    await addButton(wrapper).trigger('click')
    await wrapper.vm.$nextTick()

    expect(rows(wrapper)).toEqual(['90 222 22 22', ''])
    expect(document.activeElement?.id).toBe('branch-extra-1')
    wrapper.unmount()
  })

  it('removes exactly the row whose button was pressed', async () => {
    const wrapper = mountField(['+998902222222', '+998903333333', '+998904444444'])
    await removeButtons(wrapper)[1].trigger('click')

    expect(rows(wrapper)).toEqual(['90 222 22 22', '90 444 44 44'])
    wrapper.unmount()
  })

  it('disables the add button at the three-number cap and says why', () => {
    const wrapper = mountField(['+998902222222', '+998903333333', '+998904444444'])

    expect(addButton(wrapper).attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain("Eng ko'pi 3 ta qo'shimcha raqam")
    wrapper.unmount()
  })

  it('re-enables the add button once a row is removed at the cap', async () => {
    const wrapper = mountField(['+998902222222', '+998903333333', '+998904444444'])
    await removeButtons(wrapper)[0].trigger('click')

    expect(addButton(wrapper).attributes('disabled')).toBeUndefined()
    wrapper.unmount()
  })

  it('renders a per-row error and points the row input at it', () => {
    const wrapper = mountField(['+998902222222', ''], [undefined, 'Xato raqam.'])
    const input = wrapper.get('#branch-extra-1')

    expect(wrapper.get('#branch-extra-1-error').text()).toBe('Xato raqam.')
    expect(input.attributes('aria-describedby')).toBe('branch-extra-1-error')
    expect(input.attributes('aria-invalid')).toBe('true')
    // The clean row stays unmarked.
    expect(wrapper.get('#branch-extra-0').attributes('aria-invalid')).toBe('false')
    wrapper.unmount()
  })

  it('names each remove button for screen readers', () => {
    const wrapper = mountField(['+998902222222', '+998903333333'])

    expect(removeButtons(wrapper).map((button) => button.attributes('aria-label'))).toEqual([
      "2-telefonni o'chirish",
      "3-telefonni o'chirish",
    ])
    wrapper.unmount()
  })
})
