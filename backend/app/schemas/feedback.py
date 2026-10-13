"""Validated feedback inputs; identity and initial status are server-owned."""
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator


PositiveId = Annotated[int, Field(strict=True, gt=0)]
FactText = Annotated[str, Field(min_length=1, max_length=10000)]


class FeedbackInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, strict=True)


class FeedbackCreate(FeedbackInput):
    submission_id: str = Field(pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$', description='本次提交标识：响应丢失后重试必须保持不变')
    type_id: int = Field(ge=1, le=2, description="提报类型", json_schema_extra={"enum_code": "feedback_type"})
    module_id: PositiveId = Field(description="涉及模块", json_schema_extra={"enum_code": "feedback_module"})
    category_id: PositiveId = Field(description="具体类别：根据提报类型引用对应类别枚举")
    impact_id: PositiveId = Field(description="影响程度", json_schema_extra={"enum_code": "feedback_impact"})
    title: str = Field(min_length=1, max_length=200, description="标题")
    description: FactText = Field(description="详细说明")
    expected_result: FactText = Field(description="期望结果")
    steps: str = Field(default="", max_length=10000, description="复现步骤：问题必填")

    @model_validator(mode="after")
    def require_issue_steps(self):
        if self.type_id == 1 and not self.steps:
            raise ValueError("问题提报必须填写复现步骤")
        return self


class FeedbackSupplement(FeedbackInput):
    version: PositiveId = Field(description="预期记录版本")
    description: FactText = Field(description="补充信息")


class FeedbackHandle(FeedbackInput):
    version: PositiveId = Field(description="预期记录版本")
    status_id: int = Field(ge=1, le=6, description="处理状态", json_schema_extra={"enum_code": "feedback_status"})
    opinion: FactText = Field(description="处理意见")
    outcome_id: PositiveId | None = Field(default=None, description="处理结论", json_schema_extra={"enum_code": "feedback_outcome"})
    cause_id: PositiveId | None = Field(default=None, description="处理归因", json_schema_extra={"enum_code": "feedback_cause"})

    @model_validator(mode="after")
    def validate_terminal_conclusion(self):
        # Fixed workflow IDs stay meaningful after administrators rename labels.
        allowed = {5: {1, 2, 3, 4}, 6: {5, 6}}
        if self.status_id in allowed:
            if self.outcome_id not in allowed[self.status_id]:
                raise ValueError("完成或关闭状态必须选择相符的处理结论")
            if self.cause_id is None:
                raise ValueError("完成或关闭状态必须填写处理归因")
        return self
