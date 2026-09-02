"""
import logging
Phase 1: Revenue Recognition & P&L Attribution Infrastructure

This migration adds:
1. Enums for Service, Module, ClientType, PricingModel (ISG reporting)
2. Opportunity fields: service, module, client_type, pricing_model
3. Revenue model for revenue recognition tracking
4. Invoice: opportunity_id link
5. PartnerBUAssignment: core_revenue_share_pct

Revision ID: phase_1_revenue
Revises: (previous migration ID)
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import Enum, String, Integer, ForeignKey, DateTime, Column, func, Boolean, Text
from sqlalchemy.dialects import sqlite, mysql


revision = 'phase_1_revenue'
down_revision = None  # Set to previous migration ID
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add enum columns to opportunities table
    op.add_column('opportunities', sa.Column(
        'service',
        Enum(
            'Consulting & Advisory',
            'System Integration',
            'System Implementation & Managed Services',
            'QA & Testing',
            'Data Migration',
            'Cloud Migration',
            'Analytics and Insights',
            'Digital Experiences',
            'Staff Augmentation',
            'Others',
            name='opportunity_service',
            native_enum=False,
            create_constraint=True
        ),
        nullable=True
    ))

    op.add_column('opportunities', sa.Column(
        'module',
        Enum(
            'PolicyCenter',
            'ClaimsCenter',
            'BillingCenter',
            'InsuranceSuite',
            'InsuranceNow',
            'PricingCenter',
            'UnderwritingCenter',
            'Jutro Digital',
            'Data and Analytics',
            'ProNavigator',
            'Guidewire Marketplace accelerators',
            'Others',
            name='opportunity_module',
            native_enum=False,
            create_constraint=True
        ),
        nullable=True
    ))

    op.add_column('opportunities', sa.Column(
        'client_type',
        Enum(
            'Personal lines',
            'Commercial lines',
            'Specialty lines',
            'Others',
            name='opportunity_client_type',
            native_enum=False,
            create_constraint=True
        ),
        nullable=True
    ))

    op.add_column('opportunities', sa.Column(
        'pricing_model',
        Enum(
            'FTE-based',
            'Transaction-based',
            'Per policy',
            'Outcome based/profit and risk sharing',
            'Rebadge of Carrier FTEs',
            'Monetization of Carrier Assets',
            'Time and Material (T&M)',
            'Fixed Bid',
            'As-a-Service/Managed service',
            'Service-as-a-software',
            'Others',
            name='opportunity_pricing_model',
            native_enum=False,
            create_constraint=True
        ),
        nullable=True
    ))

    # 2. Add opportunity_id to invoices table
    op.add_column('invoices', sa.Column(
        'opportunity_id',
        sa.String(36),
        sa.ForeignKey('opportunities.id'),
        nullable=True,
        index=True
    ))

    # 3. Create revenues table (revenue recognition & P&L attribution)
    op.create_table(
        'revenues',
        sa.Column('id', sa.String(36), primary_key=True, default=sa.text("lower(hex(randomblob(16)))")),
        sa.Column('tenant_id', sa.Integer, sa.ForeignKey('tenants.id'), nullable=True, index=True),
        sa.Column('invoice_id', sa.String(36), sa.ForeignKey('invoices.id'), nullable=False, index=True),
        sa.Column('opportunity_id', sa.String(36), sa.ForeignKey('opportunities.id'), nullable=False, index=True),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id'), nullable=True, index=True),
        sa.Column('client_id', sa.String(36), sa.ForeignKey('clients.id'), nullable=False, index=True),
        sa.Column('business_unit_id', sa.Integer, sa.ForeignKey('business_units.id'), nullable=True, index=True),
        sa.Column('client_owner_id', sa.String(36), sa.ForeignKey('users.UserID'), nullable=True, index=True),

        # Revenue amount
        sa.Column('revenue_usd_cents', sa.Integer, nullable=False),
        sa.Column('currency', Enum(
            'USD', 'INR', 'GBP', 'EUR', 'AUD', 'CAD',
            name='revenue_currency',
            native_enum=False,
            create_constraint=True
        ), nullable=False, default='USD'),

        # Business classification (from opportunity)
        sa.Column('service', sa.String(100), nullable=True),
        sa.Column('module', sa.String(100), nullable=True),
        sa.Column('client_type', sa.String(100), nullable=True),
        sa.Column('pricing_model', sa.String(100), nullable=True),
        sa.Column('business_type', Enum(
            'CORE', 'SPECIALITY',
            name='revenue_business_type',
            native_enum=False,
            create_constraint=True
        ), nullable=True),

        # Partner revenue share (Core business only)
        sa.Column('partner_id', sa.String(36), sa.ForeignKey('partners.id'), nullable=True, index=True),
        sa.Column('partner_revenue_share_pct', sa.Integer, nullable=True),
        sa.Column('partner_revenue_share_usd_cents', sa.Integer, nullable=True),

        # Gross margin tracking
        sa.Column('cost_usd_cents', sa.Integer, nullable=True),
        sa.Column('gross_margin_usd_cents', sa.Integer, nullable=True),
        sa.Column('gross_margin_pct', sa.Integer, nullable=True),

        # Source and timing
        sa.Column('source', Enum(
            'INVOICE', 'MANUAL_ADJUSTMENT', 'CORRECTION',
            name='revenue_source',
            native_enum=False,
            create_constraint=True
        ), nullable=False, default='INVOICE'),
        sa.Column('recognized_at', sa.DateTime, nullable=False, server_default=func.now()),
        sa.Column('created_at', sa.DateTime, server_default=func.now()),
    )

    # 4. Add core_revenue_share_pct to partner_bu_assignments
    op.add_column('partner_bu_assignments', sa.Column(
        'core_revenue_share_pct',
        sa.Integer,
        nullable=True,
        default=0
    ))


def downgrade():
    # Remove columns/tables added in upgrade
    op.drop_column('opportunities', 'service')
    op.drop_column('opportunities', 'module')
    op.drop_column('opportunities', 'client_type')
    op.drop_column('opportunities', 'pricing_model')

    op.drop_column('invoices', 'opportunity_id')
    op.drop_table('revenues')

    op.drop_column('partner_bu_assignments', 'core_revenue_share_pct')
