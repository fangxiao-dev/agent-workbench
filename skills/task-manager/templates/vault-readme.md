# TaskManager

This vault stores cross-project task notes, source references, Bases, and dashboards.

Tracked project metadata lives in `00_Config/projects.yml`. Machine-local repository roots live in `00_Config/projects.local.yml`, which is intentionally ignored.

Task notes under `10_Tasks/<project-id>/` use the project folder as the source of truth. Each project task should keep `项目ID` and the single value in `项目` aligned with that folder.

