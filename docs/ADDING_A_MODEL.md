# Adding a model adapter

An adapter must implement sample loading, checkpoint loading, deterministic baseline prediction, native graph extraction, identity intervention, structural edge intervention, metadata, and cleanup. Add the adapter specification to the official registry and provide a Config v2 template.

New adapters must pass V01–V09, produce a native Session v2 Quick Inspection, preserve exact graph tensors through the session round trip, enumerate unique eligible controls without replacement, and explicitly leave single-case formal inference unavailable. Formal support additionally requires a frozen candidate family, declared audit units, a dependence protocol, and a registered candidate-level inference engine.

Add regression coverage for graph hashes, baseline predictions, intervention availability, Config v2 validation, Session v2 validation, and browser import.
