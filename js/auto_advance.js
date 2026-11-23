import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_CLASS = "BatchPrompt_Builder";

// prompt_id -> [{ executionId, nextIndex }], filled while a prompt runs and
// applied only once that prompt finishes successfully.
const pending = new Map();

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

function onExecuted({ detail }) {
  const output = detail?.output;
  if (!output?.bp_advance?.[0]) return;
  const executionId = detail.display_node ?? detail.node;
  if (!findNode(executionId)) return;
  const list = pending.get(detail.prompt_id) ?? [];
  list.push({ executionId, nextIndex: output.bp_next_index[0] });
  pending.set(detail.prompt_id, list);
}

function onSuccess({ detail }) {
  const list = pending.get(detail?.prompt_id);
  if (!list) return;
  pending.delete(detail.prompt_id);

  let advanced = false;
  for (const { executionId, nextIndex } of list) {
    const widget = findNode(executionId)?.widgets?.find((w) => w.name === "start_index");
    if (!widget) continue;
    widget.value = nextIndex;
    advanced = true;
  }
  if (!advanced) return;
  app.graph.setDirtyCanvas(true, true);
  app.queuePrompt(0, 1);
}

// Current layout: start_index, end_index, batch, prompt_order, vary_wildcards, auto_advance, prepend, ...
const ORDER_SLOT = 3;
const PROMPT_ORDERS = new Set(["tag first", "language first"]);
const DEFAULT_ORDER = "language first";
// Layout before prompt_order existed, where vary_wildcards sat right after batch.
const VARY_SLOT = 3;

/**
 * Widget values are positional, so graphs saved with an older widget layout are
 * shifted into the current one: first vary_wildcards (absent, or saved last),
 * then prompt_order (absent before the dropdown was added).
 */
function migrateWidgetValues(info) {
  const values = info?.widgets_values;
  if (!Array.isArray(values) || values.length <= VARY_SLOT + 1) return;
  if (PROMPT_ORDERS.has(values[ORDER_SLOT])) return;
  if (typeof values[VARY_SLOT + 1] !== "boolean") {
    const vary = values.length > 11 && typeof values.at(-1) === "boolean" ? values.pop() : false;
    values.splice(VARY_SLOT, 0, vary);
  }
  values.splice(ORDER_SLOT, 0, DEFAULT_ORDER);
}

function getLink(graph, id) {
  const links = graph?.links;
  return links?.get?.(id) ?? links?.[id];
}

/**
 * Output slots are saved by position, so a graph saved before an output was added or
 * moved puts old names, labels and links on the wrong slots. Rebuild them in the
 * node definition's order, matching saved slots by name and moving their links along.
 */
function migrateOutputs(node, info, nodeData) {
  const saved = info?.outputs;
  const names = nodeData.output_name ?? nodeData.output;
  const types = nodeData.output;
  if (!Array.isArray(saved) || !Array.isArray(names)) return;
  if (saved.length === names.length && saved.every((s, i) => s?.name === names[i] && s?.type === types[i])) return;

  const generated = new Set(names.map((n) => String(n).replace(/_/g, " ").toLowerCase()));
  const unused = new Set(saved.filter(Boolean));
  info.outputs = names.map((name, index) => {
    const candidates = [...unused].filter((s) => s.name === name);
    const pick =
      candidates.find((s) => s.links?.length && s.type === types[index]) ??
      candidates.find((s) => s.links?.length) ??
      candidates.find((s) => s.type === types[index]) ??
      candidates[0];
    if (!pick) return { name, type: types[index], links: null };
    unused.delete(pick);
    for (const id of pick.links ?? []) {
      const link = getLink(node.graph, id);
      if (!link) continue;
      link.origin_slot = index;
      link.type = types[index];
    }
    const { label, ...slot } = pick;
    const keep = label && !generated.has(String(label).toLowerCase());
    return { ...slot, ...(keep ? { label } : {}), name, type: types[index] };
  });
}

function onStopped({ detail }) {
  if (detail?.prompt_id) pending.delete(detail.prompt_id);
  else pending.clear();
}

app.registerExtension({
  name: "BatchPrompt.AutoAdvance",
  setup() {
    api.addEventListener("executed", onExecuted);
    api.addEventListener("execution_success", onSuccess);
    api.addEventListener("execution_error", onStopped);
    api.addEventListener("execution_interrupted", onStopped);
  },

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== NODE_CLASS) return;
    const configure = nodeType.prototype.configure;
    nodeType.prototype.configure = function (info) {
      migrateWidgetValues(info);
      migrateOutputs(this, info, nodeData);
      return configure.apply(this, arguments);
    };
  },
});
