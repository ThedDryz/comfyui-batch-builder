const STYLE_ID = "batch-prompt-style";

const CSS = `
.bpr-field {
  display: flex;
  flex-direction: column;
  gap: 2px;
  box-sizing: border-box;
  font: 11px/1.3 var(--comfy-font, sans-serif);
  color: var(--input-text, #ddd);
}
.bpr-head {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 0 0 22px;
  padding: 0 6px;
  border-radius: 6px;
  background: var(--comfy-input-bg, #222);
  cursor: pointer;
  user-select: none;
}
.bpr-head:hover { filter: brightness(1.15); }
.bpr-arrow {
  flex: 0 0 auto;
  font-size: 9px;
  opacity: 0.6;
  transition: transform 0.12s ease;
}
.bpr-field.open .bpr-arrow { transform: rotate(90deg); }
.bpr-label { flex: 0 0 auto; font-weight: 600; white-space: nowrap; }
.bpr-peek {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  opacity: 0.5;
}
.bpr-field.open .bpr-peek { visibility: hidden; }
.bpr-field.off .bpr-label,
.bpr-field.off .bpr-peek { opacity: 0.35; text-decoration: line-through; }
.bpr-body { display: none; flex: 0 0 auto; }
.bpr-field.open .bpr-body { display: block; }
.bpr-text {
  display: block;
  box-sizing: border-box;
  width: 100%;
  min-height: 26px;
  margin: 0;
  padding: 4px 6px;
  resize: vertical;
  border: 1px solid var(--border-color, #444);
  border-radius: 6px;
  outline: none;
  background: var(--comfy-input-bg, #222);
  color: inherit;
  font: 12px/16px var(--comfy-font, sans-serif);
}
.bpr-text:focus { border-color: var(--p-primary-color, #6a9fd8); }
.bpr-field.off .bpr-text { opacity: 0.45; }

.bpr-row { display: flex; gap: 6px; }
.bpr-cell { display: flex; flex: 1 1 0; min-width: 0; align-items: flex-start; gap: 4px; }
.bpr-cell-label { flex: 0 0 auto; padding-top: 5px; font-weight: 600; opacity: 0.7; }
.bpr-row .bpr-text { flex: 1 1 auto; width: auto; min-width: 0; }

.bpr-switch { position: relative; flex: 0 0 24px; height: 13px; cursor: pointer; }
.bpr-switch input { position: absolute; opacity: 0; width: 0; height: 0; }
.bpr-switch span {
  position: absolute;
  inset: 0;
  border-radius: 7px;
  background: var(--border-color, #555);
  transition: background 0.12s ease;
}
.bpr-switch span::after {
  content: "";
  position: absolute;
  top: 2px;
  left: 2px;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--input-text, #ddd);
  transition: transform 0.12s ease;
}
.bpr-switch input:checked + span { background: var(--p-primary-color, #4c8bd6); }
.bpr-switch input:checked + span::after { transform: translateX(11px); }

.bps-history {
  display: flex;
  gap: 3px;
  box-sizing: border-box;
  height: 100%;
  font: 10px/1 var(--comfy-font, sans-serif);
}
.bps-history button {
  flex: 1 1 0;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 0 4px;
  border: 1px solid var(--border-color, #444);
  border-radius: 6px;
  background: var(--comfy-input-bg, #222);
  color: var(--input-text, #ddd);
  cursor: pointer;
}
.bps-history button:hover:not(:disabled) { filter: brightness(1.2); }
.bps-history button:disabled { opacity: 0.35; cursor: default; }
.bps-history button.active { border-color: var(--p-primary-color, #4c8bd6); }
`;

export function injectStyle() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = CSS;
  document.head.append(style);
}

export function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

export function relayout(node) {
  requestAnimationFrame(() => {
    const [width] = node.size;
    const min = node.computeSize([width]);
    node.setSize([Math.max(width, min[0]), min[1]]);
    node.setDirtyCanvas?.(true, true);
  });
}
