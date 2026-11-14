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
});
