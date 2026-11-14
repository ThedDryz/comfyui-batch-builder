import { app } from "../../scripts/app.js";

const NODE_CLASSES = new Set(["BatchPrompt_Builder", "BatchPrompt_SeedList", "BatchPrompt_CharacterDefinition"]);
// Widgets that draw their own text: roll fields, the seed button and history row.
const SELF_LABELED = new Set(["ROLL_TEXT", "button", "seed_history"]);

function pretty(name) {
  const text = String(name).replace(/_/g, " ").trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** Labels only items still showing their raw name, so user renames are kept. */
function setLabel(item) {
  if (!item?.name || (item.label && item.label !== item.name)) return;
  item.label = pretty(item.name);
}

function applyLabels(node) {
  for (const widget of node.widgets ?? []) {
    if (widget.hidden || SELF_LABELED.has(widget.type)) continue;
    setLabel(widget);
  }
  for (const slot of [...(node.inputs ?? []), ...(node.outputs ?? [])]) setLabel(slot);
  node.setDirtyCanvas?.(true, true);
}

app.registerExtension({
  name: "BatchPrompt.Labels",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (!NODE_CLASSES.has(nodeData.name)) return;

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const result = onNodeCreated?.apply(this, arguments);
      applyLabels(this);
      return result;
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      const result = onConfigure?.apply(this, arguments);
      applyLabels(this);
      return result;
    };
  },
});
