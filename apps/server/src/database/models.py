import enum
from enum import Enum
from tortoise import fields, models

class TimestampMixin(models.Model):
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    deleted_at = fields.DatetimeField(null=True)

    class Meta:
        abstract = True

class FundMandate(TimestampMixin):
    id = fields.IntField(pk=True)
    source_url = fields.CharField(max_length=500)
    extracted_parameters = fields.ForeignKeyField('models.ExtractedParameters', related_name='fund_mandate', null=True)
    description = fields.TextField(null=True)

    class Meta:
        table = "fund_mandates"

class ExtractedParameters(TimestampMixin):
    id = fields.IntField(pk=True)
    sourcing_parameters = fields.ForeignKeyField('models.SourcingParameters', related_name='extracted_params', null=True)
    screening_parameters = fields.ForeignKeyField('models.ScreeningParameters', related_name='extracted_params', null=True)
    risk_parameters = fields.ForeignKeyField('models.RiskParameters', related_name='extracted_params', null=True)
    raw_response = fields.JSONField(null=True)

    class Meta:
        table = "extracted_parameters"

class SourcingParameters(TimestampMixin):
    id = fields.IntField(pk=True)
    parameters = fields.JSONField()

    class Meta:
        table = "sourcing_parameters"

class ScreeningParameters(TimestampMixin):
    id = fields.IntField(pk=True)
    parameters = fields.JSONField()

    class Meta:
        table = "screening_parameters"

class RiskParameters(TimestampMixin):
    id = fields.IntField(pk=True)
    parameters = fields.JSONField()

    class Meta:
        table = "risk_parameters"

class Company(TimestampMixin):
    id = fields.IntField(pk=True)
    fund_mandate = fields.ForeignKeyField('models.FundMandate', related_name='companies')
    name = fields.CharField(max_length=255)
    attributes = fields.JSONField()

    class Meta:
        table = "companies"

class Sourcing(TimestampMixin):
    id = fields.IntField(pk=True)
    fund_mandate = fields.ForeignKeyField('models.FundMandate', related_name='sourcings')
    selected_parameters = fields.JSONField()
    companies = fields.ManyToManyField('models.Company', related_name='in_sourcing')

    class Meta:
        table = "sourcing"


class Screening(TimestampMixin):
    id = fields.IntField(pk=True)
    fund_mandate = fields.ForeignKeyField('models.FundMandate', related_name='screenings')
    selected_parameters = fields.JSONField()
    companies = fields.ManyToManyField('models.Company', related_name='in_screening')

    class Meta:
        table = "screening"

class RiskAnalysis(TimestampMixin):
    id = fields.IntField(pk=True)
    fund_mandate = fields.ForeignKeyField('models.FundMandate', related_name='risk_analyses')
    selected_parameters = fields.JSONField()
    companies = fields.ManyToManyField('models.Company', related_name='in_risk_analysis')

    class Meta:
        table = "risk_analysis"
