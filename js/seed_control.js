import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { el, injectStyle, relayout } from "./ui_style.js";

const NODE_CLASS = "BatchPrompt_SeedList";
const RANDOMIZE = -1;
const RANDOM_MAX = 1125899906842624;
const HISTORY_SIZE = 4;
const BEHAVIORS = { randomize: "Randomize", increment: "Increment", decrement: "Decrement" };
const CONTROL_WIDGETS = new Set(["control_after_generate", "control_before_generate"]);

function removeWidget(node, widget) {
  if (node.removeWidget) node.removeWidget(widget);
  else node.widgets.splice(node.widgets.indexOf(widget), 1);
}

class SeedControl {
  constructor(node) {
    this.node = node;
    this.seedWidget = node.widgets?.find((w) => w.name === "seed");
    if (!this.seedWidget) return;
    this.resolvedRandom = false;

    this.removeControlWidgets();

    this.button = node.addWidget("button", "seed_button", null, () => this.toggle(), { serialize: false });
    this.button.serialize = false;

    this.historyButtons = [];
    const row = el("div", "bps-history");
    for (let i = 0; i < HISTORY_SIZE; i++) {
      const button = el("button");
      button.addEventListener("click", () => this.pin(i));
      this.historyButtons.push(button);
      row.append(button);
    }
    this.historyWidget = node.addDOMWidget("seed_history", "seed_history", row, {
      serialize: false,
      getMinHeight: () => 26,
      getMaxHeight: () => 26,
      margin: 2,
    });
    this.historyWidget.serialize = false;

    const seedWidget = this.seedWidget;
    seedWidget.beforeQueued = () => this.resolve();
    seedWidget.afterQueued = () => this.afterQueued();
    const callback = seedWidget.callback;
    seedWidget.callback = (...args) => {
      const result = callback?.apply(seedWidget, args);
      this.refresh();
      return result;
    };

    this.refresh();
  }

  removeControlWidgets() {
    const removed = (this.node.widgets ?? []).filter((w) => CONTROL_WIDGETS.has(w.name));
    for (const widget of removed) removeWidget(this.node, widget);
    if (removed.length && Array.isArray(this.seedWidget.linkedWidgets)) {
      this.seedWidget.linkedWidgets = this.seedWidget.linkedWidgets.filter((w) => !removed.includes(w));
    }
  }

  get history() {
    const history = this.node.properties?.seedHistory;
    return Array.isArray(history) ? history.filter(Number.isInteger).slice(0, HISTORY_SIZE) : [];
  }

  get behavior() {
    return BEHAVIORS[this.node.properties?.seedBehavior] ? this.node.properties.seedBehavior : "randomize";
  }

  get maxSeed() {
    return Math.min(RANDOM_MAX, this.seedWidget.options?.max ?? RANDOM_MAX);
  }

  setProperty(name, value) {
    this.node.properties ??= {};
    this.node.properties[name] = value;
  }

  remember(seed, { onlyIfNew = false } = {}) {
    const history = this.history;
    if (onlyIfNew && history.includes(seed)) return;
    this.setProperty("seedHistory", [seed, ...history.filter((s) => s !== seed)].slice(0, HISTORY_SIZE));
    this.refresh();
  }

  /** Runs before the prompt is built, so the workflow and the prompt both carry the real seed. */
  resolve() {
    this.resolvedRandom = false;
    if (this.seedWidget.value !== RANDOMIZE) return;
    const last = this.history[0];
    let seed;
    if (this.behavior === "increment" && last != null) seed = last + 1;
    else if (this.behavior === "decrement" && last != null) seed = last - 1;
    else seed = Math.floor(Math.random() * (this.maxSeed + 1));
    this.seedWidget.value = Math.min(Math.max(seed, 0), this.maxSeed);
    this.resolvedRandom = true;
  }

  afterQueued() {
    const used = this.seedWidget.value;
    if (Number.isInteger(used) && used >= 0) this.remember(used);
    if (this.resolvedRandom) this.seedWidget.value = RANDOMIZE;
    this.resolvedRandom = false;
    this.refresh();
  }

  toggle() {
    if (this.seedWidget.value !== RANDOMIZE) this.seedWidget.value = RANDOMIZE;
    else if (this.history.length) this.seedWidget.value = this.history[0];
    this.refresh();
  }

  pin(index) {
    const seed = this.history[index];
    if (seed == null) return;
    this.seedWidget.value = seed;
    this.refresh();
  }

  setBehavior(behavior) {
    this.setProperty("seedBehavior", behavior);
    this.seedWidget.value = RANDOMIZE;
    this.refresh();
  }

  refresh() {
    if (!this.button) return;
    this.button.label = `${BEHAVIORS[this.behavior]} / Last Queued Seed`;
    const history = this.history;
    const current = this.seedWidget.value;
    this.historyButtons.forEach((button, i) => {
      const seed = history[i];
      button.disabled = seed == null;
      button.textContent = seed == null ? "\u2013" : String(seed);
      button.title = seed == null ? "No queued seed yet" : `Use seed ${seed}`;
      button.classList.toggle("active", seed != null && seed === current);
    });
    this.node.setDirtyCanvas?.(true, true);
  }
}

function findNode(executionId) {
  let graph = app.graph;
  let node = null;
  for (const id of String(executionId).split(":")) {
    node = graph?.getNodeById(Number(id)) ?? graph?.getNodeById(id);
    if (!node) return null;
    graph = node.subgraph;
  }
  return node?.comfyClass === NODE_CLASS ? node : null;
}

app.registerExtension({
  name: "BatchPrompt.SeedControl",

  init() {
    injectStyle();
  },

  setup() {
    // Records seeds the backend picked itself (seed -1 reached Python, e.g. no beforeQueued).
    api.addEventListener("executed", ({ detail }) => {
      const seed = detail?.output?.bp_master_seed?.[0];
      if (!Number.isInteger(seed)) return;
      findNode(detail.display_node ?? detail.node)?.seedControl?.remember(seed, { onlyIfNew: true });
    });
  },

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== NODE_CLASS) return;

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const result = onNodeCreated?.apply(this, arguments);
      this.seedControl = new SeedControl(this);
      relayout(this);
      return result;
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      const result = onConfigure?.apply(this, arguments);
      this.seedControl?.removeControlWidgets();
      this.seedControl?.refresh();
      relayout(this);
      return result;
    };

    const getExtraMenuOptions = nodeType.prototype.getExtraMenuOptions;
    nodeType.prototype.getExtraMenuOptions = function (canvas, options) {
      const result = getExtraMenuOptions?.apply(this, arguments);
      const control = this.seedControl;
      if (control?.button) {
        options.push(
          null,
          ...Object.entries(BEHAVIORS).map(([key, label]) => ({
            content: `Seed behavior: ${label}${control.behavior === key ? " (current)" : ""}`,
            callback: () => control.setBehavior(key),
          })),
        );
      }
      return result;
    };
  },
});
