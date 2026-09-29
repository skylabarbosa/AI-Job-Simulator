from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Difficulty = Literal["easy", "medium", "hard"]
BlueprintStatus = Literal["draft", "approved", "rejected"]
# Canonical persisted values. `data_cleaning` is shared by blueprint, runtime,
# evaluator, and workspace presentation.
TaskKind = Literal["analysis", "sql", "data_cleaning", "communication", "other"]
EvaluationType = Literal["deterministic", "qualitative"]


class BlueprintConcept(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=1000)


class BlueprintCompetency(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=1000)
    concepts: list[BlueprintConcept] = Field(min_length=1, max_length=4)


class BlueprintModule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=1000)
    rationale: str = Field(min_length=1, max_length=1000)
    competencies: list[BlueprintCompetency] = Field(min_length=1, max_length=4)


class EvaluationCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=1000)
    what_should_be_checked: str = Field(min_length=1, max_length=1000)
    evaluation_type: EvaluationType = "qualitative"


class BlueprintTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_key: UUID = Field(default_factory=uuid4, description="Stable task identity")
    title: str = Field(min_length=1, max_length=200)
    workplace_context: str = Field(min_length=1, max_length=1200)
    instruction: str = Field(min_length=1, max_length=1600)
    expected_outcome: str = Field(min_length=1, max_length=1200)
    difficulty: Difficulty
    task_kind: TaskKind = "analysis"
    related_module: str = Field(min_length=1, max_length=160)
    related_competencies: list[str] = Field(min_length=1, max_length=8)
    related_concepts: list[str] = Field(default_factory=list, max_length=12)
    dataset_fields: list[str] = Field(default_factory=list, max_length=20)
    sql_tables: list[str] = Field(default_factory=list, max_length=8)
    sql_concepts: list[str] = Field(default_factory=list, max_length=12)
    evaluation_criteria: list[EvaluationCriterion] = Field(min_length=1, max_length=6)


class ProjectBlueprint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_summary: str = Field(min_length=1, max_length=1600)
    workplace_goal: str = Field(min_length=1, max_length=1200)
    modules: list[BlueprintModule] = Field(min_length=1, max_length=4)
    tasks: list[BlueprintTask] = Field(min_length=1, max_length=7)

    @field_validator("modules")
    @classmethod
    def unique_module_names(cls, modules: list[BlueprintModule]) -> list[BlueprintModule]:
        names = [module.name.casefold() for module in modules]
        if len(names) != len(set(names)):
            raise ValueError("Module names must be unique")
        return modules

    @model_validator(mode="after")
    def validate_references(self) -> "ProjectBlueprint":
        module_names = {module.name.casefold() for module in self.modules}
        hierarchy: dict[str, dict[str, set[str]]] = {}
        for module in self.modules:
            competencies: dict[str, set[str]] = {}
            for competency in module.competencies:
                competency_name = competency.name.casefold()
                if competency_name in competencies:
                    raise ValueError(f"Competency names must be unique within module: {competency.name}")
                concepts = {concept.name.casefold() for concept in competency.concepts}
                if len(concepts) != len(competency.concepts):
                    raise ValueError(f"Concept names must be unique within competency: {competency.name}")
                competencies[competency_name] = concepts
            hierarchy[module.name.casefold()] = competencies
        for task in self.tasks:
            module_name = task.related_module.casefold()
            if module_name not in module_names:
                raise ValueError(f"Task references unknown module: {task.related_module}")
            module_competencies = hierarchy[module_name]
            if any(name.casefold() not in module_competencies for name in task.related_competencies):
                raise ValueError(f"Task references a competency outside its module: {task.title}")
            referenced_competencies = {name.casefold() for name in task.related_competencies}
            referenced_concepts = {
                concept
                for competency, concepts in module_competencies.items()
                if competency in referenced_competencies
                for concept in concepts
            }
            if any(name.casefold() not in referenced_concepts for name in task.related_concepts):
                raise ValueError(f"Task references a concept outside its competency hierarchy: {task.title}")
            if task.task_kind != "sql" and task.sql_tables:
                raise ValueError(f"Only SQL tasks may declare SQL tables: {task.title}")
            if task.task_kind != "sql" and task.sql_concepts:
                raise ValueError(f"Only SQL tasks may declare SQL concepts: {task.title}")
        return self


class BlueprintRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    project_id: UUID
    version: int
    status: BlueprintStatus
    source_dataset_ids: list[UUID]
    blueprint_json: ProjectBlueprint
    provider: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    generated_by: UUID | None = None
    approved_by: UUID | None = None
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None = None


class BlueprintWorkAreaView(BaseModel):
    name: str
    description: str
    how_it_will_be_done: str
    resources_used: list[str] = Field(default_factory=list)
    expected_outcome: str


class BlueprintAssignmentView(BaseModel):
    task_key: UUID
    title: str
    workplace_context: str
    expected_output: str
    difficulty: Difficulty
    related_work_area: str


class BlueprintOverview(BaseModel):
    project_id: UUID
    blueprint_id: UUID
    version: int
    status: Literal["approved"]
    project_name: str
    project_summary: str
    business_objective: str
    work_areas: list[BlueprintWorkAreaView]
    assignments: list[BlueprintAssignmentView]
    overall_expected_outcome: str


class BlueprintApproval(BaseModel):
    blueprint_id: UUID


class BlueprintReviseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blueprint_json: ProjectBlueprint | None = None


class BlueprintUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blueprint_json: ProjectBlueprint
