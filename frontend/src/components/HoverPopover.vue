<template>
  <Teleport to="body">
    <div
      v-if="visible"
      ref="popover"
      class="popover hover-popover"
      role="tooltip"
      :style="{ top: top + 'px', left: left + 'px' }"
    >
      <h3 v-if="$slots.title" class="popover-header"><slot name="title" /></h3>
      <div class="popover-body"><slot /></div>
    </div>
  </Teleport>
</template>

<script>
import { defineComponent } from "vue";

// Minimal replacement for bootstrap-vue's <b-popover> (no Vue 3 support):
// shows on hover/focus of the element with id `target`, positioned above it
// (below if there is no room), styled with Bootstrap 4's .popover classes.
const GAP = 8;

export default defineComponent({
  name: "HoverPopover",
  props: {
    target: { type: String, required: true },
    placement: { type: String, default: "auto" },
  },
  emits: ["show"],
  data() {
    return { visible: false, top: 0, left: 0 };
  },
  mounted() {
    document.addEventListener("mouseover", this.onEnter);
    document.addEventListener("focusin", this.onEnter);
    document.addEventListener("mouseout", this.onLeave);
    document.addEventListener("focusout", this.onLeave);
    window.addEventListener("scroll", this.onScroll, true);
  },
  beforeUnmount() {
    document.removeEventListener("mouseover", this.onEnter);
    document.removeEventListener("focusin", this.onEnter);
    document.removeEventListener("mouseout", this.onLeave);
    document.removeEventListener("focusout", this.onLeave);
    window.removeEventListener("scroll", this.onScroll, true);
  },
  methods: {
    targetEl() {
      return document.getElementById(this.target);
    },
    isInTarget(node) {
      const el = this.targetEl();
      return !!(el && node && el.contains(node));
    },
    onEnter(e) {
      if (this.visible || !this.isInTarget(e.target)) return;
      this.visible = true;
      this.$emit("show");
      this.$nextTick(this.position);
    },
    onLeave(e) {
      if (!this.visible || !this.isInTarget(e.target)) return;
      if (this.isInTarget(e.relatedTarget)) return;
      this.hide();
    },
    hide() {
      this.visible = false;
    },
    onScroll() {
      if (this.visible) this.position();
    },
    position() {
      const el = this.targetEl();
      const pop = this.$refs.popover;
      if (!el || !pop) return;
      const t = el.getBoundingClientRect();
      const p = pop.getBoundingClientRect();
      const fitsAbove = t.top - p.height - GAP >= 0;
      const above = this.placement === "bottom" ? false : fitsAbove || this.placement === "top";
      const top = above ? t.top - p.height - GAP : t.bottom + GAP;
      const maxLeft = window.innerWidth - p.width - GAP;
      const left = Math.max(GAP, Math.min(t.left + t.width / 2 - p.width / 2, maxLeft));
      this.top = top;
      this.left = left;
    },
  },
});
</script>

<style>
.hover-popover {
  position: fixed;
  z-index: 1070;
  max-width: 276px;
  pointer-events: none;
}
</style>
