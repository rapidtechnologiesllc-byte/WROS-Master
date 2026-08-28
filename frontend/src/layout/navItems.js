// NAV_ITEMS, split out of Shell.js so it can be imported without a
// circular dependency: FlashWidget.js needs this list (Report an Issue's
// Affected Screen dropdown), and Shell.js itself renders FlashWidget --
// importing NAV_ITEMS from Shell.js directly deadlocks the module graph
// ("Cannot access 'NAV_ITEMS' before initialization").
import {
  BadgeDollarSign,
  Briefcase,
  BarChart3,
  LayoutDashboard,
  Shield,
  UserCheck,
  Users,
  FileTextIcon,
  Users2,
  ShieldAlert,
  CalendarCheck2,
  UserPlus,
  Send,
  Clock,
  TrendingUp,
  LineChart,
  Globe2,
  Bot,
  FolderKanban,
  AlertOctagon,
  MessageSquareText,
  Receipt,
  Settings,
  Award,
  Gift,
  Zap,
  Database,
  Cog,
} from "lucide-react";
import { ROUTES } from "../utils/Routes";

export const NAV_ITEMS = {
  dashboard: { path: ROUTES.DASHBOARD, label: "Dashboard", icon: LayoutDashboard },
  // S-434 -- org-wide Task Dashboard. Visible to every internal role
  // (every branch below), not gated to any one department/function --
  // Task serves the whole org, per Avinash's explicit direction.
  myTasks: { path: ROUTES.MY_TASKS, label: "My Tasks", icon: CalendarCheck2 },
  // Employee self-service timesheet, 2026-08-04 -- visible to every
  // internal role, same universal-visibility posture as myTasks.
  myTimesheet: { path: ROUTES.MY_TIMESHEET, label: "My Timesheet", icon: Clock },
  // Self-service expense logging, 2026-08-05 -- same universal-
  // visibility posture as myTasks/myTimesheet (Avinash: "the expense
  // is logged by employee so they need to login to their portal").
  myExpenses: { path: ROUTES.MY_EXPENSES, label: "My Expenses", icon: Receipt },
  // Employee referral program tracking - visible to all employees
  myReferrals: { path: ROUTES.MY_REFERRALS, label: "My Referrals", icon: Gift },
  candidates: { path: ROUTES.CANDIDATES, label: "Candidates", icon: Users },
  jobs: { path: ROUTES.JOBS, label: "Jobs", icon: Briefcase },
  candidateReview: { path: ROUTES.HM_CANDIDATE_REVIEW, label: "Candidate Review", icon: UserCheck },
  offerLetters: { path: ROUTES.OFFERS, label: "Offer Letters", icon: FileTextIcon },
  offerLettersListing: { path: ROUTES.OFFERS_LISTING, label: "Offer Letters", icon: FileTextIcon },
  submissions: { path: ROUTES.SUBMISSIONS, label: "Submissions", icon: Send },
  employees: { path: ROUTES.EMPLOYEES, label: "Employees", icon: UserPlus },
  employeeConversion: { path: ROUTES.EMPLOYEE_CONVERSION, label: "Convert to Employee", icon: UserPlus },
  // HRMS-1105/S-320 -- Resource Management Agent. No dedicated
  // Partner/Resource Manager role exists in this codebase's role set
  // yet, so this is scoped to the roles that already get HR/oversight
  // nav items (SUPER_USER, ADMIN, HR Manager) as the closest proxy --
  // flagged for Avinash to confirm/adjust during story review.
  resourceManagement: { path: ROUTES.RESOURCE_MANAGEMENT, label: "Resource Management", icon: Users2 },
  allocations: { path: ROUTES.ALLOCATIONS, label: "Allocations", icon: Briefcase },
  // S-353/HRMS-0514 + S-373/HRMS-0529 -- same role scoping rationale.
  corePull: { path: ROUTES.CORE_PULL, label: "Core-Pull & Pool Guard", icon: ShieldAlert },
  // Client Management -- add/edit client details, real gap flagged
  // 2026-08-05 (no client CRUD UI existed anywhere before this).
  clientManagement: { path: ROUTES.CLIENT_MANAGEMENT, label: "Client Management", icon: Briefcase },
  // S-372/HRMS-0528 -- same role scoping rationale.
  demandConfirmation: { path: ROUTES.DEMAND_CONFIRMATION, label: "Demand Confirmation", icon: CalendarCheck2 },
  utilization: { path: ROUTES.UTILIZATION_DASHBOARD, label: "Utilization & Bench Cost", icon: BarChart3 },
  forecast: { path: ROUTES.FORECAST, label: "Resource Forecast", icon: TrendingUp },
  forecastVsActual: { path: ROUTES.FORECAST_VS_ACTUAL, label: "Forecast vs Actual", icon: TrendingUp },
  htdIntake: { path: ROUTES.HTD_INTAKE, label: "HTD Intake", icon: AlertOctagon },
  projects: { path: ROUTES.PROJECTS, label: "Projects", icon: FolderKanban },
  // S-364/S-365 -- 30-Day Buddy Program KPI tracking + graduation gate.
  buddyProgram: { path: ROUTES.BUDDY_PROGRAM, label: "Buddy Program", icon: UserCheck },
  timesheets: { path: ROUTES.TIMESHEETS, label: "Timesheets", icon: Clock },
  invoices: { path: ROUTES.INVOICES, label: "Invoices", icon: BadgeDollarSign },
  invoiceManagement: { path: ROUTES.INVOICE_MANAGEMENT, label: "Invoice Management", icon: BadgeDollarSign },
  revenue: { path: ROUTES.REVENUE, label: "Revenue", icon: LineChart },
  // EPIC-02/03 Revenue Visibility Engine, 2026-08-05 -- Opportunity
  // pipeline (S-236/237), gated the same as the rest of Finance via
  // revenue.view server-side.
  opportunityPipeline: { path: ROUTES.OPPORTUNITY_PIPELINE, label: "Opportunity Pipeline", icon: TrendingUp },
  executiveRevenueDashboard: { path: ROUTES.EXECUTIVE_REVENUE_DASHBOARD, label: "Executive Revenue", icon: LineChart },
  financeOperations: { path: ROUTES.FINANCE_OPERATIONS, label: "Finance Operations", icon: BadgeDollarSign },
  partnerRoi: { path: ROUTES.PARTNER_ROI, label: "Partner ROI Agent", icon: TrendingUp },
  ceoFyProgress: { path: ROUTES.CEO_FY_PROGRESS, label: "CEO FY Progress", icon: BarChart3 },
  cfoDashboard: { path: ROUTES.CFO_DASHBOARD, label: "CFO Agent", icon: LineChart },
  usersAccessControl: { path: ROUTES.USERS_ACCESS_CONTROL, label: "Users & Access Control", icon: Shield },
  certifications: { path: ROUTES.CERTIFICATIONS, label: "Certifications", icon: Award },
  // S-219/HRMS-0121 -- tenant-wide setting, grouped under Admin.
  tenantLocale: { path: ROUTES.TENANT_LOCALE, label: "Locale & Currency", icon: Globe2 },
  // S-077/HRMS-0477 -- unified Thunder config, Super User only server-side
  // (tenant.ai_config) -- visible in nav to the same Admin-group audience
  // as tenantLocale above, same posture (backend enforces the real gate).
  tenantAiConfig: { path: ROUTES.TENANT_AI_CONFIG, label: "AI Configuration", icon: Bot },
  // Help Desk/IT-HR Ticketing -- category routing + SLA policy config,
  // gated server-side by rbac.manage same as the other Admin items.
  ticketRoutingAdmin: { path: ROUTES.TICKET_ROUTING_ADMIN, label: "Ticket Routing & SLA", icon: CalendarCheck2 },
  // Executive Signal & Culture Agent -- advisory-only org-health +
  // recognition + feedback cycle; Super User/Admin only (personnel data).
  executiveSignal: { path: ROUTES.EXECUTIVE_SIGNAL, label: "Executive Signal", icon: LineChart },
  // S-215/HRMS-0117 -- Error Logging Framework, Admin/Director-only per spec.
  errorLog: { path: ROUTES.ERROR_LOG, label: "Error Log", icon: AlertOctagon },
  // S-213/HRMS-0115 -- System Configuration & Admin Settings Panel.
  // Read is broader (any internal user); the backend enforces the real
  // Admin-only write gate, same posture as every other Admin item here.
  adminSettings: { path: ROUTES.ADMIN_SETTINGS, label: "Admin Settings", icon: Settings },
  // Admin Weekly Recap Dashboard -- CEO/Director weekly executive summary
  // (weekly agent health, pipeline status, performance metrics).
  adminWeeklyRecap: { path: ROUTES.ADMIN_WEEKLY_RECAP, label: "Weekly Recap", icon: BarChart3 },
  // Message Queue Dashboard -- monitor background tasks, Celery queue status,
  // failed jobs, and retry capabilities. Real-time visibility into async operations.
  messageQueueDashboard: { path: ROUTES.MESSAGE_QUEUE_DASHBOARD, label: "Message Queue", icon: MessageSquareText },
  // Queue Management -- channel-based message queue with engagement tracking,
  // retry logic, and email delivery metrics. Real-time visibility into all message channels.
  queueManagement: { path: '/admin/queue-management', label: "Queue Management", icon: MessageSquareText },
  // S-014/HRMS-0414 -- template.manage-gated activate action lives on
  // the screen itself; the nav entry is visible to anyone who can see
  // the Admin group (recruiters can create/preview, just not activate).
  messageTemplates: { path: ROUTES.MESSAGE_TEMPLATES, label: "Message Templates", icon: MessageSquareText },
  // Agent Configuration -- manage agent pipeline settings and orchestration
  // Super User/Admin only. Configure agents, set queue names, manage pipeline order.
  agentConfig: { path: ROUTES.AGENT_CONFIG, label: "Agent Configuration", icon: Cog },
  // S-028/HRMS-0428 -- Self-Learning Model (SLM) for resume parsing management.
  // Super User only. Monitor parsing accuracy, manage training data, retrain model.
  slmDashboard: { path: ROUTES.SLM_DASHBOARD, label: "Resume Parser (SLM)", icon: Zap },
  slmTraining: { path: ROUTES.SLM_TRAINING, label: "SLM Training Data", icon: Database },
  // S-062/HRMS-0462 -- candidates that need a human right now (escalations,
  // high drop risk, SLA breaches, etc.), same recruiter-facing grouping as
  // the rest of Recruitment.
  interventionQueue: { path: ROUTES.INTERVENTION_QUEUE, label: "Intervention Queue", icon: AlertOctagon },
  // Rehire guard, Part 2 of the interview regrouping + rehire guard
  // priority (2026-08-05) -- candidates with a past no-hire outcome
  // whose re-interview justification needs a hiring manager's sign-off.
  rehireApprovals: { path: ROUTES.REHIRE_APPROVALS, label: "Rehire Approvals", icon: AlertOctagon },
  // S-063/HRMS-0463 -- broader visibility companion to the intervention
  // queue above (all active candidates + trends, not just the ones
  // needing action right now).
  riskDashboard: { path: ROUTES.RISK_DASHBOARD, label: "Risk Dashboard", icon: BarChart3 },
  // S-071/HRMS-0471 -- leadership-facing KPI view of Thunder's own
  // autonomous performance, distinct from the per-candidate risk view above.
  thunderAnalytics: { path: ROUTES.THUNDER_ANALYTICS, label: "Thunder Analytics", icon: LineChart },
  // S-074/HRMS-0474 -- CSV import + rate-limited Thunder launch for
  // many candidates at once.
  bulkLaunch: { path: ROUTES.BULK_LAUNCH, label: "Bulk Launch", icon: UserPlus },

  // Training & Certifications (new)
  trainingCertification: { path: ROUTES.TRAINING_CERTIFICATION, label: "Training & Certifications", icon: Award },

  // Troy's Partner Dashboard (new)
  troyPartnerDashboard: { path: ROUTES.TROY_PARTNER_DASHBOARD, label: "Partner Dashboard", icon: BarChart3 },

  // BI Explorer (new)
  biExplorer: { path: ROUTES.BI_EXPLORER, label: "BI Explorer", icon: BarChart3 },

  // BU Head Dashboard (new)
  buHeadDashboard: { path: ROUTES.BU_HEAD_DASHBOARD, label: "BU Head Dashboard", icon: BarChart3 },
};
