# Offline local audit workflow

Keep upstream model source, checkpoint, and dataset files outside the DGraInsight repository. Edit a Config v2 template with those local paths, then run `validate`, `edges` or `wizard`, and `validate-session`.

On Windows, `Start-DGraInsight-Audit.cmd` starts the guided current workflow. The default output is `dgrainsight_session_v2.json`. The browser import panel accepts that Session v2 file and does not upload it or rerun the model.

Formal examples use repository-owned frozen operands. Quick Inspection uses the user's local assets and always reports formal inference as unavailable for a single inspected case.
