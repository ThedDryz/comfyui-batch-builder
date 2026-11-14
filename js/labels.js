import { app } from "../../scripts/app.js";

const NODE_CLASSES = new Set(["BatchPrompt_Builder", "BatchPrompt_SeedList", "BatchPrompt_CharacterDefinition"]);
// Widgets that draw their own text: roll fields, the seed button and history row.
const SELF_LABELED = new Set(["ROLL_TEXT", "button", "seed_history"]);

function pretty(name) {
  const text = String(name).replace(/_/g, " ").trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/**
 * Labels items showing their raw name or a label this script made for another item
 * (left behind when a saved slot moved); any other label is a user rename and is kept.
 */
function setLabel(item, generated) {
  if (!item?.name) return;
  if (item.label && item.label !== item.name && !generated.has(item.label)) return;
  item.label = pretty(item.name);
}

function applyLabels(node) {
  const widgets = (node.widgets ?? []).filter((w) => !w.hidden && !SELF_LABELED.has(w.type));
  const slots = [...(node.inputs ?? []), ...(node.outputs ?? [])];
  const generated = new Set([...widgets, ...slots].filter((i) => i?.name).map((i) => pretty(i.name)));
  for (const item of [...widgets, ...slots]) setLabel(item, generated);
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
