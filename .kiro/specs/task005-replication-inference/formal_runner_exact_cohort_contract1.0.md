# TASK_005 Formal Runner Exact Cohort Contract 1.0

Formal replication uses a fixed predeclared cohort of exactly 24 block
identities: `R001` through `R024`. Replacement blocks are not permitted.
`R025` and later identities must be rejected for formal use.

Failed, invalid, or interrupted blocks do not count as valid formal blocks.
Recovery may retry only the same replicate identity with the same deterministic
seed identities. Automatic retry loops are not part of this contract; retry
requires explicit resume invocation.

The formal wrapper is the only formal launch entry point. It fixes
`num_replicates = 24`, requires serial execution, rejects engineering
namespaces, and preserves `formal_llm_launch_permitted = false` for this stage.
The final real formal master seed is deferred to a later launch contract.
