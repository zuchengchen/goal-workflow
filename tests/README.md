# Behavioral Eval Contract

`evals.json` is a declarative behavior contract for a future manual or agent-driven harness. Each case fixes the initial state, decisive checkpoint replies, required behaviors, forbidden actions, and observable action ordering for a high-risk workflow branch.

`checkpoint_replies` is not a complete transcript. A harness must answer routine discovery questions from the declared setup or record additional explicit fixture input, but it must never invent a design, save, overwrite, or start approval. An ordering constraint applies when both named actions occur; a terminal state may intentionally stop before the later action.

The repository validator and CI currently check the JSON schema, required scenario coverage, action names, and declared ordering constraints. They do not run a model, inspect a live conversation trace, or claim that model behavior passed these cases. To evaluate behavior, a human reviewer or agent harness must run each prompt, capture every additional user turn plus the interaction and tool trace, and compare that evidence with the corresponding `expected` object.
