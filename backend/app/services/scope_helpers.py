"""Filter expressions for relationships the models express indirectly.

Invoices, projects, allocations and revenue rows have no business_unit_id
of their own: they belong to a BU through their client (Client.
business_unit_id) or, for Revenue, through its BU context. Invoices reach
an opportunity through their project. These are subquery-based filter
expressions, so they drop into any existing .filter() without adding joins.
"""
from sqlalchemy import select

from app.models.client import Client


def client_ids_in_bu(business_unit_id):
    return select(Client.id).where(Client.business_unit_id == business_unit_id)


def invoice_in_bu(business_unit_id):
    from app.models.invoice import Invoice

    return Invoice.client_id.in_(client_ids_in_bu(business_unit_id))


def invoice_for_opportunity(opportunity_id):
    from app.models.invoice import Invoice
    from app.models.project import Project

    return Invoice.project_id.in_(select(Project.id).where(Project.opportunity_id == opportunity_id))


def project_in_bu(business_unit_id):
    from app.models.project import Project

    return Project.client_id.in_(client_ids_in_bu(business_unit_id))


def allocation_in_bu(business_unit_id):
    from app.models.employee_allocation import EmployeeAllocation

    return EmployeeAllocation.client_id.in_(client_ids_in_bu(business_unit_id))


def opportunity_in_bu(business_unit_id):
    from app.models.opportunity import Opportunity

    return Opportunity.client_id.in_(client_ids_in_bu(business_unit_id))


def revenue_in_bu(business_unit_id):
    from app.models.business_unit_context import BusinessUnitContext
    from app.models.revenue import Revenue

    return Revenue.bu_context_id.in_(
        select(BusinessUnitContext.id).where(BusinessUnitContext.business_unit_id == business_unit_id)
    )
