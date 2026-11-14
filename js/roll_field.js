import { app } from "../../scripts/app.js";
import { el, injectStyle, relayout } from "./ui_style.js";

const TYPE = "ROLL_TEXT";
const MARGIN = 2;
const HEADER = 22;
const GAP = 2;
const LINE = 16;
const TEXT_CHROME = 10; // textarea padding + border
const DEFAULT_TEXT_HEIGHT = 3 * LINE + TEXT_CHROME;
const MIN_TEXT_HEIGHT = LINE + TEXT_CHROME;

function storedState(node, name) {
  return node.properties?.rollFields?.[name];
}

function saveState(node, name, state) {
  node.properties ??= {};
  node.properties.rollFields ??= {};
  node.properties.rollFields[name] = state;
}

function hideWidget(widget) {
  widget.hidden = true;
  widget.computeSize = () => [0, -4];
  widget.draw = () => {};
  widget.mouse = () => false;
}

class RollField {
  constructor(node, name, options) {
    this.node = node;
    this.name = name;
    this.open = false;
    this.textHeight = DEFAULT_TEXT_HEIGHT;
    this.toggleName = options.toggle ?? null;
    this.toggleWidget = null;
    this.title = options.title ?? name;
    this.tooltip = options.tooltip ?? "";
    this.group = options.group ?? null;
    this.groupTitle = options.group_title ?? this.title;
    this.leader = null;
    this.members = [this];
    this.defaultHeight = DEFAULT_TEXT_HEIGHT;

    this.root = el("div", "bpr-field");
    this.head = el("div", "bpr-head");
    this.head.title = this.tooltip;
    const arrow = el("span", "bpr-arrow", "\u25B6");
    this.label = el("span", "bpr-label", this.title);
    this.peek = el("span", "bpr-peek");
    this.head.append(arrow, this.label, this.peek);

    this.text = el("textarea", "bpr-text");
    this.text.placeholder = options.placeholder ?? "";
    this.text.spellcheck = false;
    this.text.value = options.default ?? "";
    this.root.append(this.head, this.text);

    this.head.addEventListener("click", () => this.setOpen(!this.open, true));
    this.text.addEventListener("input", () => {
      (this.leader ?? this).updatePeek();
      this.widget?.callback?.(this.text.value);
    });
    new ResizeObserver(() => (this.leader ?? this).onTextResized(this.text)).observe(this.text);

    this.widget = node.addDOMWidget(name, TYPE, this.root, {
      getValue: () => this.text.value,
      setValue: (value) => {
        this.text.value = value ?? "";
        this.sync();
      },
      getMinHeight: () => this.height(),
      getMaxHeight: () => this.height(),
      margin: MARGIN,
    });
    this.widget.rollField = this;
    this.sync();
  }

  height() {
    if (this.leader) return 0;
    return 2 * MARGIN + HEADER + (this.open ? GAP + this.textHeight : 0);
  }

  /** Re-applies saved roll state, or the default (unrolled only when the field has text). */
  sync() {
    if (this.leader) return this.leader.sync();
    const state = storedState(this.node, this.name);
    if (state) {
      this.textHeight = Math.max(MIN_TEXT_HEIGHT, state.height ?? this.defaultHeight);
      this.apply(!!state.open);
    } else {
      this.apply(this.members.some((m) => m.text.value.trim() !== ""));
    }
    this.syncToggle();
  }

  /** Moves the followers' text boxes into this field's row, under one header. */
  adopt(followers) {
    this.members = [this, ...followers];
    this.label.textContent = this.groupTitle;
    this.defaultHeight = MIN_TEXT_HEIGHT;
    if (!storedState(this.node, this.name)) this.textHeight = MIN_TEXT_HEIGHT;

    const row = el("div", "bpr-row");
    for (const member of this.members) {
      const cell = el("div", "bpr-cell");
      const tag = el("span", "bpr-cell-label", member.title);
      tag.title = member.tooltip;
      cell.append(tag, member.text);
      row.append(cell);
      if (member === this) continue;
      member.leader = this;
      member.root.replaceChildren();
      member.widget.hidden = true;
      member.widget.computeSize = () => [0, -4];
    }
    this.root.append(row);
    this.sync();
  }

  setOpen(open, persist) {
    this.apply(open);
    if (persist) this.persist();
    relayout(this.node);
  }

  apply(open) {
    this.open = open;
    this.root.classList.toggle("open", open);
    for (const member of this.members) member.text.style.height = `${this.textHeight}px`;
    this.updatePeek();
  }

  persist() {
    saveState(this.node, this.name, { open: this.open, height: this.textHeight });
  }

  updatePeek() {
    const lines = this.members.map((m) => m.text.value.split(/\r?\n/).map((l) => l.trim()).filter(Boolean));
    const extra = Math.max(...lines.map((l) => l.length)) - 1;
    let first;
    if (this.members.length > 1) {
      first = lines.every((l) => !l.length) ? "" : lines.map((l) => l[0] ?? "?").join(" x ");
    } else {
      first = lines[0][0] ?? "";
    }
    this.peek.textContent = extra > 0 ? `${first}  (+${extra})` : first;
  }

  onTextResized(textarea) {
    if (!this.open) return;
    const height = textarea.offsetHeight;
    if (!height || Math.abs(height - this.textHeight) < 1) return;
    this.textHeight = Math.max(MIN_TEXT_HEIGHT, height);
    for (const member of this.members) member.text.style.height = `${this.textHeight}px`;
    this.persist();
    relayout(this.node);
  }

  linkToggle() {
    if (!this.toggleName || this.toggleWidget) return;
    const widget = this.node.widgets?.find((w) => w.name === this.toggleName);
    if (!widget) return;
    this.toggleWidget = widget;
    hideWidget(widget);

    const sw = el("label", "bpr-switch");
    sw.title = "Include this part";
    this.checkbox = el("input");
    this.checkbox.type = "checkbox";
    sw.append(this.checkbox, el("span"));
    sw.addEventListener("click", (e) => e.stopPropagation());
    this.checkbox.addEventListener("change", () => {
      widget.value = this.checkbox.checked;
      widget.callback?.(widget.value);
      this.syncToggle();
      this.node.setDirtyCanvas?.(true, true);
    });
    this.head.insertBefore(sw, this.peek);
    this.syncToggle();
  }

  syncToggle() {
    if (!this.toggleWidget) return;
    const on = !!this.toggleWidget.value;
    this.checkbox.checked = on;
    this.root.classList.toggle("off", !on);
  }
}

function rollFields(node) {
  return (node.widgets ?? []).map((w) => w.rollField).filter(Boolean);
}

function linkGroups(node) {
  const groups = new Map();
  for (const field of rollFields(node)) {
    if (!field.group || field.leader) continue;
    if (!groups.has(field.group)) groups.set(field.group, []);
    groups.get(field.group).push(field);
  }
  for (const [leader, ...followers] of groups.values()) {
    if (followers.length && leader.members.length === 1) leader.adopt(followers);
  }
}

function usesRollText(nodeData) {
  const inputs = { ...(nodeData.input?.required ?? {}), ...(nodeData.input?.optional ?? {}) };
  return Object.values(inputs).some((spec) => Array.isArray(spec) && spec[0] === TYPE);
}

app.registerExtension({
  name: "BatchPrompt.RollField",

  init() {
    injectStyle();
  },

  getCustomWidgets() {
    return {
      [TYPE](node, inputName, inputData) {
        const field = new RollField(node, inputName, inputData?.[1] ?? {});
        return { widget: field.widget, minWidth: 220 };
      },
    };
  },

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (!usesRollText(nodeData)) return;

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const result = onNodeCreated?.apply(this, arguments);
      for (const field of rollFields(this)) field.linkToggle();
      linkGroups(this);
      relayout(this);
      return result;
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      const result = onConfigure?.apply(this, arguments);
      linkGroups(this);
      for (const field of rollFields(this)) {
        field.linkToggle();
        field.sync();
      }
      relayout(this);
      return result;
    };
  },
});
