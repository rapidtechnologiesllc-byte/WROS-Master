"""
Shared enums for ISG P&L reporting, revenue recognition, and partner attribution.

These enums define the master vocabulary for:
- Service classification (Consulting, System Integration, Staff Augmentation, etc.)
- Guidewire module focus (PolicyCenter, ClaimsCenter, etc.)
- Pricing models (FTE, Transaction-based, Fixed Bid, etc.)
- Client lines of business (Personal, Commercial, Specialty)

Used by:
- Opportunity (service, module, pricing_model)
- Partner ROI Dashboard (revenue breakdown by service/module)
- Invoice Management (revenue recognition by classification)
- Forecast vs Actual (revenue attribution by service type)
"""

# Service Types - primary service classification for ISG reporting
SERVICE_TYPES = (
    "Consulting & Advisory",
    "System Integration",
    "System Implementation & Managed Services",
    "QA & Testing",
    "Data Migration",
    "Cloud Migration",
    "Analytics and Insights",
    "Digital Experiences",
    "Staff Augmentation",
    "Others",
)

# Guidewire Module Types - which Guidewire product is the engagement centered on?
MODULE_TYPES = (
    "PolicyCenter",
    "ClaimsCenter",
    "BillingCenter",
    "InsuranceSuite",
    "InsuranceNow",
    "PricingCenter",
    "UnderwritingCenter",
    "Jutro Digital",
    "Data and Analytics",
    "ProNavigator",
    "Guidewire Marketplace accelerators",
    "Others",
)

# Client Type / Line of Business - for ISG revenue breakdown
CLIENT_TYPES = (
    "Personal lines",
    "Commercial lines",
    "Specialty lines",
    "Others",
)

# Pricing Model Types - how is this engagement billed?
PRICING_MODEL_TYPES = (
    "FTE-based",
    "Transaction-based",
    "Per policy",
    "Outcome based/profit and risk sharing",
    "Rebadge of Carrier FTEs",
    "Monetization of Carrier Assets",
    "Time and Material (T&M)",
    "Fixed Bid",
    "As-a-Service/Managed service",
    "Service-as-a-software",
    "Others",
)
